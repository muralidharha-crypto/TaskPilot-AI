import json
from datetime import datetime, date, timedelta
from app.models.database import Database
from app.tools.task_tool import TaskTool
from app.tools.scheduler_tool import SchedulerTool
from app.tools.planner_tool import PlannerTool
from app.tools.monitor_tool import MonitorTool
from app.services.approval_manager import ApprovalManager

class ReplannerService:
    @staticmethod
    def simulate_delay_and_replan(reason="I couldn't study today", target_date=None, daily_hours=3.0):
        """
        Simulates a missed schedule, detects the conflict, and generates a new adapted plan.
        Shows the crucial hackathon flow:
        Original Plan -> Conflict Detected -> Replanning -> New Plan -> Approval -> Execute
        """
        if not target_date:
            target_date = date.today().isoformat()

        conn = Database.get_connection()
        try:
            cursor = conn.cursor()

            # 1. Fetch current schedules for the target date
            cursor.execute("SELECT * FROM schedules WHERE date_str = ? AND status != 'COMPLETED'", (target_date,))
            impacted_rows = cursor.fetchall()
            missed_sessions = [dict(r) for r in impacted_rows]

            # Mark them as MISSED
            cursor.execute("UPDATE schedules SET status = 'MISSED' WHERE date_str = ? AND status != 'COMPLETED'", (target_date,))
            conn.commit()

            # 2. Capture old plan state
            cursor.execute("SELECT * FROM schedules ORDER BY date_str ASC, start_time ASC")
            all_schedules_old = [dict(r) for r in cursor.fetchall()]

            old_plan_summary = {
                "date_affected": target_date,
                "missed_session_count": len(missed_sessions),
                "missed_hours": sum(s.get("duration_hours", 1.0) for s in missed_sessions),
                "all_schedules": all_schedules_old
            }

            # 3. Detect conflict
            conflict_desc = (
                f"Schedule disruption detected on {target_date}: {len(missed_sessions)} session(s) "
                f"({old_plan_summary['missed_hours']}h) were missed. "
                "Your original schedule is no longer feasible."
            )

            # 4. Generate New Adapted Plan starting from tomorrow
            tomorrow = (datetime.strptime(target_date, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
            
            # Fetch uncompleted tasks
            pending_tasks = TaskTool.list_tasks(status="PENDING")
            new_plan = PlannerTool.generate_plan(
                tasks=pending_tasks,
                daily_hours=daily_hours,
                start_date=tomorrow
            )

            # 5. Create new Agent Run for the replan
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO agent_runs (goal, intent, status, timeline_json, created_at, updated_at)
                VALUES (?, 'reschedule_replan', 'REPLANNING', ?, ?, ?)
                """,
                (
                    f"Replan schedule due to: {reason}",
                    json.dumps([
                        {"step": "CONFLICT_DETECTED", "time": now, "details": conflict_desc},
                        {"step": "REPLANNING", "time": now, "details": "Recalculated available capacity and rescheduled remaining sessions"}
                    ]),
                    now,
                    now
                )
            )
            replan_run_id = cursor.lastrowid

            # 6. Record Conflict in Database
            cursor.execute(
                """
                INSERT INTO conflicts (run_id, description, conflict_type, old_plan_json, new_plan_json, resolved, created_at)
                VALUES (?, ?, 'MISSED_SESSION', ?, ?, 0, ?)
                """,
                (
                    replan_run_id,
                    conflict_desc,
                    json.dumps(old_plan_summary),
                    json.dumps(new_plan),
                    now
                )
            )
            conflict_id = cursor.lastrowid
            conn.commit()

            # 7. Formulate Proposed Replan Actions
            replan_actions = [
                {
                    "action_id": "clear_uncompleted_future",
                    "category": "SCHEDULE_CLEANUP",
                    "tool_name": "scheduler",
                    "function_name": "clear_all_schedules",
                    "description": "Clear stale schedule slots to prevent overlapping sessions",
                    "requires_approval": True,
                    "arguments": {}
                }
            ]

            for day in new_plan.get("days", []):
                for sess in day.get("sessions", []):
                    replan_actions.append({
                        "action_id": f"replan_sched_{sess['date_str']}_{sess['start_time'].replace(':', '')}",
                        "category": "SCHEDULE_REALLOCATION",
                        "tool_name": "scheduler",
                        "function_name": "create_schedule",
                        "description": f"Reschedule '{sess['title']}' on {sess['date_str']} ({sess['start_time']} - {sess['end_time']})",
                        "requires_approval": True,
                        "arguments": {
                            "title": sess["title"],
                            "date_str": sess["date_str"],
                            "start_time": sess["start_time"],
                            "end_time": sess["end_time"],
                            "duration_hours": sess["duration_hours"],
                            "notes": f"Priority: {sess['priority']} | Rescheduled after delay"
                        }
                    })

            # 8. Create Approval Record
            cursor.execute(
                """
                INSERT INTO approvals (run_id, proposed_actions_json, status, created_at)
                VALUES (?, ?, 'PENDING', ?)
                """,
                (replan_run_id, json.dumps(replan_actions), now)
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
                (json.dumps(replan_actions), now, replan_run_id)
            )
            conn.commit()

            return {
                "conflict_id": conflict_id,
                "replan_run_id": replan_run_id,
                "approval_id": approval_id,
                "conflict_detected": True,
                "conflict_description": conflict_desc,
                "reason": reason,
                "old_plan": old_plan_summary,
                "new_plan": new_plan,
                "proposed_actions": replan_actions,
                "message": "Conflict detected and resolved. Awaiting human approval to apply the updated schedule."
            }

        finally:
            conn.close()
