from datetime import date, timedelta
from app.tools.planner_tool import PlannerTool

class PlannerService:
    @staticmethod
    def create_plan(ranked_tasks, constraints=None):
        """
        Creates a feasible execution plan based on ranked tasks and constraints.
        Validates workload capacity against daily limits and flags overloads.
        """
        constraints = constraints or {}
        daily_hours = float(constraints.get("daily_hours", 3.0))
        max_daily_hours = float(constraints.get("max_daily_hours", 8.0))
        
        total_hours = sum(t.get("duration_hours", 1.0) for t in ranked_tasks)
        
        # Check workload feasibility
        # If user asked for single-day or has specific day constraint that is impossible
        if daily_hours > max_daily_hours:
            return {
                "feasible": False,
                "error": f"Requested daily workload ({daily_hours}h) exceeds maximum safe capacity ({max_daily_hours}h).",
                "recommendation": "Reduce daily study hours or spread tasks across additional days."
            }

        plan_result = PlannerTool.generate_plan(
            tasks=ranked_tasks,
            daily_hours=daily_hours,
            start_date=date.today().isoformat()
        )

        plan_result["feasible"] = True
        plan_result["total_estimated_hours"] = total_hours
        plan_result["daily_hours_limit"] = daily_hours
        return plan_result
