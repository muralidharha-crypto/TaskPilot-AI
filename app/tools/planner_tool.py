import json
from datetime import datetime, date, timedelta
from app.models.database import Database
from app.tools.task_tool import TaskTool
from app.tools.scheduler_tool import SchedulerTool


class PlannerTool:

    @staticmethod
    def calculate_priority_score(
        deadline_str,
        duration_hours,
        importance="MEDIUM",
        dependency_count=0
    ):
        """
        Calculates an explainable priority score between 0 and 100 based on:
        - Deadline Urgency (40%)
        - Task Importance (30%)
        - Estimated Effort (20%)
        - Dependency Impact (10%)
        """

        today = date.today()
        urgency_score = 50.0
        days_until_deadline = None

        if deadline_str:
            try:
                d_date = datetime.strptime(
                    deadline_str.split("T")[0],
                    "%Y-%m-%d"
                ).date()

                days_until_deadline = (d_date - today).days

                if days_until_deadline <= 0:
                    urgency_score = 100.0
                elif days_until_deadline == 1:
                    urgency_score = 95.0
                elif days_until_deadline <= 3:
                    urgency_score = 80.0
                elif days_until_deadline <= 7:
                    urgency_score = 60.0
                else:
                    urgency_score = 30.0

            except Exception:
                urgency_score = 50.0

        # Importance
        imp_map = {
            "CRITICAL": 100.0,
            "HIGH": 85.0,
            "MEDIUM": 60.0,
            "LOW": 30.0
        }

        importance_score = imp_map.get(
            importance.upper(),
            60.0
        )

        # Effort
        effort = float(duration_hours or 1.0)

        effort_score = min(
            100.0,
            max(20.0, effort * 20.0)
        )

        # Dependencies
        dep_score = min(
            100.0,
            dependency_count * 25.0
        )

        total_score = round(
            (urgency_score * 0.40) +
            (importance_score * 0.30) +
            (effort_score * 0.20) +
            (dep_score * 0.10),
            1
        )

        if total_score >= 75:
            priority_label = "HIGH"
        elif total_score >= 50:
            priority_label = "MEDIUM"
        else:
            priority_label = "LOW"

        reasons = []

        if days_until_deadline is not None:
            if days_until_deadline <= 1:
                reasons.append(
                    f"due in {days_until_deadline} day(s) "
                    f"(urgent deadline)"
                )
            else:
                reasons.append(
                    f"due in {days_until_deadline} days"
                )

        reasons.append(
            f"{importance.upper()} importance"
        )

        reasons.append(
            f"{effort}h estimated effort"
        )

        if dependency_count > 0:
            reasons.append(
                f"{dependency_count} dependent tasks"
            )

        explanation = (
            f"Assigned {priority_label} "
            f"(Score: {total_score}/100) because task is "
            f"{', '.join(reasons)}."
        )

        return {
            "score": total_score,
            "label": priority_label,
            "explanation": explanation,
            "breakdown": {
                "urgency_score": urgency_score,
                "importance_score": importance_score,
                "effort_score": effort_score,
                "dependency_score": dep_score
            }
        }

    # ---------------------------------------------------------
    # PRIORITIZATION
    # ---------------------------------------------------------

    @staticmethod
    def prioritize_tasks(tasks_list=None):
        """Ranks tasks based on calculated priority scores."""

        if tasks_list is None:
            tasks_list = TaskTool.list_tasks(
                status="PENDING"
            )

        scored_tasks = []

        for t in tasks_list:

            # Never prioritize fixed calendar events
            if (
                t.get("event_type") == "FIXED_EVENT"
                or t.get("type") == "FIXED_EVENT"
            ):
                continue

            deps = t.get("dependencies", [])

            dep_count = (
                len(deps)
                if isinstance(deps, list)
                else 0
            )

            score_data = PlannerTool.calculate_priority_score(
                deadline_str=t.get("deadline"),
                duration_hours=t.get(
                    "duration_hours",
                    1.0
                ),
                importance=t.get(
                    "priority",
                    "MEDIUM"
                ),
                dependency_count=dep_count
            )

            t_copy = dict(t)

            t_copy["calculated_score"] = (
                score_data["score"]
            )

            t_copy["calculated_priority"] = (
                score_data["label"]
            )

            t_copy["priority_explanation"] = (
                score_data["explanation"]
            )

            scored_tasks.append(t_copy)

        scored_tasks.sort(
            key=lambda x: x["calculated_score"],
            reverse=True
        )

        return scored_tasks

    # ---------------------------------------------------------
    # TIME HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _time_to_minutes(time_str):
        """Converts HH:MM into minutes from midnight."""

        try:
            hour, minute = map(
                int,
                time_str.split(":")[:2]
            )

            return hour * 60 + minute

        except Exception:
            return None

    @staticmethod
    def _minutes_to_time(minutes):
        """Converts minutes from midnight into HH:MM."""

        hour = minutes // 60
        minute = minutes % 60

        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _normalize_fixed_events(fixed_events):
        """
        Converts fixed events into a consistent internal format.
        Invalid events are ignored safely.
        """

        normalized = []

        for event in fixed_events or []:

            start_time = event.get("start_time")
            end_time = event.get("end_time")

            if not start_time:
                continue

            start_minutes = PlannerTool._time_to_minutes(
                start_time
            )

            if start_minutes is None:
                continue

            # If no end time exists, assume 1 hour.
            if end_time:
                end_minutes = PlannerTool._time_to_minutes(
                    end_time
                )
            else:
                end_minutes = start_minutes + 60

            if end_minutes <= start_minutes:
                end_minutes = start_minutes + 60

            normalized.append({
                "id": event.get("id"),
                "title": event.get(
                    "title",
                    "Fixed Event"
                ),
                "date_str": event.get(
                    "date_str"
                ),
                "start_time": PlannerTool._minutes_to_time(
                    start_minutes
                ),
                "end_time": PlannerTool._minutes_to_time(
                    end_minutes
                ),
                "start_minutes": start_minutes,
                "end_minutes": end_minutes,
                "event_type": "FIXED_EVENT",
                "blocks_schedule": True,
                "is_actionable": False
            })

        return normalized

    @staticmethod
    def _event_overlaps(
        start_minutes,
        end_minutes,
        event_start,
        event_end
    ):
        """
        Returns True if two time intervals overlap.

        Example:

        Task: 18:30 - 19:30
        Event: 19:00 - 20:00

        Result: True
        """

        return (
            start_minutes < event_end
            and end_minutes > event_start
        )

    @staticmethod
    def _find_available_slot(
        current_date,
        duration_minutes,
        current_time_minutes,
        start_hour,
        fixed_events
    ):
        """
        Finds the next available slot that does not overlap
        with a fixed event.

        Default working window:
            18:00 - 21:00
        """

        window_start = start_hour * 60
        window_end = window_start + 180

        candidate = max(
            current_time_minutes,
            window_start
        )

        # Try repeatedly until a free slot is found.
        while candidate + duration_minutes <= window_end:

            candidate_end = (
                candidate + duration_minutes
            )

            conflict = False

            for event in fixed_events:

                event_date = event.get("date_str")

                if event_date != current_date.isoformat():
                    continue

                if PlannerTool._event_overlaps(
                    candidate,
                    candidate_end,
                    event["start_minutes"],
                    event["end_minutes"]
                ):
                    conflict = True

                    # Jump directly to the end of the
                    # conflicting fixed event.
                    candidate = event["end_minutes"]
                    break

            if not conflict:
                return candidate

        return None

    # ---------------------------------------------------------
    # PLAN GENERATION
    # ---------------------------------------------------------

    @staticmethod
    def generate_plan(
        tasks=None,
        daily_hours=3.0,
        start_date=None,
        start_hour=18,
        fixed_events=None
    ):
        """
        Generates a chronological multi-day study/execution schedule.

        Fixed events are treated as BLOCKED calendar periods.

        Example:

            18:00 - 19:00  DBMS
            19:00 - 20:00  Tutoring Class [FIXED]
            20:00 - 21:00  DBMS
        """

        if tasks is None:
            tasks = TaskTool.list_tasks()

        fixed_events = PlannerTool._normalize_fixed_events(
            fixed_events
        )

        # -----------------------------------------------------
        # Remove fixed events from actionable tasks
        # -----------------------------------------------------

        pending_tasks = [
            t for t in tasks
            if t.get(
                "status",
                "PENDING"
            ) in (
                "PENDING",
                "IN_PROGRESS"
            )
            and t.get("event_type") != "FIXED_EVENT"
            and t.get("type") != "FIXED_EVENT"
        ]

        # -----------------------------------------------------
        # Build fixed-event sessions
        # -----------------------------------------------------

        fixed_sessions = []

        for event in fixed_events:

            fixed_sessions.append({
                "task_id": None,
                "subtask_id": None,
                "title": event["title"],
                "date_str": event.get(
                    "date_str"
                ),
                "start_time": event["start_time"],
                "end_time": event["end_time"],
                "duration_hours": round(
                    (
                        event["end_minutes"]
                        - event["start_minutes"]
                    ) / 60,
                    2
                ),
                "priority": "FIXED",
                "deadline": None,
                "event_type": "FIXED_EVENT",
                "blocks_schedule": True,
                "is_actionable": False
            })

        # -----------------------------------------------------
        # If there are no actionable tasks, return fixed events
        # -----------------------------------------------------

        if not pending_tasks:

            if not fixed_sessions:
                return {
                    "days": [],
                    "total_hours": 0.0,
                    "message": (
                        "No pending tasks to schedule"
                    )
                }

            days = {}

            for session in fixed_sessions:

                session_date = session["date_str"]

                if not session_date:
                    continue

                if session_date not in days:
                    d = datetime.strptime(
                        session_date,
                        "%Y-%m-%d"
                    ).date()

                    days[session_date] = {
                        "date": session_date,
                        "day_name": d.strftime("%A"),
                        "formatted_date": d.strftime(
                            "%b %d, %Y"
                        ),
                        "total_hours": 0.0,
                        "sessions": []
                    }

                days[session_date]["sessions"].append(
                    session
                )

            for day in days.values():
                day["sessions"].sort(
                    key=lambda x: x["start_time"]
                )

            return {
                "days": list(days.values()),
                "total_hours": 0.0,
                "daily_capacity": float(
                    daily_hours
                ),
                "task_count": 0,
                "items_scheduled": 0,
                "fixed_event_count": len(
                    fixed_sessions
                ),
                "generated_at": datetime.now().isoformat()
            }

        # -----------------------------------------------------
        # Prioritize actionable tasks
        # -----------------------------------------------------

        prioritized = PlannerTool.prioritize_tasks(
            pending_tasks
        )

        # -----------------------------------------------------
        # Build execution items
        # -----------------------------------------------------

        work_items = []

        for t in prioritized:

            subtasks = t.get(
                "subtasks",
                []
            )

            if subtasks and len(subtasks) > 0:

                for st in subtasks:

                    if isinstance(st, str):
                        st_title = st
                        st_dur = 0.5
                        st_id = None
                        st_status = "PENDING"

                    else:
                        st_title = st.get(
                            "title",
                            ""
                        )

                        st_dur = float(
                            st.get(
                                "duration_hours",
                                0.5
                            )
                        )

                        st_id = st.get("id")

                        st_status = st.get(
                            "status",
                            "PENDING"
                        )

                    if st_status == "COMPLETED":
                        continue

                    work_items.append({
                        "task_id": t.get("id"),
                        "task_title": t.get("title"),
                        "subtask_id": st_id,
                        "item_title": (
                            f"{t.get('title')}: "
                            f"{st_title}"
                        ),
                        "duration_hours": st_dur,
                        "deadline": t.get(
                            "deadline"
                        ),
                        "priority": t.get(
                            "calculated_priority",
                            "MEDIUM"
                        )
                    })

            else:

                work_items.append({
                    "task_id": t.get("id"),
                    "task_title": t.get("title"),
                    "subtask_id": None,
                    "item_title": t.get(
                        "title"
                    ),
                    "duration_hours": float(
                        t.get(
                            "duration_hours",
                            1.0
                        )
                    ),
                    "deadline": t.get(
                        "deadline"
                    ),
                    "priority": t.get(
                        "calculated_priority",
                        "MEDIUM"
                    )
                })

        # -----------------------------------------------------
        # Schedule work around fixed events
        # -----------------------------------------------------

        cur_date = (
            datetime.strptime(
                start_date,
                "%Y-%m-%d"
            ).date()
            if start_date
            else date.today()
        )

        daily_capacity = float(
            daily_hours
        )

        days_schedule = []

        current_day_date = cur_date
        current_day_sessions = []
        current_day_used = 0.0
        current_time_minutes = start_hour * 60

        for item in work_items:

            remaining_minutes = int(
                item["duration_hours"] * 60
            )

            # -------------------------------------------------
            # Break a task into chunks when necessary.
            #
            # Example:
            #
            # 2h DBMS
            # 18-19 DBMS
            # 19-20 Tutoring
            # 20-21 DBMS
            # -------------------------------------------------

            while remaining_minutes > 0:

                # Find an available slot
                slot_start = PlannerTool._find_available_slot(
                    current_day_date,
                    remaining_minutes,
                    current_time_minutes,
                    start_hour,
                    fixed_events
                )

                # If the whole remaining task does not fit,
                # try a smaller slot before the next fixed event
                # or end of the working window.
                if slot_start is None:

                    window_end = (
                        start_hour * 60
                        + 180
                    )

                    candidate = max(
                        current_time_minutes,
                        start_hour * 60
                    )

                    next_block_start = window_end

                    for event in fixed_events:

                        if event.get("date_str") != (
                            current_day_date.isoformat()
                        ):
                            continue

                        if (
                            event["start_minutes"]
                            >= candidate
                        ):
                            next_block_start = min(
                                next_block_start,
                                event["start_minutes"]
                            )

                    available_minutes = (
                        next_block_start - candidate
                    )

                    if available_minutes <= 0:

                        # Save current day
                        if current_day_sessions:
                            days_schedule.append({
                                "date": current_day_date.isoformat(),
                                "day_name": current_day_date.strftime(
                                    "%A"
                                ),
                                "formatted_date": current_day_date.strftime(
                                    "%b %d, %Y"
                                ),
                                "total_hours": round(
                                    current_day_used,
                                    1
                                ),
                                "sessions": current_day_sessions
                            })

                        # Move to next day
                        current_day_date += timedelta(
                            days=1
                        )

                        current_day_sessions = []
                        current_day_used = 0.0
                        current_time_minutes = (
                            start_hour * 60
                        )

                        continue

                    chunk_minutes = min(
                        remaining_minutes,
                        available_minutes
                    )

                    slot_start = candidate

                else:

                    # Use the complete remaining duration
                    chunk_minutes = remaining_minutes

                    # Prevent crossing the daily capacity
                    remaining_capacity_minutes = int(
                        (
                            daily_capacity
                            - current_day_used
                        ) * 60
                    )

                    if (
                        remaining_capacity_minutes
                        <= 0
                    ):

                        if current_day_sessions:
                            days_schedule.append({
                                "date": current_day_date.isoformat(),
                                "day_name": current_day_date.strftime(
                                    "%A"
                                ),
                                "formatted_date": current_day_date.strftime(
                                    "%b %d, %Y"
                                ),
                                "total_hours": round(
                                    current_day_used,
                                    1
                                ),
                                "sessions": current_day_sessions
                            })

                        current_day_date += timedelta(
                            days=1
                        )

                        current_day_sessions = []
                        current_day_used = 0.0
                        current_time_minutes = (
                            start_hour * 60
                        )

                        continue

                    chunk_minutes = min(
                        chunk_minutes,
                        remaining_capacity_minutes
                    )

                # -------------------------------------------------
                # Create session
                # -------------------------------------------------

                session_start = slot_start
                session_end = (
                    session_start
                    + chunk_minutes
                )

                session = {
                    "task_id": item["task_id"],
                    "subtask_id": item.get(
                        "subtask_id"
                    ),
                    "title": item["item_title"],
                    "date_str": current_day_date.isoformat(),
                    "start_time": PlannerTool._minutes_to_time(
                        session_start
                    ),
                    "end_time": PlannerTool._minutes_to_time(
                        session_end
                    ),
                    "duration_hours": round(
                        chunk_minutes / 60,
                        2
                    ),
                    "priority": item["priority"],
                    "deadline": item.get(
                        "deadline"
                    ),
                    "event_type": "TASK_STUDY",
                    "blocks_schedule": False,
                    "is_actionable": True
                }

                current_day_sessions.append(
                    session
                )

                current_day_used += (
                    chunk_minutes / 60
                )

                current_time_minutes = (
                    session_end
                )

                remaining_minutes -= (
                    chunk_minutes
                )

                # -------------------------------------------------
                # If there is still work remaining and we've hit
                # the daily capacity, move to next day.
                # -------------------------------------------------

                if (
                    remaining_minutes > 0
                    and current_day_used >= daily_capacity
                ):

                    if current_day_sessions:
                        days_schedule.append({
                            "date": current_day_date.isoformat(),
                            "day_name": current_day_date.strftime(
                                "%A"
                            ),
                            "formatted_date": current_day_date.strftime(
                                "%b %d, %Y"
                            ),
                            "total_hours": round(
                                current_day_used,
                                1
                            ),
                            "sessions": current_day_sessions
                        })

                    current_day_date += timedelta(
                        days=1
                    )

                    current_day_sessions = []
                    current_day_used = 0.0
                    current_time_minutes = (
                        start_hour * 60
                    )

        # ---------------------------------------------------------
        # Save final day
        # ---------------------------------------------------------

        if current_day_sessions:

            days_schedule.append({
                "date": current_day_date.isoformat(),
                "day_name": current_day_date.strftime(
                    "%A"
                ),
                "formatted_date": current_day_date.strftime(
                    "%b %d, %Y"
                ),
                "total_hours": round(
                    current_day_used,
                    1
                ),
                "sessions": current_day_sessions
            })

        # ---------------------------------------------------------
        # Add fixed events into their calendar days
        # ---------------------------------------------------------

        for event in fixed_sessions:

            event_date = event.get(
                "date_str"
            )

            if not event_date:
                continue

            existing_day = None

            for day in days_schedule:
                if day["date"] == event_date:
                    existing_day = day
                    break

            if existing_day is None:

                event_date_obj = datetime.strptime(
                    event_date,
                    "%Y-%m-%d"
                ).date()

                existing_day = {
                    "date": event_date,
                    "day_name": event_date_obj.strftime(
                        "%A"
                    ),
                    "formatted_date": event_date_obj.strftime(
                        "%b %d, %Y"
                    ),
                    "total_hours": 0.0,
                    "sessions": []
                }

                days_schedule.append(
                    existing_day
                )

            existing_day["sessions"].append(
                event
            )

        # ---------------------------------------------------------
        # Sort days and sessions chronologically
        # ---------------------------------------------------------

        days_schedule.sort(
            key=lambda x: x["date"]
        )

        for day in days_schedule:

            day["sessions"].sort(
                key=lambda x: x.get(
                    "start_time",
                    "00:00"
                )
            )

        # ---------------------------------------------------------
        # Calculate study hours
        # ---------------------------------------------------------

        total_hours = sum(
            day["total_hours"]
            for day in days_schedule
        )

        return {
            "days": days_schedule,
            "total_hours": round(
                total_hours,
                1
            ),
            "daily_capacity": daily_capacity,
            "task_count": len(
                pending_tasks
            ),
            "items_scheduled": len(
                work_items
            ),
            "fixed_event_count": len(
                fixed_sessions
            ),
            "fixed_events": fixed_sessions,
            "generated_at": datetime.now().isoformat()
        }

    # ---------------------------------------------------------
    # REPLANNING
    # ---------------------------------------------------------

    @staticmethod
    def replan(
        conflicts=None,
        daily_hours=3.0,
        fixed_events=None
    ):
        """
        Generates an updated plan after conflicts/missed
        sessions are detected.
        """

        tasks = TaskTool.list_tasks()

        new_plan = PlannerTool.generate_plan(
            tasks=tasks,
            daily_hours=daily_hours,
            start_date=date.today().isoformat(),
            fixed_events=fixed_events or []
        )

        return new_plan