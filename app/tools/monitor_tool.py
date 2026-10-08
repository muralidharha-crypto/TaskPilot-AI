from datetime import datetime, date
from app.models.database import Database
from app.tools.task_tool import TaskTool
from app.tools.scheduler_tool import SchedulerTool

class MonitorTool:
    @staticmethod
    def get_progress():
        """Calculates global progress statistics across tasks and schedules."""
        tasks = TaskTool.list_tasks()
        schedules = SchedulerTool.get_schedule()

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t["status"] == "COMPLETED")
        in_progress_tasks = sum(1 for t in tasks if t["status"] == "IN_PROGRESS")
        pending_tasks = sum(1 for t in tasks if t["status"] == "PENDING")
        overdue_tasks = sum(1 for t in tasks if t["status"] == "OVERDUE")

        total_hours = sum(t.get("duration_hours", 0.0) for t in tasks)
        completed_hours = sum(t.get("duration_hours", 0.0) for t in tasks if t["status"] == "COMPLETED")

        completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0
        scheduled_blocks = len(schedules)
        completed_blocks = sum(1 for s in schedules if s.get("status") == "COMPLETED")
        missed_blocks = sum(1 for s in schedules if s.get("status") == "MISSED")

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "in_progress_tasks": in_progress_tasks,
            "pending_tasks": pending_tasks,
            "overdue_tasks": overdue_tasks,
            "total_hours": round(total_hours, 1),
            "completed_hours": round(completed_hours, 1),
            "completion_rate": completion_rate,
            "scheduled_blocks": scheduled_blocks,
            "completed_blocks": completed_blocks,
            "missed_blocks": missed_blocks
        }

    @staticmethod
    def detect_overdue_tasks():
        """Finds any tasks whose deadline is earlier than today and not yet completed."""
        today = date.today().isoformat()
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks 
                WHERE deadline IS NOT NULL 
                  AND deadline < ? 
                  AND status != 'COMPLETED'
                """,
                (today,)
            )
            rows = cursor.fetchall()
            overdue = []
            for r in rows:
                t = dict(r)
                # Auto update status to OVERDUE in database
                if t["status"] != "OVERDUE":
                    cursor.execute("UPDATE tasks SET status = 'OVERDUE' WHERE id = ?", (t["id"],))
                    t["status"] = "OVERDUE"
                overdue.append(t)
            conn.commit()
            return overdue
        finally:
            conn.close()

    @staticmethod
    def detect_conflict(daily_hours_limit=3.0):
        """
        Detects scheduling conflicts:
        1. Overdue tasks
        2. Missed schedule sessions
        3. Workload capacity overflow on scheduled dates
        """
        conflicts = []
        today = date.today().isoformat()

        # 1. Overdue tasks
        overdue = MonitorTool.detect_overdue_tasks()
        for ot in overdue:
            conflicts.append({
                "type": "OVERDUE_TASK",
                "severity": "HIGH",
                "task_id": ot["id"],
                "title": ot["title"],
                "description": f"Task '{ot['title']}' missed deadline of {ot['deadline']}.",
                "recommended_action": "Reschedule remaining subtasks urgently or adjust deadline."
            })

        # 2. Missed sessions
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM schedules 
                WHERE status = 'MISSED' OR (date_str < ? AND status = 'SCHEDULED')
                """,
                (today,)
            )
            missed_rows = cursor.fetchall()
            for mr in missed_rows:
                s = dict(mr)
                conflicts.append({
                    "type": "MISSED_SESSION",
                    "severity": "HIGH",
                    "schedule_id": s["id"],
                    "title": s["title"],
                    "description": f"Scheduled study session '{s['title']}' on {s['date_str']} was not completed.",
                    "recommended_action": "Reallocate incomplete session hours to next available slot."
                })

            # 3. Daily capacity overloads
            cursor.execute(
                """
                SELECT date_str, SUM(duration_hours) as day_total
                FROM schedules
                WHERE status != 'COMPLETED'
                GROUP BY date_str
                HAVING day_total > ?
                """,
                (float(daily_hours_limit),)
            )
            overloaded_days = cursor.fetchall()
            for od in overloaded_days:
                day_data = dict(od)
                excess = round(day_data["day_total"] - daily_hours_limit, 1)
                conflicts.append({
                    "type": "TIME_OVERLOAD",
                    "severity": "MEDIUM",
                    "date_str": day_data["date_str"],
                    "description": f"Total scheduled work on {day_data['date_str']} ({day_data['day_total']}h) exceeds daily limit of {daily_hours_limit}h by {excess}h.",
                    "recommended_action": f"Redistribute {excess} hours across upcoming days."
                })

        finally:
            conn.close()

        has_conflict = len(conflicts) > 0
        return {
            "has_conflict": has_conflict,
            "conflict_count": len(conflicts),
            "conflicts": conflicts
        }
