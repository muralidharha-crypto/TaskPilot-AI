from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Config
from app.tools.planner_tool import PlannerTool


class PlannerService:
    @staticmethod
    def create_plan(ranked_tasks, constraints=None):
        """
        Creates a feasible execution plan based on ranked tasks and constraints.

        Fixed events such as tutoring classes, lectures, meetings, etc.
        are treated as calendar blocks and are NOT treated as study tasks.
        """

        constraints = constraints or {}

        daily_hours = float(constraints.get("daily_hours", 3.0))
        max_daily_hours = float(
            constraints.get("max_daily_hours", 8.0)
        )

        fixed_events = constraints.get("fixed_events", [])

        # ---------------------------------------------------------
        # 1. Calculate workload from actionable tasks only
        # ---------------------------------------------------------
        total_hours = sum(
            float(task.get("duration_hours", 1.0))
            for task in ranked_tasks
            if task.get("event_type") != "FIXED_EVENT"
            and task.get("type") != "FIXED_EVENT"
        )

        # ---------------------------------------------------------
        # 2. Validate daily capacity
        # ---------------------------------------------------------
        if daily_hours > max_daily_hours:
            return {
                "feasible": False,
                "error": (
                    f"Requested daily workload ({daily_hours}h) "
                    f"exceeds maximum safe capacity "
                    f"({max_daily_hours}h)."
                ),
                "recommendation": (
                    "Reduce daily study hours or spread tasks "
                    "across additional days."
                ),
                "fixed_events": fixed_events,
            }

        # ---------------------------------------------------------
        # 3. Generate plan
        # ---------------------------------------------------------
        plan_result = PlannerTool.generate_plan(
            tasks=ranked_tasks,
            daily_hours=daily_hours,
            start_date=datetime.now(ZoneInfo(Config.TIMEZONE)).date().isoformat(),
            fixed_events=fixed_events,
        )

        # ---------------------------------------------------------
        # 4. Preserve fixed events in the result
        # ---------------------------------------------------------
        plan_result["fixed_events"] = fixed_events

        # ---------------------------------------------------------
        # 5. Planning metadata
        # ---------------------------------------------------------
        plan_result["feasible"] = True
        plan_result["total_estimated_hours"] = total_hours
        plan_result["daily_hours_limit"] = daily_hours
        plan_result["max_daily_hours"] = max_daily_hours

        return plan_result