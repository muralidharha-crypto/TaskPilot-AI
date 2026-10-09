from app.services.agent import AgentService
from app.services.planner import PlannerService
from app.tools.monitor_tool import MonitorTool
from app.tools.planner_tool import PlannerTool
from app.tools.scheduler_tool import SchedulerTool
from app.tools.task_tool import TaskTool


def test_pages_render(client):
    """Ensure all web pages render cleanly (HTTP 200)."""
    pages = ['/', '/tasks', '/planner', '/runs', '/approvals', '/calendar', '/research', '/analytics', '/health']
    for p in pages:
        res = client.get(p)
        assert res.status_code == 200

def test_priority_formula_breakdown():
    """Verify explainable multi-factor formula: 0.4*Urgency + 0.3*Importance + 0.2*Effort + 0.1*Dependencies"""
    # 1. Urgent task due tomorrow
    urgent_score = PlannerTool.calculate_priority_score(
        deadline_str="2026-10-09",
        duration_hours=3.0,
        importance="HIGH",
        dependency_count=1
    )
    assert urgent_score["score"] >= 75.0
    assert urgent_score["label"] in ("HIGH", "CRITICAL")
    assert "explanation" in urgent_score
    assert "urgency_score" in urgent_score["breakdown"]

    # 2. Low importance far-off task
    low_score = PlannerTool.calculate_priority_score(
        deadline_str="2026-12-31",
        duration_hours=1.0,
        importance="LOW",
        dependency_count=0
    )
    assert low_score["score"] < 55.0
    assert low_score["label"] == "LOW"

def test_workload_capacity_feasibility_check():
    """Verify Error Zero handling: Rejecting impossible schedules that exceed safe limits."""
    tasks = [
        {"title": "Massive Task", "duration_hours": 15.0, "priority": "HIGH", "status": "PENDING"}
    ]
    # Attempting to schedule 15h in a single day when limit is 8h
    res = PlannerService.create_plan(tasks, constraints={"daily_hours": 15.0, "max_daily_hours": 8.0})
    assert res["feasible"] is False
    assert "exceeds maximum safe capacity" in res["error"]
    assert "recommendation" in res

def test_approval_rejection_flow(test_app):
    """Verify human rejection terminates run without executing actions."""
    with test_app.app_context():
        res = AgentService.process_goal("Plan my exam preparation")
        approval_id = res["approval"]["approval_id"]

        rej = AgentService.reject_plan(approval_id, reason="Changed my mind")
        assert rej["status"] == "REJECTED"

        # Verify run marked CANCELLED
        run_data = AgentService.get_run(res["run_id"])
        assert run_data["status"] == "CANCELLED"
        # No tasks created
        assert len(TaskTool.list_tasks()) == 0

def test_conflict_detection_and_capacity_overflow(test_app):
    """Verify monitor tool catches overloaded days."""
    with test_app.app_context():
        # Schedule 5 hours on the same day when limit is 3h
        SchedulerTool.create_schedule("Block 1", "2026-10-10", "14:00", "16:00", duration_hours=2.0)
        SchedulerTool.create_schedule("Block 2", "2026-10-10", "16:00", "19:00", duration_hours=3.0)

        conflicts = MonitorTool.detect_conflict(daily_hours_limit=3.0)
        assert conflicts["has_conflict"] is True
        assert any(c["type"] == "TIME_OVERLOAD" for c in conflicts["conflicts"])
