import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Config
from app.models.database import Database
from app.tools.planner_tool import PlannerTool
from app.tools.task_tool import TaskTool


class ReplannerService:
    @staticmethod
    def _today():
        """Return today's date in the configured application timezone."""
        return datetime.now(ZoneInfo(Config.TIMEZONE)).date()

    @staticmethod
    def simulate_delay_and_replan(
        reason="I couldn't study today",
        target_date=None,
        daily_hours=3.0,
    ):
        """
        Simulate a missed schedule, detect conflicts, and generate
        a new adapted plan.

        Workflow:
        Original Plan -> Conflict Detected -> Replanning
        -> New Plan -> Approval -> Execute
        """
        if not target_date:
            target_date = ReplannerService._today().isoformat()

        # Validate the date format before changing the schedule.
        try:
            target_date_obj = date.fromisoformat(target_date)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "target_date must be a valid date in YYYY-MM-DD format."
            ) from exc

        # Ensure that the date is in the expected ISO format.
        if target_date_obj.isoformat() != target_date:
            raise ValueError(
                "target_date must use YYYY-MM-DD format."
            )

        conn = Database.get_connection()

        try:
            cursor = conn.cursor()

            # 1. Fetch current schedules for the target date.
            cursor.execute(
                """
                SELECT *
                FROM schedules
                WHERE date_str = ?
                  AND status != 'COMPLETED'
                """,
                (target_date,),
            )

            impacted_rows = cursor.fetchall()
            missed_sessions = [dict(row) for row in impacted_rows]

            # Mark uncompleted sessions as MISSED.
            cursor.execute(
                """
                UPDATE schedules
                SET status = 'MISSED'
                WHERE date_str = ?
                  AND status != 'COMPLETED'
                """,
                (target_date,),
            )

            conn.commit()

            # 2. Capture the old plan state.
            cursor.execute(
                """
                SELECT *
                FROM schedules
                ORDER BY date_str ASC, start_time ASC
                """
            )

            all_schedules_old = [
                dict(row) for row in cursor.fetchall()
            ]

            old_plan_summary = {
                "date_affected": target_date,
                "missed_session_count": len(missed_sessions),
                "missed_hours": sum(
                    session.get("duration_hours", 1.0)
                    for session in missed_sessions
                ),
                "all_schedules": all_schedules_old,
            }

            # 3. Detect the scheduling conflict.
            conflict_desc = (
                f"Schedule disruption detected on {target_date}: "
                f"{len(missed_sessions)} session(s) "
                f"({old_plan_summary['missed_hours']}h) were missed. "
                "Your original schedule is no longer feasible."
            )

            # 4. Generate an adapted plan starting tomorrow.
            tomorrow = (
                target_date_obj + timedelta(days=1)
            ).isoformat()

            # Fetch uncompleted tasks.
            pending_tasks = TaskTool.list_tasks(status="PENDING")

            new_plan = PlannerTool.generate_plan(
                tasks=pending_tasks,
                daily_hours=daily_hours,
                start_date=tomorrow,
            )

            # 5. Create a new agent run.
            # Store audit timestamps in timezone-aware UTC.
            now = datetime.now(UTC).isoformat()

            cursor.execute(
                """
                INSERT INTO agent_runs (
                    goal,
                    intent,
                    status,
                    timeline_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?,
                    'reschedule_replan',
                    'REPLANNING',
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    f"Replan schedule due to: {reason}",
                    json.dumps(
                        [
                            {
                                "step": "CONFLICT_DETECTED",
                                "time": now,
                                "details": conflict_desc,
                            },
                            {
                                "step": "REPLANNING",
                                "time": now,
                                "details": (
                                    "Recalculated available capacity "
                                    "and rescheduled remaining sessions"
                                ),
                            },
                        ]
                    ),
                    now,
                    now,
                ),
            )

            replan_run_id = cursor.lastrowid

            # 6. Record the conflict in the database.
            cursor.execute(
                """
                INSERT INTO conflicts (
                    run_id,
                    description,
                    conflict_type,
                    old_plan_json,
                    new_plan_json,
                    resolved,
                    created_at
                )
                VALUES (?, ?, 'MISSED_SESSION', ?, ?, 0, ?)
                """,
                (
                    replan_run_id,
                    conflict_desc,
                    json.dumps(old_plan_summary),
                    json.dumps(new_plan),
                    now,
                ),
            )

            conflict_id = cursor.lastrowid
            conn.commit()

            # 7. Formulate proposed replanning actions.
            # Clearing existing schedules requires approval.
            replan_actions = [
                {
                    "action_id": "clear_uncompleted_future",
                    "category": "SCHEDULE_CLEANUP",
                    "tool_name": "scheduler",
                    "function_name": "clear_all_schedules",
                    "description": (
                        "Clear stale schedule slots to prevent "
                        "overlapping sessions"
                    ),
                    "requires_approval": True,
                    "arguments": {},
                }
            ]

            # Add proposed schedule-creation actions.
            for day in new_plan.get("days", []):
                for session in day.get("sessions", []):
                    replan_actions.append(
                        {
                            "action_id": (
                                f"replan_sched_{session['date_str']}_"
                                f"{session['start_time'].replace(':', '')}"
                            ),
                            "category": "SCHEDULE_REALLOCATION",
                            "tool_name": "scheduler",
                            "function_name": "create_schedule",
                            "description": (
                                f"Reschedule '{session['title']}' "
                                f"on {session['date_str']} "
                                f"({session['start_time']} - "
                                f"{session['end_time']})"
                            ),
                            "requires_approval": True,
                            "arguments": {
                                "title": session["title"],
                                "date_str": session["date_str"],
                                "start_time": session["start_time"],
                                "end_time": session["end_time"],
                                "duration_hours": (
                                    session["duration_hours"]
                                ),
                                "notes": (
                                    f"Priority: {session['priority']} "
                                    "| Rescheduled after delay"
                                ),
                            },
                        }
                    )

            # 8. Create the approval record.
            cursor.execute(
                """
                INSERT INTO approvals (
                    run_id,
                    proposed_actions_json,
                    status,
                    created_at
                )
                VALUES (?, ?, 'PENDING', ?)
                """,
                (
                    replan_run_id,
                    json.dumps(replan_actions),
                    now,
                ),
            )

            approval_id = cursor.lastrowid

            # Update the agent run to await human approval.
            cursor.execute(
                """
                UPDATE agent_runs
                SET status = 'WAITING_APPROVAL',
                    proposed_actions_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(replan_actions),
                    now,
                    replan_run_id,
                ),
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
                "message": (
                    "Conflict detected and resolved. Awaiting human "
                    "approval to apply the updated schedule."
                ),
            }

        finally:
            conn.close()