import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Config
from app.models.database import Database


class ApprovalManager:
    @staticmethod
    def create_approval_request(run_id, ranked_tasks, plan_data):
        """
        Formulates atomic proposed actions requiring human sign-off.
        Stores them in the database for human review.
        """
        proposed_actions = []

        # 1. Task creation actions
        for t in ranked_tasks:
            proposed_actions.append({
                "action_id": f"task_{t.get('title', '').replace(' ', '_').lower()}",
                "category": "TASK_CREATION",
                "tool_name": "task_manager",
                "function_name": "create_task",
                "description": f"Create '{t['title']}' ({t['priority']} Priority, {t['duration_hours']}h) with {len(t.get('subtasks', []))} subtasks",
                "requires_approval": True,
                "arguments": {
                    "title": t["title"],
                    "description": f"Auto-planned task for {t.get('subject', 'General')}. Priority: {t['priority']}",
                    "priority": t["priority"],
                    "priority_score": t.get("priority_score", 50.0),
                    "deadline": t.get("deadline"),
                    "duration_hours": t.get("duration_hours", 1.0),
                    "subtasks": t.get("subtasks", [])
                }
            })

        # 2. Scheduling session actions
        for day in plan_data.get("days", []):
            for sess in day.get("sessions", []):
                proposed_actions.append({
                    "action_id": f"sched_{sess['date_str']}_{sess['start_time'].replace(':', '')}",
                    "category": "SCHEDULE_ALLOCATION",
                    "tool_name": "scheduler",
                    "function_name": "create_schedule",
                    "description": f"Schedule '{sess['title']}' on {sess['date_str']} ({sess['start_time']} - {sess['end_time']})",
                    "requires_approval": True,
                    "arguments": {
                        "title": sess["title"],
                        "date_str": sess["date_str"],
                        "start_time": sess["start_time"],
                        "end_time": sess["end_time"],
                        "duration_hours": sess["duration_hours"],
                        "notes": f"Priority: {sess['priority']} | Due: {sess.get('deadline', 'N/A')}"
                    }
                })

        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()
            cursor.execute(
                """
                INSERT INTO approvals (run_id, proposed_actions_json, status, created_at)
                VALUES (?, ?, 'PENDING', ?)
                """,
                (run_id, json.dumps(proposed_actions), now)
            )
            approval_id = cursor.lastrowid

            cursor.execute(
                """
                UPDATE agent_runs 
                SET status = 'WAITING_APPROVAL', 
                    proposed_actions_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(proposed_actions), now, run_id)
            )
            conn.commit()

            return {
                "approval_id": approval_id,
                "run_id": run_id,
                "status": "PENDING",
                "total_actions": len(proposed_actions),
                "proposed_actions": proposed_actions,
                "created_at": now
            }
        finally:
            conn.close()

    @staticmethod
    def get_approval(approval_id):
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["proposed_actions"] = json.loads(res["proposed_actions_json"])
            return res
        finally:
            conn.close()

    @staticmethod
    def reject(approval_id, comments="Rejected by user"):
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()
            cursor.execute(
                """
                UPDATE approvals 
                SET status = 'REJECTED', user_action_at = ?, comments = ?
                WHERE id = ?
                """,
                (now, comments, approval_id)
            )
            cursor.execute("SELECT run_id FROM approvals WHERE id = ?", (approval_id,))
            r = cursor.fetchone()
            if r:
                run_id = r["run_id"]
                cursor.execute(
                    "UPDATE agent_runs SET status = 'CANCELLED', updated_at = ? WHERE id = ?",
                    (now, run_id)
                )
            conn.commit()
            return {"approval_id": approval_id, "status": "REJECTED", "comments": comments}
        finally:
            conn.close()
