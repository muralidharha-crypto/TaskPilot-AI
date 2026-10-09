from app.services.agent import AgentService
from app.services.intent_analyzer import IntentAnalyzer
from app.services.replanner import ReplannerService
from app.tools.scheduler_tool import SchedulerTool
from app.tools.task_tool import TaskTool


def test_intent_analyzer():
    prompt = "I have a Java exam on Monday, DBMS assignment due tomorrow, and project presentation on Wednesday. I have 3 hours available every evening. Create a study plan."
    res = IntentAnalyzer.analyze(prompt)
    assert res["intent"] == "academic_planning"
    assert len(res["detected_tasks"]) >= 3
    assert res["constraints"]["daily_hours"] == 3.0

def test_full_agent_workflow(test_app):
    with test_app.app_context():
        prompt = "I have a Java exam on Monday, DBMS assignment due tomorrow, and project presentation on Wednesday. I have 3 hours available every evening. Create a study plan."
        
        # 1. Start Goal: Intent -> Decompose -> Prioritize -> Plan -> Formulate Approval
        result = AgentService.process_goal(prompt)
        assert result["status"] == "WAITING_APPROVAL"
        assert result["run_id"] is not None
        assert "approval" in result
        approval_id = result["approval"]["approval_id"]
        assert len(result["approval"]["proposed_actions"]) > 0

        # Verify no tasks were silently created yet (Human-in-the-loop guarantee)
        assert len(TaskTool.list_tasks()) == 0

        # 2. Human Approves Plan -> Tool Execution
        exec_result = AgentService.approve_and_execute(approval_id)
        assert exec_result["status"] == "COMPLETED"
        assert exec_result["summary"]["successful_actions"] > 0
        assert exec_result["user_approved_at"] is not None
        assert exec_result["agent_executed_at"] is not None

        # Verify tasks and schedules are now really created in the database
        created_tasks = TaskTool.list_tasks()
        assert len(created_tasks) >= 3
        schedules = SchedulerTool.get_schedule()
        assert len(schedules) > 0

        # 3. Simulate Schedule Disruption: "I couldn't study today" -> Conflict Detection & Replanning
        replan_res = ReplannerService.simulate_delay_and_replan("I couldn't study today")
        assert replan_res["conflict_detected"] is True
        assert "no longer feasible" in replan_res["conflict_description"].lower()
        assert replan_res["approval_id"] is not None

        # 4. Human Approves New Rebalanced Schedule
        new_exec = AgentService.approve_and_execute(replan_res["approval_id"])
        assert new_exec["status"] == "COMPLETED"
