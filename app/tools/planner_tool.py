from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Config
from app.tools.task_tool import TaskTool


class PlannerTool:
    """Creates prioritized schedules while respecting fixed calendar events."""

    @staticmethod
    def calculate_priority_score(
        deadline_str,
        duration_hours,
        importance="MEDIUM",
        dependency_count=0,
    ):
        """
        Calculate an explainable priority score between 0 and 100.

        Weights:
        - Deadline urgency: 40%
        - Task importance: 30%
        - Estimated effort: 20%
        - Dependency impact: 10%
        """
        today = datetime.now(ZoneInfo(Config.TIMEZONE)).date()
        urgency_score = 50.0
        days_until_deadline = None

        if deadline_str:
            try:
                deadline_date = date.fromisoformat(
                    deadline_str.split("T")[0]
                )
                days_until_deadline = (deadline_date - today).days

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

            except (ValueError, TypeError, AttributeError):
                urgency_score = 50.0

        # Importance
        importance_map = {
            "CRITICAL": 100.0,
            "HIGH": 85.0,
            "MEDIUM": 60.0,
            "LOW": 30.0,
        }

        importance_score = importance_map.get(
            str(importance or "MEDIUM").upper(),
            60.0,
        )

        # Estimated effort
        try:
            effort = float(duration_hours or 1.0)
        except (TypeError, ValueError):
            effort = 1.0

        effort_score = min(
            100.0,
            max(20.0, effort * 20.0),
        )

        # Dependency impact
        try:
            dependency_count = max(0, int(dependency_count or 0))
        except (TypeError, ValueError):
            dependency_count = 0

        dependency_score = min(
            100.0,
            dependency_count * 25.0,
        )

        total_score = round(
            (urgency_score * 0.40)
            + (importance_score * 0.30)
            + (effort_score * 0.20)
            + (dependency_score * 0.10),
            1,
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
                    "(urgent deadline)"
                )
            else:
                reasons.append(
                    f"due in {days_until_deadline} days"
                )

        reasons.append(
            f"{str(importance or 'MEDIUM').upper()} importance"
        )
        reasons.append(f"{effort}h estimated effort")

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
                "dependency_score": dependency_score,
            },
        }

    # ---------------------------------------------------------
    # PRIORITIZATION
    # ---------------------------------------------------------

    @staticmethod
    def prioritize_tasks(tasks_list=None):
        """Rank actionable tasks by calculated priority score."""

        if tasks_list is None:
            tasks_list = TaskTool.list_tasks(status="PENDING")

        scored_tasks = []

        for task in tasks_list:
            # Fixed calendar events are not actionable tasks.
            if (
                task.get("event_type") == "FIXED_EVENT"
                or task.get("type") == "FIXED_EVENT"
            ):
                continue

            dependencies = task.get("dependencies", [])

            dependency_count = (
                len(dependencies)
                if isinstance(dependencies, list)
                else 0
            )

            score_data = PlannerTool.calculate_priority_score(
                deadline_str=task.get("deadline"),
                duration_hours=task.get("duration_hours", 1.0),
                importance=task.get("priority", "MEDIUM"),
                dependency_count=dependency_count,
            )

            task_copy = dict(task)
            task_copy["calculated_score"] = score_data["score"]
            task_copy["calculated_priority"] = score_data["label"]
            task_copy["priority_explanation"] = score_data[
                "explanation"
            ]

            scored_tasks.append(task_copy)

        scored_tasks.sort(
            key=lambda task: task["calculated_score"],
            reverse=True,
        )

        return scored_tasks

    # ---------------------------------------------------------
    # TIME HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _time_to_minutes(time_str):
        """Convert HH:MM into minutes from midnight."""

        try:
            hour, minute = map(
                int,
                time_str.split(":")[:2],
            )
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None

            return hour * 60 + minute

        except (ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def _minutes_to_time(minutes):
        """Convert minutes from midnight into HH:MM."""

        hour = minutes // 60
        minute = minutes % 60

        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _normalize_fixed_events(fixed_events):
        """
        Convert fixed events into a consistent internal format.
        Invalid events are skipped.
        """

        normalized = []

        for event in fixed_events or []:
            if not isinstance(event, dict):
                continue

            start_time = event.get("start_time")
            end_time = event.get("end_time")

            if not start_time:
                continue

            start_minutes = PlannerTool._time_to_minutes(start_time)

            if start_minutes is None:
                continue

            # If no end time exists, assume one hour.
            if end_time:
                end_minutes = PlannerTool._time_to_minutes(end_time)
                if end_minutes is None:
                    continue
            else:
                end_minutes = start_minutes + 60

            if end_minutes <= start_minutes:
                end_minutes = start_minutes + 60

            normalized.append(
                {
                    "id": event.get("id"),
                    "title": event.get("title", "Fixed Event"),
                    "date_str": event.get("date_str"),
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
                    "is_actionable": False,
                }
            )

        return normalized

    @staticmethod
    def _event_overlaps(
        start_minutes,
        end_minutes,
        event_start,
        event_end,
    ):
        """Return True when two time intervals overlap."""

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
        fixed_events,
    ):
        """
        Find an available slot without overlapping fixed events.

        Default working window: start_hour to start_hour + 3 hours.
        """

        window_start = start_hour * 60
        window_end = window_start + 180

        candidate = max(
            current_time_minutes,
            window_start,
        )

        while candidate + duration_minutes <= window_end:
            candidate_end = candidate + duration_minutes
            conflict = False

            for event in fixed_events:
                event_date = event.get("date_str")

                if event_date != current_date.isoformat():
                    continue

                if PlannerTool._event_overlaps(
                    candidate,
                    candidate_end,
                    event["start_minutes"],
                    event["end_minutes"],
                ):
                    conflict = True

                    # Continue searching after the conflicting event.
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
        fixed_events=None,
    ):
        """
        Generate a chronological multi-day schedule.

        Fixed events block their calendar time but are not actionable
        tasks. Remaining work is scheduled around those events.
        """

        if tasks is None:
            tasks = TaskTool.list_tasks()

        fixed_events = PlannerTool._normalize_fixed_events(
            fixed_events
        )

        # Remove fixed events from actionable tasks.
        pending_tasks = [
            task
            for task in tasks
            if task.get("status", "PENDING")
            in ("PENDING", "IN_PROGRESS")
            and task.get("event_type") != "FIXED_EVENT"
            and task.get("type") != "FIXED_EVENT"
        ]

        # Build fixed-event sessions.
        fixed_sessions = []

        for event in fixed_events:
            fixed_sessions.append(
                {
                    "task_id": None,
                    "subtask_id": None,
                    "title": event["title"],
                    "date_str": event.get("date_str"),
                    "start_time": event["start_time"],
                    "end_time": event["end_time"],
                    "duration_hours": round(
                        (
                            event["end_minutes"]
                            - event["start_minutes"]
                        ) / 60,
                        2,
                    ),
                    "priority": "FIXED",
                    "deadline": None,
                    "event_type": "FIXED_EVENT",
                    "blocks_schedule": True,
                    "is_actionable": False,
                }
            )

        # Handle the case where no actionable tasks exist.
        if not pending_tasks:
            if not fixed_sessions:
                return {
                    "days": [],
                    "total_hours": 0.0,
                    "message": "No pending tasks to schedule",
                }

            days = {}

            for session in fixed_sessions:
                session_date = session.get("date_str")

                if not session_date:
                    continue

                try:
                    parsed_date = date.fromisoformat(session_date)
                except (ValueError, TypeError):
                    continue

                if session_date not in days:
                    days[session_date] = {
                        "date": session_date,
                        "day_name": parsed_date.strftime("%A"),
                        "formatted_date": parsed_date.strftime(
                            "%b %d, %Y"
                        ),
                        "total_hours": 0.0,
                        "sessions": [],
                    }

                days[session_date]["sessions"].append(session)

            for day in days.values():
                day["sessions"].sort(
                    key=lambda session: session["start_time"]
                )

            return {
                "days": list(days.values()),
                "total_hours": 0.0,
                "daily_capacity": float(daily_hours),
                "task_count": 0,
                "items_scheduled": 0,
                "fixed_event_count": len(fixed_sessions),
                "generated_at": datetime.now(
                    ZoneInfo(Config.TIMEZONE)
                ).isoformat(),
            }

        # Prioritize actionable tasks.
        prioritized = PlannerTool.prioritize_tasks(pending_tasks)

        # Build execution items.
        work_items = []

        for task in prioritized:
            subtasks = task.get("subtasks", [])

            if subtasks:
                for subtask in subtasks:
                    if isinstance(subtask, str):
                        subtask_title = subtask
                        subtask_duration = 0.5
                        subtask_id = None
                        subtask_status = "PENDING"
                    elif isinstance(subtask, dict):
                        subtask_title = subtask.get("title", "")
                        try:
                            subtask_duration = float(
                                subtask.get("duration_hours", 0.5)
                            )
                        except (ValueError, TypeError):
                            subtask_duration = 0.5

                        subtask_id = subtask.get("id")
                        subtask_status = subtask.get(
                            "status",
                            "PENDING",
                        )
                    else:
                        continue

                    if subtask_status == "COMPLETED":
                        continue

                    work_items.append(
                        {
                            "task_id": task.get("id"),
                            "task_title": task.get("title"),
                            "subtask_id": subtask_id,
                            "item_title": (
                                f"{task.get('title')}: {subtask_title}"
                            ),
                            "duration_hours": subtask_duration,
                            "deadline": task.get("deadline"),
                            "priority": task.get(
                                "calculated_priority",
                                "MEDIUM",
                            ),
                        }
                    )
            else:
                try:
                    duration = float(
                        task.get("duration_hours", 1.0)
                    )
                except (ValueError, TypeError):
                    duration = 1.0

                work_items.append(
                    {
                        "task_id": task.get("id"),
                        "task_title": task.get("title"),
                        "subtask_id": None,
                        "item_title": task.get("title"),
                        "duration_hours": duration,
                        "deadline": task.get("deadline"),
                        "priority": task.get(
                            "calculated_priority",
                            "MEDIUM",
                        ),
                    }
                )

        # Determine the schedule start date.
        if start_date:
            try:
                current_day_date = date.fromisoformat(start_date)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "start_date must use YYYY-MM-DD format"
                ) from exc
        else:
            current_day_date = datetime.now(
                ZoneInfo(Config.TIMEZONE)
            ).date()

        daily_capacity = float(daily_hours)

        if daily_capacity <= 0:
            raise ValueError("daily_hours must be greater than zero")

        if not 0 <= start_hour <= 23:
            raise ValueError("start_hour must be between 0 and 23")

        days_schedule = []
        current_day_sessions = []
        current_day_used = 0.0
        current_time_minutes = start_hour * 60

        for item in work_items:
            remaining_minutes = max(
                0,
                int(item["duration_hours"] * 60),
            )

            while remaining_minutes > 0:
                # Find a slot that avoids fixed events.
                slot_start = PlannerTool._find_available_slot(
                    current_day_date,
                    remaining_minutes,
                    current_time_minutes,
                    start_hour,
                    fixed_events,
                )

                if slot_start is None:
                    window_end = start_hour * 60 + 180
                    candidate = max(
                        current_time_minutes,
                        start_hour * 60,
                    )
                    next_block_start = window_end

                    for event in fixed_events:
                        if event.get("date_str") != (
                            current_day_date.isoformat()
                        ):
                            continue

                        if event["start_minutes"] >= candidate:
                            next_block_start = min(
                                next_block_start,
                                event["start_minutes"],
                            )

                    available_minutes = next_block_start - candidate

                    if available_minutes <= 0:
                        # Save this day before moving forward.
                        if current_day_sessions:
                            days_schedule.append(
                                {
                                    "date": current_day_date.isoformat(),
                                    "day_name": current_day_date.strftime(
                                        "%A"
                                    ),
                                    "formatted_date": (
                                        current_day_date.strftime(
                                            "%b %d, %Y"
                                        )
                                    ),
                                    "total_hours": round(
                                        current_day_used,
                                        1,
                                    ),
                                    "sessions": current_day_sessions,
                                }
                            )

                        current_day_date += timedelta(days=1)
                        current_day_sessions = []
                        current_day_used = 0.0
                        current_time_minutes = start_hour * 60
                        continue

                    chunk_minutes = min(
                        remaining_minutes,
                        available_minutes,
                    )
                    slot_start = candidate

                else:
                    chunk_minutes = remaining_minutes

                    remaining_capacity_minutes = int(
                        (daily_capacity - current_day_used) * 60
                    )

                    if remaining_capacity_minutes <= 0:
                        if current_day_sessions:
                            days_schedule.append(
                                {
                                    "date": current_day_date.isoformat(),
                                    "day_name": current_day_date.strftime(
                                        "%A"
                                    ),
                                    "formatted_date": (
                                        current_day_date.strftime(
                                            "%b %d, %Y"
                                        )
                                    ),
                                    "total_hours": round(
                                        current_day_used,
                                        1,
                                    ),
                                    "sessions": current_day_sessions,
                                }
                            )

                        current_day_date += timedelta(days=1)
                        current_day_sessions = []
                        current_day_used = 0.0
                        current_time_minutes = start_hour * 60
                        continue

                    chunk_minutes = min(
                        chunk_minutes,
                        remaining_capacity_minutes,
                    )

                if chunk_minutes <= 0:
                    break

                # Create the scheduled session.
                session_start = slot_start
                session_end = session_start + chunk_minutes

                session = {
                    "task_id": item["task_id"],
                    "subtask_id": item.get("subtask_id"),
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
                        2,
                    ),
                    "priority": item["priority"],
                    "deadline": item.get("deadline"),
                    "event_type": "TASK_STUDY",
                    "blocks_schedule": False,
                    "is_actionable": True,
                }

                current_day_sessions.append(session)
                current_day_used += chunk_minutes / 60
                current_time_minutes = session_end
                remaining_minutes -= chunk_minutes

                # Move forward when daily capacity has been reached.
                if (
                    remaining_minutes > 0
                    and current_day_used >= daily_capacity
                ):
                    if current_day_sessions:
                        days_schedule.append(
                            {
                                "date": current_day_date.isoformat(),
                                "day_name": current_day_date.strftime(
                                    "%A"
                                ),
                                "formatted_date": (
                                    current_day_date.strftime(
                                        "%b %d, %Y"
                                    )
                                ),
                                "total_hours": round(
                                    current_day_used,
                                    1,
                                ),
                                "sessions": current_day_sessions,
                            }
                        )

                    current_day_date += timedelta(days=1)
                    current_day_sessions = []
                    current_day_used = 0.0
                    current_time_minutes = start_hour * 60

        # Save the final day.
        if current_day_sessions:
            days_schedule.append(
                {
                    "date": current_day_date.isoformat(),
                    "day_name": current_day_date.strftime("%A"),
                    "formatted_date": current_day_date.strftime(
                        "%b %d, %Y"
                    ),
                    "total_hours": round(current_day_used, 1),
                    "sessions": current_day_sessions,
                }
            )

        # Add fixed events to their calendar days.
        for event in fixed_sessions:
            event_date = event.get("date_str")

            if not event_date:
                continue

            try:
                event_date_obj = date.fromisoformat(event_date)
            except (ValueError, TypeError):
                continue

            existing_day = next(
                (
                    day
                    for day in days_schedule
                    if day["date"] == event_date
                ),
                None,
            )

            if existing_day is None:
                existing_day = {
                    "date": event_date,
                    "day_name": event_date_obj.strftime("%A"),
                    "formatted_date": event_date_obj.strftime(
                        "%b %d, %Y"
                    ),
                    "total_hours": 0.0,
                    "sessions": [],
                }
                days_schedule.append(existing_day)

            existing_day["sessions"].append(event)

        # Sort days and sessions chronologically.
        days_schedule.sort(key=lambda day: day["date"])

        for day in days_schedule:
            day["sessions"].sort(
                key=lambda session: session.get(
                    "start_time",
                    "00:00",
                )
            )

        # Calculate scheduled task hours.
        total_hours = sum(
            day["total_hours"]
            for day in days_schedule
        )

        return {
            "days": days_schedule,
            "total_hours": round(total_hours, 1),
            "daily_capacity": daily_capacity,
            "task_count": len(pending_tasks),
            "items_scheduled": len(work_items),
            "fixed_event_count": len(fixed_sessions),
            "fixed_events": fixed_sessions,
            "generated_at": datetime.now(
                ZoneInfo(Config.TIMEZONE)
            ).isoformat(),
        }

    # ---------------------------------------------------------
    # REPLANNING
    # ---------------------------------------------------------

    @staticmethod
    def replan(
        conflicts=None,
        daily_hours=3.0,
        fixed_events=None,
    ):
        """Generate an updated plan after conflicts or missed sessions."""

        tasks = TaskTool.list_tasks()

        new_plan = PlannerTool.generate_plan(
            tasks=tasks,
            daily_hours=daily_hours,
            start_date=datetime.now(
                ZoneInfo(Config.TIMEZONE)
            ).date().isoformat(),
            fixed_events=fixed_events or [],
        )

        return new_plan