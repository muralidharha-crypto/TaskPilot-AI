import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Config
from app.models.database import Database
from app.tools.tool_registry import registry


class ToolExecutor:
    @staticmethod
    def execute_approval(approval_id):
        """
        Executes all proposed actions in an approved plan using the allowlisted tool registry.
        Records an exact audit trail of execution results.
        """
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            approval_row = cursor.fetchone()
            if not approval_row:
                raise ValueError(f"Approval record {approval_id} not found")

            approval = dict(approval_row)
            if approval["status"] == "APPROVED":
                return {
                    "already_executed": True,
                    "approval_id": approval_id,
                    "message": "This action plan has already been executed."
                }

            run_id = approval["run_id"]
            actions = json.loads(approval["proposed_actions_json"])

            user_action_at = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()
            execution_start_at = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()

            # Mark approval status
            cursor.execute(
                "UPDATE approvals SET status = 'APPROVED', user_action_at = ? WHERE id = ?",
                (user_action_at, approval_id)
            )
            cursor.execute(
                "UPDATE agent_runs SET status = 'EXECUTING', updated_at = ? WHERE id = ?",
                (execution_start_at, run_id)
            )
            conn.commit()

            results = []
            created_task_ids = {}

            for act in actions:
                tool_name = act["tool_name"]
                func_name = act["function_name"]
                args = act["arguments"].copy()

                # If this is a scheduler action for a task, wire task_id if known
                if tool_name == "scheduler" and "task_id" not in args:
                    # Match title prefix
                    for title_prefix, tid in created_task_ids.items():
                        if act["arguments"]["title"].startswith(title_prefix):
                            args["task_id"] = tid
                            break

                exec_res = registry.execute(tool_name, func_name, args, run_id=run_id, db_conn=conn)
                
                # If we just created a task, keep its ID
                if tool_name == "task_manager" and func_name == "create_task" and exec_res.get("success"):
                    created_data = exec_res.get("data", {})
                    created_task_ids[created_data.get("title")] = created_data.get("id")

                results.append({
                    "action_id": act.get("action_id"),
                    "description": act.get("description"),
                    "tool": tool_name,
                    "function": func_name,
                    "success": exec_res.get("success", False),
                    "output": exec_res.get("data") if exec_res.get("success") else exec_res.get("error")
                })

            executed_at = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()

            # Finalize approval and agent run
            cursor.execute(
                "UPDATE approvals SET executed_at = ? WHERE id = ?",
                (executed_at, approval_id)
            )

            execution_summary = {
                "total_actions": len(actions),
                "successful_actions": sum(1 for r in results if r["success"]),
                "failed_actions": sum(1 for r in results if not r["success"]),
                "user_approved_at": user_action_at,
                "agent_executed_at": executed_at,
                "details": results
            }

            cursor.execute(
                """
                UPDATE agent_runs 
                SET status = 'COMPLETED',
                    execution_summary_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(execution_summary), executed_at, run_id)
            )
            conn.commit()

            return {
                "approval_id": approval_id,
                "run_id": run_id,
                "status": "COMPLETED",
                "user_approved_at": user_action_at,
                "agent_executed_at": executed_at,
                "summary": execution_summary,
                "actions": results
            }
        finally:
            conn.close()
