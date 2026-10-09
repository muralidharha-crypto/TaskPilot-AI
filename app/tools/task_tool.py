import json
from datetime import datetime
from app.models.database import Database

class TaskTool:
    @staticmethod
    def create_task(title, description="", priority="MEDIUM", priority_score=0.0, 
                    deadline=None, duration_hours=1.0, dependencies=None, subtasks=None):
        """Creates a new task and optional subtasks."""
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty")

        now = datetime.now().isoformat()
        deps_json = json.dumps(dependencies or [])
        subtasks = subtasks or []

        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            clean_title = title.strip()
            # Check if active task with same title already exists
            cursor.execute("SELECT id FROM tasks WHERE LOWER(title) = LOWER(?) AND status != 'COMPLETED'", (clean_title,))
            existing = cursor.fetchone()
            if existing:
                task_id = existing["id"]
                cursor.execute(
                    """
                    UPDATE tasks 
                    SET description = ?, priority = ?, priority_score = ?, deadline = ?,
                        duration_hours = ?, dependencies = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (description, priority.upper(), float(priority_score), deadline, float(duration_hours), deps_json, now, task_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO tasks (title, description, priority, priority_score, deadline, 
                                       duration_hours, status, dependencies, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
                    """,
                    (clean_title, description, priority.upper(), float(priority_score), 
                     deadline, float(duration_hours), deps_json, now, now)
                )
                task_id = cursor.lastrowid

            created_subtasks = []
            for idx, st in enumerate(subtasks):
                st_title = st if isinstance(st, str) else st.get("title", "")
                st_dur = 0.5 if isinstance(st, str) else st.get("duration_hours", 0.5)
                if st_title:
                    # Avoid duplicate subtask under same task
                    cursor.execute(
                        "SELECT id FROM subtasks WHERE task_id = ? AND LOWER(title) = LOWER(?)",
                        (task_id, st_title.strip())
                    )
                    st_exists = cursor.fetchone()
                    if not st_exists:
                        cursor.execute(
                            """
                            INSERT INTO subtasks (task_id, title, status, duration_hours, order_idx, created_at)
                            VALUES (?, ?, 'PENDING', ?, ?, ?)
                            """,
                            (task_id, st_title.strip(), float(st_dur), idx, now)
                        )
                        created_subtasks.append({
                            "id": cursor.lastrowid,
                            "title": st_title.strip(),
                            "status": "PENDING",
                            "duration_hours": st_dur
                        })
                    else:
                        created_subtasks.append({
                            "id": st_exists["id"],
                            "title": st_title.strip(),
                            "status": "PENDING",
                            "duration_hours": st_dur
                        })

            conn.commit()
            return {
                "id": task_id,
                "title": title.strip(),
                "description": description,
                "priority": priority.upper(),
                "priority_score": float(priority_score),
                "deadline": deadline,
                "duration_hours": float(duration_hours),
                "status": "PENDING",
                "dependencies": dependencies or [],
                "subtasks": created_subtasks,
                "created_at": now
            }
        finally:
            conn.close()

    @staticmethod
    def update_task(task_id, title=None, description=None, priority=None, 
                    priority_score=None, deadline=None, duration_hours=None, status=None):
        """Updates an existing task."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Task with ID {task_id} not found")

            updates = []
            params = []
            now = datetime.now().isoformat()

            if title is not None:
                updates.append("title = ?")
                params.append(title.strip())
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if priority is not None:
                updates.append("priority = ?")
                params.append(priority.upper())
            if priority_score is not None:
                updates.append("priority_score = ?")
                params.append(float(priority_score))
            if deadline is not None:
                updates.append("deadline = ?")
                params.append(deadline)
            if duration_hours is not None:
                updates.append("duration_hours = ?")
                params.append(float(duration_hours))
            if status is not None:
                updates.append("status = ?")
                params.append(status.upper())

            updates.append("updated_at = ?")
            params.append(now)
            params.append(task_id)

            sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            return TaskTool.get_task(task_id)
        finally:
            conn.close()

    @staticmethod
    def complete_task(task_id):
        """Marks a task and all its subtasks as completed."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("UPDATE tasks SET status = 'COMPLETED', updated_at = ? WHERE id = ?", (now, task_id))
            cursor.execute("UPDATE subtasks SET status = 'COMPLETED' WHERE task_id = ?", (task_id,))
            cursor.execute("UPDATE schedules SET status = 'COMPLETED' WHERE task_id = ?", (task_id,))
            conn.commit()
            return {"task_id": task_id, "status": "COMPLETED", "completed_at": now}
        finally:
            conn.close()

    @staticmethod
    def delete_task(task_id):
        """Deletes a task and cascading subtasks."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return {"task_id": task_id, "deleted": True}
        finally:
            conn.close()

    @staticmethod
    def get_task(task_id):
        """Fetches a single task with its subtasks."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            task = dict(row)
            task["dependencies"] = json.loads(task["dependencies"] or "[]")
            
            cursor.execute("SELECT * FROM subtasks WHERE task_id = ? ORDER BY order_idx ASC", (task_id,))
            sub_rows = cursor.fetchall()
            task["subtasks"] = [dict(sr) for sr in sub_rows]
            return task
        finally:
            conn.close()

    @staticmethod
    def list_tasks(status=None):
        """Lists all tasks with subtasks."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY priority_score DESC, deadline ASC", (status.upper(),))
            else:
                cursor.execute("SELECT * FROM tasks ORDER BY priority_score DESC, deadline ASC")
            rows = cursor.fetchall()

            tasks = []
            for r in rows:
                t = dict(r)
                t["dependencies"] = json.loads(t["dependencies"] or "[]")
                cursor.execute("SELECT * FROM subtasks WHERE task_id = ? ORDER BY order_idx ASC", (t["id"],))
                t["subtasks"] = [dict(sr) for sr in cursor.fetchall()]
                tasks.append(t)
            return tasks
        finally:
            conn.close()
