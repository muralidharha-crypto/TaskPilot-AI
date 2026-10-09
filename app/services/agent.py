import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Config
from app.models.database import Database
from app.services.approval_manager import ApprovalManager
from app.services.decomposer import TaskDecomposer
from app.services.executor import ToolExecutor
from app.services.intent_analyzer import IntentAnalyzer
from app.services.planner import PlannerService
from app.services.priority_engine import PriorityEngine
from app.services.replanner import ReplannerService
from app.services.research_service import ResearchService


class AgentService:

    @staticmethod
    def process_goal(user_goal):
        """
        Main Agent Execution Entry Point.

        Lifecycle:

        RECEIVED
            ↓
        INTENT_ANALYSIS
            ↓
        TASK_DECOMPOSITION
            ↓
        PRIORITIZATION
            ↓
        PLAN_GENERATION
            ↓
        HUMAN_APPROVAL_REQUIRED
            ↓
        EXECUTION

        Fixed events are preserved separately from actionable tasks
        and are passed into the planner as schedule-blocking events.
        """

        # ---------------------------------------------------------
        # VALIDATE INPUT
        # ---------------------------------------------------------

        if not user_goal or not user_goal.strip():
            raise ValueError(
                "User goal cannot be empty."
            )

        now = datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            # =====================================================
            # 1. RECEIVED
            # =====================================================

            initial_timeline = [

                {
                    "step": "RECEIVED",
                    "time": now,
                    "details":
                        f"Goal received: '{user_goal}'"
                }

            ]

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
                    'unknown',
                    'RECEIVED',
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    user_goal.strip(),
                    json.dumps(initial_timeline),
                    now,
                    now
                )
            )

            run_id = cursor.lastrowid

            conn.commit()

            # =====================================================
            # 2. INTENT ANALYSIS
            # =====================================================

            analysis = IntentAnalyzer.analyze(
                user_goal
            )

            intent = analysis.get(
                "intent",
                "ACTIONABLE_TASK"
            )

            cursor.execute(
                """
                UPDATE agent_runs
                SET
                    intent = ?,
                    status = 'ANALYZING',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    intent,
                    now,
                    run_id
                )
            )

            conn.commit()

            # =====================================================
            # 3. RESEARCH REQUEST
            # =====================================================

            if intent == "RESEARCH_REQUEST":

                research_res = ResearchService.run_research(
                    analysis.get(
                        "topic",
                        user_goal
                    )
                )

                return {

                    "run_id": run_id,

                    "intent": intent,

                    "status": "COMPLETED",

                    "type": "RESEARCH",

                    "research": research_res
                }

            # =====================================================
            # 4. REPLANNING REQUEST
            # =====================================================

            if intent == "REPLANNING_REQUEST":

                replan_res = (
                    ReplannerService
                    .simulate_delay_and_replan(
                        reason=user_goal
                    )
                )

                return {

                    "run_id":
                        replan_res.get(
                            "replan_run_id",
                            run_id
                        ),

                    "intent": intent,

                    "status":
                        "WAITING_APPROVAL",

                    "type": "REPLAN",

                    "replan": replan_res
                }

            # =====================================================
            # 5. EXTRACT TASKS AND FIXED EVENTS
            # =====================================================

            detected_tasks = analysis.get(
                "detected_tasks",
                []
            )

            fixed_events = analysis.get(
                "fixed_events",
                []
            )

            # Make sure they are always lists.
            if not isinstance(
                detected_tasks,
                list
            ):
                detected_tasks = []

            if not isinstance(
                fixed_events,
                list
            ):
                fixed_events = []

            # =====================================================
            # 6. TASK DECOMPOSITION
            # =====================================================

            # IMPORTANT:
            #
            # Previously:
            #
            # TaskDecomposer.decompose(detected_tasks)
            #
            # This completely dropped fixed_events.
            #
            # Now both are passed forward.

            decomposed_tasks = (
                TaskDecomposer.decompose(
                    detected_tasks,
                    fixed_events
                )
            )

            # =====================================================
            # 7. SEPARATE FIXED EVENTS FROM ACTIONABLE TASKS
            # =====================================================

            actionable_decomposed_tasks = []

            preserved_fixed_events = []

            for item in decomposed_tasks:

                if (
                    item.get("event_type")
                    == "FIXED_EVENT"
                    or item.get("type")
                    == "FIXED_EVENT"
                ):

                    preserved_fixed_events.append(
                        item
                    )

                else:

                    actionable_decomposed_tasks.append(
                        item
                    )

            # =====================================================
            # 8. PRIORITY ENGINE
            # =====================================================

            # IMPORTANT:
            #
            # Fixed events must NOT be ranked as normal tasks.
            #
            # They are calendar constraints.
            #
            ranked_tasks = PriorityEngine.rank(
                actionable_decomposed_tasks
            )

            # =====================================================
            # 9. PLANNER INPUT
            # =====================================================

            planner_constraints = dict(
                analysis.get(
                    "constraints",
                    {}
                )
            )

            # Pass fixed events explicitly to the planner.
            planner_constraints[
                "fixed_events"
            ] = preserved_fixed_events

            planner_constraints[
                "fixed_event_blocks"
            ] = len(
                preserved_fixed_events
            )

            # =====================================================
            # 10. PLAN GENERATION
            # =====================================================

            plan_result = PlannerService.create_plan(
                ranked_tasks,
                planner_constraints
            )

            # -----------------------------------------------------
            # Ensure fixed events are visible in plan result.
            # -----------------------------------------------------

            if not isinstance(
                plan_result,
                dict
            ):
                plan_result = {
                    "feasible": False,
                    "error":
                        "Planner returned an invalid response."
                }

            plan_result[
                "fixed_events"
            ] = preserved_fixed_events

            # =====================================================
            # 11. PLAN FEASIBILITY
            # =====================================================

            if not plan_result.get(
                "feasible",
                True
            ):

                cursor.execute(
                    """
                    UPDATE agent_runs
                    SET
                        status = 'FAILED',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat(),
                        run_id
                    )
                )

                conn.commit()

                return {

                    "run_id": run_id,

                    "intent": intent,

                    "status": "FAILED",

                    "error":
                        plan_result.get(
                            "error"
                        ),

                    "recommendation":
                        plan_result.get(
                            "recommendation"
                        )
                }

            # =====================================================
            # 12. SAVE PLAN
            # =====================================================

            cursor.execute(
                """
                INSERT INTO plans (
                    goal,
                    total_estimated_hours,
                    daily_hours_limit,
                    constraints,
                    status,
                    plan_json,
                    created_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    'ACTIVE',
                    ?,
                    ?
                )
                """,
                (

                    user_goal,

                    plan_result.get(
                        "total_hours",
                        0.0
                    ),

                    analysis.get(
                        "constraints",
                        {}
                    ).get(
                        "daily_hours",
                        3.0
                    ),

                    json.dumps(
                        planner_constraints
                    ),

                    json.dumps(
                        plan_result
                    ),

                    now
                )
            )

            plan_id = cursor.lastrowid

            # =====================================================
            # 13. BUILD AGENT TIMELINE
            # =====================================================

            total_subtasks = sum(
                len(
                    task.get(
                        "subtasks",
                        []
                    )
                )
                for task
                in actionable_decomposed_tasks
            )

            timeline = [

                {
                    "step": "RECEIVED",
                    "time": now,
                    "details":
                        f"Goal received: '{user_goal}'"
                },

                {
                    "step": "INTENT_ANALYSIS",
                    "time": now,
                    "details":
                        (
                            f"Intent: {intent} | "
                            f"{len(detected_tasks)} "
                            f"actionable task(s) | "
                            f"{len(fixed_events)} "
                            f"fixed event(s)"
                        )
                },

                {
                    "step": "TASK_DECOMPOSITION",
                    "time": now,
                    "details":
                        (
                            f"Decomposed into "
                            f"{total_subtasks} "
                            f"modular subtasks; "
                            f"{len(preserved_fixed_events)} "
                            f"fixed event(s) preserved"
                        )
                },

                {
                    "step": "PRIORITIZATION",
                    "time": now,
                    "details":
                        (
                            f"Ranked "
                            f"{len(ranked_tasks)} "
                            f"actionable task(s) "
                            f"via multi-factor "
                            f"urgency algorithm"
                        )
                },

                {
                    "step": "PLAN_GENERATION",
                    "time": now,
                    "details":
                        (
                            f"Generated "
                            f"{len(plan_result.get('days', []))} "
                            f"day balanced study schedule "
                            f"with "
                            f"{len(preserved_fixed_events)} "
                            f"blocked calendar event(s)"
                        )
                },

                {
                    "step":
                        "HUMAN_APPROVAL_REQUIRED",

                    "time": now,

                    "details":
                        (
                            "Formulated atomic tool "
                            "execution plan awaiting "
                            "human sign-off"
                        )
                }
            ]

            # =====================================================
            # 14. SAVE AGENT RUN STATE
            # =====================================================

            cursor.execute(
                """
                UPDATE agent_runs
                SET
                    timeline_json = ?,
                    status = 'WAITING_APPROVAL',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        timeline
                    ),
                    datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat(),
                    run_id
                )
            )

            conn.commit()

            # =====================================================
            # 15. HUMAN APPROVAL
            # =====================================================

            approval_res = (
                ApprovalManager
                .create_approval_request(
                    run_id,
                    ranked_tasks,
                    plan_result
                )
            )

            # =====================================================
            # 16. RETURN COMPLETE RESULT
            # =====================================================

            return {

                "run_id": run_id,

                "plan_id": plan_id,

                "intent": intent,

                "status":
                    "WAITING_APPROVAL",

                "analysis": analysis,

                "detected_tasks":
                    detected_tasks,

                "fixed_events":
                    preserved_fixed_events,

                "ranked_tasks":
                    ranked_tasks,

                "plan":
                    plan_result,

                "timeline":
                    timeline,

                "approval":
                    approval_res
            }

        finally:

            conn.close()

    # =============================================================
    # APPROVE + EXECUTE
    # =============================================================

    @staticmethod
    def approve_and_execute(approval_id):
        """
        Human approval callback.

        No state-changing tool should execute before
        explicit approval.
        """

        return ToolExecutor.execute_approval(
            approval_id
        )

    # =============================================================
    # REJECT PLAN
    # =============================================================

    @staticmethod
    def reject_plan(
        approval_id,
        reason="Rejected by user"
    ):
        """
        Human rejection callback.
        """

        return ApprovalManager.reject(
            approval_id,
            reason
        )

    # =============================================================
    # GET RUN
    # =============================================================

    @staticmethod
    def get_run(run_id):
        """
        Fetch complete execution state:

            timeline
            proposed actions
            execution summary
            tool calls
            approval
        """

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM agent_runs
                WHERE id = ?
                """,
                (run_id,)
            )

            row = cursor.fetchone()

            if not row:
                return None

            run_data = dict(row)

            run_data["timeline"] = json.loads(
                run_data.get(
                    "timeline_json",
                    "[]"
                ) or "[]"
            )

            run_data[
                "proposed_actions"
            ] = json.loads(
                run_data.get(
                    "proposed_actions_json",
                    "[]"
                ) or "[]"
            )

            run_data[
                "execution_summary"
            ] = json.loads(
                run_data.get(
                    "execution_summary_json",
                    "{}"
                ) or "{}"
            )

            # -----------------------------------------------------
            # TOOL CALLS
            # -----------------------------------------------------

            cursor.execute(
                """
                SELECT *
                FROM tool_calls
                WHERE run_id = ?
                ORDER BY timestamp ASC
                """,
                (run_id,)
            )

            run_data["tool_calls"] = [

                {

                    "id": tc["id"],

                    "tool_name":
                        tc["tool_name"],

                    "function_name":
                        tc["function_name"],

                    "arguments": json.loads(
                        tc["arguments_json"]
                        or "{}"
                    ),

                    "result": json.loads(
                        tc["result_json"]
                        or "{}"
                    ),

                    "status":
                        tc["status"],

                    "timestamp":
                        tc["timestamp"]
                }

                for tc
                in cursor.fetchall()
            ]

            # -----------------------------------------------------
            # APPROVAL
            # -----------------------------------------------------

            cursor.execute(
                """
                SELECT *
                FROM approvals
                WHERE run_id = ?
                """,
                (run_id,)
            )

            approval = cursor.fetchone()

            run_data["approval"] = (
                dict(approval)
                if approval
                else None
            )

            return run_data

        finally:

            conn.close()

    # =============================================================
    # LIST RUNS
    # =============================================================

    @staticmethod
    def list_runs():
        """
        Returns the latest 50 agent runs.
        """

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM agent_runs
                ORDER BY id DESC
                LIMIT 50
                """
            )

            runs = []

            for row in cursor.fetchall():

                run_data = dict(row)

                run_data[
                    "timeline"
                ] = json.loads(
                    run_data.get(
                        "timeline_json",
                        "[]"
                    ) or "[]"
                )

                runs.append(
                    run_data
                )

            return runs

        finally:

            conn.close()
