import json
from datetime import datetime
from app.models.database import Database
from app.services.intent_analyzer import IntentAnalyzer
from app.services.decomposer import TaskDecomposer
from app.services.priority_engine import PriorityEngine
from app.services.planner import PlannerService
from app.services.approval_manager import ApprovalManager
from app.services.executor import ToolExecutor
from app.services.replanner import ReplannerService
from app.services.research_service import ResearchService

class AgentService:
    @staticmethod
    def process_goal(user_goal):
        """
        Main Agent Execution Entry Point.
        Lifecycle:
        RECEIVED -> ANALYZING -> PLANNING -> WAITING_APPROVAL
        """
        if not user_goal or not user_goal.strip():
            raise ValueError("User goal cannot be empty.")

        now = datetime.now().isoformat()
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()

            # 1. State: RECEIVED
            initial_timeline = [
                {"step": "RECEIVED", "time": now, "details": f"Goal received: '{user_goal}'"}
            ]
            cursor.execute(
                """
                INSERT INTO agent_runs (goal, intent, status, timeline_json, created_at, updated_at)
                VALUES (?, 'unknown', 'RECEIVED', ?, ?, ?)
                """,
                (user_goal.strip(), json.dumps(initial_timeline), now, now)
            )
            run_id = cursor.lastrowid
            conn.commit()

            # 2. State: ANALYZING
            analysis = IntentAnalyzer.analyze(user_goal)
            intent = analysis["intent"]
            cursor.execute("UPDATE agent_runs SET intent = ?, status = 'ANALYZING' WHERE id = ?", (intent, run_id))
            conn.commit()

            # If user wanted research
            if intent == "research_inquiry":
                research_res = ResearchService.run_research(analysis.get("topic", user_goal))
                return {
                    "run_id": run_id,
                    "intent": intent,
                    "status": "COMPLETED",
                    "type": "RESEARCH",
                    "research": research_res
                }

            # If user wanted replan / reschedule directly
            if intent == "reschedule_replan":
                replan_res = ReplannerService.simulate_delay_and_replan(reason=user_goal)
                return {
                    "run_id": replan_res["replan_run_id"],
                    "intent": intent,
                    "status": "WAITING_APPROVAL",
                    "type": "REPLAN",
                    "replan": replan_res
                }

            # Standard Academic / Task Planning Flow
            detected_tasks = analysis.get("detected_tasks", [])
            
            # Step: Task Decomposition
            decomposed_tasks = TaskDecomposer.decompose(detected_tasks)

            # Step: Priority Engine (Urgency + Importance + Effort + Dependencies)
            ranked_tasks = PriorityEngine.rank(decomposed_tasks)

            # Step: Schedule Planning
            plan_result = PlannerService.create_plan(ranked_tasks, analysis.get("constraints", {}))
            
            if not plan_result.get("feasible", True):
                # Workload overload error handling
                cursor.execute("UPDATE agent_runs SET status = 'FAILED' WHERE id = ?", (run_id,))
                conn.commit()
                return {
                    "run_id": run_id,
                    "intent": intent,
                    "status": "FAILED",
                    "error": plan_result.get("error"),
                    "recommendation": plan_result.get("recommendation")
                }

            # Save generated plan to database
            cursor.execute(
                """
                INSERT INTO plans (goal, total_estimated_hours, daily_hours_limit, constraints, status, plan_json, created_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
                """,
                (
                    user_goal,
                    plan_result.get("total_hours", 0.0),
                    analysis.get("constraints", {}).get("daily_hours", 3.0),
                    json.dumps(analysis.get("constraints", {})),
                    json.dumps(plan_result),
                    now
                )
            )
            plan_id = cursor.lastrowid

            # Update timeline with full agent steps
            timeline = [
                {"step": "RECEIVED", "time": now, "details": f"Goal received: '{user_goal}'"},
                {"step": "INTENT_ANALYSIS", "time": now, "details": f"Intent: Academic Planning | {len(detected_tasks)} high-level milestones extracted"},
                {"step": "TASK_DECOMPOSITION", "time": now, "details": f"Decomposed into {sum(len(t.get('subtasks', [])) for t in decomposed_tasks)} modular subtasks"},
                {"step": "PRIORITIZATION", "time": now, "details": f"Ranked {len(ranked_tasks)} tasks via multi-factor urgency algorithm"},
                {"step": "PLAN_GENERATION", "time": now, "details": f"Generated {len(plan_result.get('days', []))}-day balanced study schedule"},
                {"step": "HUMAN_APPROVAL_REQUIRED", "time": now, "details": "Formulated atomic tool execution plan awaiting human sign-off"}
            ]

            cursor.execute(
                """
                UPDATE agent_runs 
                SET timeline_json = ?, status = 'WAITING_APPROVAL' 
                WHERE id = ?
                """,
                (json.dumps(timeline), run_id)
            )
            conn.commit()

            # Formulate Proposed Actions and Human Approval Request
            approval_res = ApprovalManager.create_approval_request(run_id, ranked_tasks, plan_result)

            return {
                "run_id": run_id,
                "plan_id": plan_id,
                "intent": intent,
                "status": "WAITING_APPROVAL",
                "analysis": analysis,
                "ranked_tasks": ranked_tasks,
                "plan": plan_result,
                "timeline": timeline,
                "approval": approval_res
            }

        finally:
            conn.close()

    @staticmethod
    def approve_and_execute(approval_id):
        """Human approval callback -> executes actions via allowlisted tools."""
        return ToolExecutor.execute_approval(approval_id)

    @staticmethod
    def reject_plan(approval_id, reason="Rejected by user"):
        """Human rejection callback."""
        return ApprovalManager.reject(approval_id, reason)

    @staticmethod
    def get_run(run_id):
        """Fetches full execution state, timeline, tool calls, and approvals for a run."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            run_data = dict(row)
            run_data["timeline"] = json.loads(run_data["timeline_json"] or "[]")
            run_data["proposed_actions"] = json.loads(run_data["proposed_actions_json"] or "[]")
            run_data["execution_summary"] = json.loads(run_data["execution_summary_json"] or "{}")

            cursor.execute("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY timestamp ASC", (run_id,))
            run_data["tool_calls"] = [
                {
                    "id": tc["id"],
                    "tool_name": tc["tool_name"],
                    "function_name": tc["function_name"],
                    "arguments": json.loads(tc["arguments_json"] or "{}"),
                    "result": json.loads(tc["result_json"] or "{}"),
                    "status": tc["status"],
                    "timestamp": tc["timestamp"]
                }
                for tc in cursor.fetchall()
            ]

            cursor.execute("SELECT * FROM approvals WHERE run_id = ?", (run_id,))
            appr = cursor.fetchone()
            run_data["approval"] = dict(appr) if appr else None
            return run_data
        finally:
            conn.close()

    @staticmethod
    def list_runs():
        """Lists recent agent runs."""
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_runs ORDER BY id DESC LIMIT 50")
            runs = []
            for r in cursor.fetchall():
                rd = dict(r)
                rd["timeline"] = json.loads(rd["timeline_json"] or "[]")
                runs.append(rd)
            return runs
        finally:
            conn.close()
