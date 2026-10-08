from datetime import datetime
from app.models.database import Database

class SchedulerTool:
    @staticmethod
    def create_schedule(title, date_str, start_time, end_time, duration_hours=1.0, task_id=None, notes=None):
        """Creates a scheduled study or work block."""
        if not title or not date_str or not start_time or not end_time:
            raise ValueError("Title, date_str, start_time, and end_time are required")

        now = datetime.now().isoformat()
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO schedules (task_id, title, date_str, start_time, end_time, 
                                       duration_hours, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED', ?, ?)
                """,
                (task_id, title.strip(), date_str, start_time, end_time, float(duration_hours), notes, now)
            )
            sched_id = cursor.lastrowid
            conn.commit()
            return {
                "id": sched_id,
                "task_id": task_id,
                "title": title.strip(),
                "date_str": date_str,
                "start_time": start_time,
                "end_time": end_time,
                "duration_hours": float(duration_hours),
                "status": "SCHEDULED",
                "notes": notes,
                "created_at": now
            }
        finally:
            conn.close()

    @staticmethod
    def update_schedule(schedule_id, title=None, date_str=None, start_time=None, 
                        end_time=None, duration_hours=None, status=None, notes=None):
        """Updates a schedule item."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Schedule with ID {schedule_id} not found")

            updates = []
            params = []
            if title is not None:
                updates.append("title = ?")
                params.append(title.strip())
            if date_str is not None:
                updates.append("date_str = ?")
                params.append(date_str)
            if start_time is not None:
                updates.append("start_time = ?")
                params.append(start_time)
            if end_time is not None:
                updates.append("end_time = ?")
                params.append(end_time)
            if duration_hours is not None:
                updates.append("duration_hours = ?")
                params.append(float(duration_hours))
            if status is not None:
                updates.append("status = ?")
                params.append(status.upper())
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)

            params.append(schedule_id)
            cursor.execute(f"UPDATE schedules SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

            cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    @staticmethod
    def remove_schedule(schedule_id):
        """Removes a schedule item."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            return {"schedule_id": schedule_id, "deleted": True}
        finally:
            conn.close()

    @staticmethod
    def get_schedule(date_str=None, task_id=None):
        """Returns schedule items ordered chronologically."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT s.*, t.priority, t.deadline FROM schedules s LEFT JOIN tasks t ON s.task_id = t.id WHERE 1=1"
            params = []
            if date_str:
                query += " AND s.date_str = ?"
                params.append(date_str)
            if task_id:
                query += " AND s.task_id = ?"
                params.append(task_id)

            query += " ORDER BY s.date_str ASC, s.start_time ASC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def mark_missed(schedule_id):
        """Marks a schedule as missed to flag for replanning."""
        return SchedulerTool.update_schedule(schedule_id, status="MISSED")

    @staticmethod
    def clear_all_schedules():
        """Clears all schedules (used when replanning from scratch)."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules")
            conn.commit()
            return {"cleared": True}
        finally:
            conn.close()
