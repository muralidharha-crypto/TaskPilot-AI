import json
from datetime import datetime, date, timedelta
from app.models.database import Database
from app.tools.task_tool import TaskTool
from app.tools.scheduler_tool import SchedulerTool

class PlannerTool:
    @staticmethod
    def calculate_priority_score(deadline_str, duration_hours, importance="MEDIUM", dependency_count=0):
        """
        Calculates an explainable priority score between 0 and 100 based on:
        - Deadline Urgency (40%)
        - Task Importance (30%)
        - Estimated Effort (20%)
        - Dependency Impact (10%)
        """
        today = date.today()
        urgency_score = 50.0 # Default moderate
        days_until_deadline = None

        if deadline_str:
            try:
                # Handle YYYY-MM-DD
                d_date = datetime.strptime(deadline_str.split("T")[0], "%Y-%m-%d").date()
                days_until_deadline = (d_date - today).days
                if days_until_deadline <= 0:
                    urgency_score = 100.0 # Due today or overdue
                elif days_until_deadline == 1:
                    urgency_score = 95.0  # Due tomorrow
                elif days_until_deadline <= 3:
                    urgency_score = 80.0
                elif days_until_deadline <= 7:
                    urgency_score = 60.0
                else:
                    urgency_score = 30.0
            except Exception:
                urgency_score = 50.0

        # Importance (0 - 100)
        imp_map = {"CRITICAL": 100.0, "HIGH": 85.0, "MEDIUM": 60.0, "LOW": 30.0}
        importance_score = imp_map.get(importance.upper(), 60.0)

        # Effort (0 - 100): normalized where 1-4 hours is 50-80, >5h is 90
        effort = float(duration_hours or 1.0)
        effort_score = min(100.0, max(20.0, effort * 20.0))

        # Dependency Impact (0 - 100)
        dep_score = min(100.0, dependency_count * 25.0)

        total_score = round(
            (urgency_score * 0.40) + 
            (importance_score * 0.30) + 
            (effort_score * 0.20) + 
            (dep_score * 0.10),
            1
        )

        # Categorize label
        if total_score >= 75:
            priority_label = "HIGH"
        elif total_score >= 50:
            priority_label = "MEDIUM"
        else:
            priority_label = "LOW"

        # Explainability text
        reasons = []
        if days_until_deadline is not None:
            if days_until_deadline <= 1:
                reasons.append(f"due in {days_until_deadline} day(s) (urgent deadline)")
            else:
                reasons.append(f"due in {days_until_deadline} days")
        reasons.append(f"{importance.upper()} importance")
        reasons.append(f"{effort}h estimated effort")
        if dependency_count > 0:
            reasons.append(f"{dependency_count} dependent tasks")

        explanation = f"Assigned {priority_label} (Score: {total_score}/100) because task is {', '.join(reasons)}."

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

    @staticmethod
    def prioritize_tasks(tasks_list=None):
        """Ranks tasks based on calculated priority scores."""
        if tasks_list is None:
            tasks_list = TaskTool.list_tasks(status="PENDING")

        scored_tasks = []
        for t in tasks_list:
            deps = t.get("dependencies", [])
            dep_count = len(deps) if isinstance(deps, list) else 0
            score_data = PlannerTool.calculate_priority_score(
                deadline_str=t.get("deadline"),
                duration_hours=t.get("duration_hours", 1.0),
                importance=t.get("priority", "MEDIUM"),
                dependency_count=dep_count
            )
            t_copy = dict(t)
            t_copy["calculated_score"] = score_data["score"]
            t_copy["calculated_priority"] = score_data["label"]
            t_copy["priority_explanation"] = score_data["explanation"]
            scored_tasks.append(t_copy)

        # Sort descending by priority score
        scored_tasks.sort(key=lambda x: x["calculated_score"], reverse=True)
        return scored_tasks

    @staticmethod
    def generate_plan(tasks=None, daily_hours=3.0, start_date=None, start_hour=18):
        """
        Generates a chronological multi-day study/execution schedule.
        Allocates tasks and subtasks into evening slots (e.g., 6:00 PM to 9:00 PM).
        """
        if tasks is None:
            tasks = TaskTool.list_tasks()

        pending_tasks = [t for t in tasks if t.get("status", "PENDING") in ("PENDING", "IN_PROGRESS")]
        if not pending_tasks:
            return {"days": [], "total_hours": 0.0, "message": "No pending tasks to schedule"}

        # Prioritize tasks first
        prioritized = PlannerTool.prioritize_tasks(pending_tasks)

        # Build execution items from tasks or their subtasks
        work_items = []
        for t in prioritized:
            subtasks = t.get("subtasks", [])
            if subtasks and len(subtasks) > 0:
                for st in subtasks:
                    if isinstance(st, str):
                        st_title = st
                        st_dur = 0.5
                        st_id = None
                        st_status = "PENDING"
                    else:
                        st_title = st.get("title", "")
                        st_dur = float(st.get("duration_hours", 0.5))
                        st_id = st.get("id")
                        st_status = st.get("status", "PENDING")

                    if st_status != "COMPLETED":
                        work_items.append({
                            "task_id": t.get("id"),
                            "task_title": t.get("title"),
                            "subtask_id": st_id,
                            "item_title": f"{t.get('title')}: {st_title}",
                            "duration_hours": st_dur,
                            "deadline": t.get("deadline"),
                            "priority": t.get("calculated_priority", "MEDIUM")
                        })
            else:
                work_items.append({
                    "task_id": t.get("id"),
                    "task_title": t.get("title"),
                    "subtask_id": None,
                    "item_title": t.get("title"),
                    "duration_hours": float(t.get("duration_hours", 1.0)),
                    "deadline": t.get("deadline"),
                    "priority": t.get("calculated_priority", "MEDIUM")
                })

        # Schedule into days
        cur_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date.today()
        daily_capacity = float(daily_hours)
        days_schedule = []
        
        current_day_date = cur_date
        current_day_sessions = []
        current_day_used = 0.0
        current_time_minutes = start_hour * 60 # 18:00 = 1080 min

        for item in work_items:
            dur = item["duration_hours"]
            if current_day_used + dur > daily_capacity and current_day_sessions:
                # Wrap to next day
                days_schedule.append({
                    "date": current_day_date.isoformat(),
                    "day_name": current_day_date.strftime("%A"),
                    "formatted_date": current_day_date.strftime("%b %d, %Y"),
                    "total_hours": round(current_day_used, 1),
                    "sessions": current_day_sessions
                })
                current_day_date += timedelta(days=1)
                current_day_sessions = []
                current_day_used = 0.0
                current_time_minutes = start_hour * 60

            # Calculate session start & end string
            start_h = current_time_minutes // 60
            start_m = current_time_minutes % 60
            end_minutes = current_time_minutes + int(dur * 60)
            end_h = end_minutes // 60
            end_m = end_minutes % 60

            start_str = f"{start_h:02d}:{start_m:02d}"
            end_str = f"{end_h:02d}:{end_m:02d}"

            session = {
                "task_id": item["task_id"],
                "subtask_id": item.get("subtask_id"),
                "title": item["item_title"],
                "date_str": current_day_date.isoformat(),
                "start_time": start_str,
                "end_time": end_str,
                "duration_hours": dur,
                "priority": item["priority"],
                "deadline": item.get("deadline")
            }
            current_day_sessions.append(session)
            current_day_used += dur
            current_time_minutes = end_minutes

        if current_day_sessions:
            days_schedule.append({
                "date": current_day_date.isoformat(),
                "day_name": current_day_date.strftime("%A"),
                "formatted_date": current_day_date.strftime("%b %d, %Y"),
                "total_hours": round(current_day_used, 1),
                "sessions": current_day_sessions
            })

        total_hours = sum(d["total_hours"] for d in days_schedule)
        return {
            "days": days_schedule,
            "total_hours": round(total_hours, 1),
            "daily_capacity": daily_capacity,
            "task_count": len(pending_tasks),
            "items_scheduled": len(work_items),
            "generated_at": datetime.now().isoformat()
        }

    @staticmethod
    def replan(conflicts=None, daily_hours=3.0):
        """Generates an updated plan after conflicts/missed sessions are detected."""
        # Grab current tasks
        tasks = TaskTool.list_tasks()
        new_plan = PlannerTool.generate_plan(tasks=tasks, daily_hours=daily_hours, start_date=date.today().isoformat())
        return new_plan
