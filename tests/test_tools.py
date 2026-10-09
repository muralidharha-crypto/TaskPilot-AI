from app.tools.monitor_tool import MonitorTool
from app.tools.planner_tool import PlannerTool
from app.tools.research_tool import ResearchTool
from app.tools.scheduler_tool import SchedulerTool
from app.tools.task_tool import TaskTool


def test_task_crud(test_app):
    with test_app.app_context():
        # 1. Create task
        task = TaskTool.create_task(
            title="DBMS Assignment",
            description="Complete ER diagrams",
            priority="HIGH",
            deadline="2026-10-09",
            duration_hours=3.0,
            subtasks=["Read specs", "Draw ER", "SQL queries"]
        )
        assert task["id"] is not None
        assert task["title"] == "DBMS Assignment"
        assert len(task["subtasks"]) == 3

        # 2. Update task
        updated = TaskTool.update_task(task["id"], priority="CRITICAL")
        assert updated["priority"] == "CRITICAL"

        # 3. Complete task
        comp = TaskTool.complete_task(task["id"])
        assert comp["status"] == "COMPLETED"

        # 4. List tasks
        all_tasks = TaskTool.list_tasks()
        assert len(all_tasks) == 1
        assert all_tasks[0]["status"] == "COMPLETED"

        # 5. Delete task
        deleted = TaskTool.delete_task(task["id"])
        assert deleted["deleted"] is True
        assert len(TaskTool.list_tasks()) == 0

def test_scheduler_crud(test_app):
    with test_app.app_context():
        sched = SchedulerTool.create_schedule(
            title="Study DBMS",
            date_str="2026-10-09",
            start_time="18:00",
            end_time="19:00",
            duration_hours=1.0
        )
        assert sched["id"] is not None
        assert sched["title"] == "Study DBMS"

        schedules = SchedulerTool.get_schedule(date_str="2026-10-09")
        assert len(schedules) == 1

        missed = SchedulerTool.mark_missed(sched["id"])
        assert missed["status"] == "MISSED"

def test_research_tool(test_app):
    with test_app.app_context():
        # Curated lookup
        search_res = ResearchTool.search_information("AI agents in education")
        assert "sources" in search_res
        assert len(search_res["sources"]) > 0

        summary_res = ResearchTool.summarize_information("AI agents in education")
        assert "findings" in summary_res
        assert "action_items" in summary_res
        assert len(summary_res["action_items"]) > 0

def test_planner_priority_and_schedule(test_app):
    with test_app.app_context():
        # Score calculation
        score_meta = PlannerTool.calculate_priority_score("2026-10-09", 3.0, "HIGH", 0)
        assert score_meta["score"] > 60.0
        assert "breakdown" in score_meta
        assert "urgency_score" in score_meta["breakdown"]

        # Plan generation
        tasks = [
            {"id": 1, "title": "Task A", "priority": "HIGH", "duration_hours": 2.0, "status": "PENDING", "subtasks": []},
            {"id": 2, "title": "Task B", "priority": "LOW", "duration_hours": 2.0, "status": "PENDING", "subtasks": []}
        ]
        plan = PlannerTool.generate_plan(tasks=tasks, daily_hours=3.0)
        assert len(plan["days"]) >= 2
        assert plan["total_hours"] == 4.0

def test_monitor_tool(test_app):
    with test_app.app_context():
        TaskTool.create_task(title="Past Task", deadline="2020-01-01", duration_hours=1.0)
        overdue = MonitorTool.detect_overdue_tasks()
        assert len(overdue) == 1
        assert overdue[0]["status"] == "OVERDUE"

        progress = MonitorTool.get_progress()
        assert progress["total_tasks"] == 1
        assert progress["overdue_tasks"] == 1
