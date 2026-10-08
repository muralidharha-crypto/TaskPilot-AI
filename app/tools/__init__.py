from app.tools.tool_registry import registry, ToolRegistry
from app.tools.task_tool import TaskTool
from app.tools.scheduler_tool import SchedulerTool
from app.tools.research_tool import ResearchTool
from app.tools.planner_tool import PlannerTool
from app.tools.monitor_tool import MonitorTool

def register_default_tools():
    # 1. Task Manager
    registry.register("task_manager", "create_task", TaskTool.create_task, "Create a new task and optional subtasks")
    registry.register("task_manager", "update_task", TaskTool.update_task, "Update an existing task")
    registry.register("task_manager", "delete_task", TaskTool.delete_task, "Delete a task")
    registry.register("task_manager", "complete_task", TaskTool.complete_task, "Mark a task as completed")
    registry.register("task_manager", "list_tasks", TaskTool.list_tasks, "List all tasks")
    registry.register("task_manager", "get_task", TaskTool.get_task, "Get task details by ID")

    # 2. Scheduler
    registry.register("scheduler", "create_schedule", SchedulerTool.create_schedule, "Create a scheduled study block")
    registry.register("scheduler", "update_schedule", SchedulerTool.update_schedule, "Update a schedule block")
    registry.register("scheduler", "remove_schedule", SchedulerTool.remove_schedule, "Remove a schedule block")
    registry.register("scheduler", "get_schedule", SchedulerTool.get_schedule, "Retrieve scheduled blocks")
    registry.register("scheduler", "mark_missed", SchedulerTool.mark_missed, "Mark a schedule block as missed")
    registry.register("scheduler", "clear_all_schedules", SchedulerTool.clear_all_schedules, "Clear all scheduled blocks")

    # 3. Research Tool
    registry.register("research_tool", "search_information", ResearchTool.search_information, "Search information and literature")
    registry.register("research_tool", "summarize_information", ResearchTool.summarize_information, "Summarize research with actionable points")

    # 4. Planner
    registry.register("planner", "generate_plan", PlannerTool.generate_plan, "Generate chronological multi-day execution plan")
    registry.register("planner", "prioritize_tasks", PlannerTool.prioritize_tasks, "Score and rank tasks based on urgency and importance")
    registry.register("planner", "replan", PlannerTool.replan, "Replan existing tasks around conflicts")

    # 5. Monitor
    registry.register("monitor", "get_progress", MonitorTool.get_progress, "Get overall task and schedule progress")
    registry.register("monitor", "detect_conflict", MonitorTool.detect_conflict, "Detect schedule conflicts and overloads")
    registry.register("monitor", "detect_overdue_tasks", MonitorTool.detect_overdue_tasks, "Identify overdue uncompleted tasks")

# Register tools on import
register_default_tools()

__all__ = [
    "registry",
    "ToolRegistry",
    "TaskTool",
    "SchedulerTool",
    "ResearchTool",
    "PlannerTool",
    "MonitorTool"
]
