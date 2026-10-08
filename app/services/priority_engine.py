from app.tools.planner_tool import PlannerTool

class PriorityEngine:
    @staticmethod
    def rank(tasks):
        """
        Ranks tasks using multi-factor priority scoring:
        Score = 0.4*Urgency + 0.3*Importance + 0.2*Effort + 0.1*Dependencies
        Returns sorted tasks with full mathematical breakdown and reasoning.
        """
        scored_tasks = []
        for t in tasks:
            t_copy = dict(t)
            score_meta = PlannerTool.calculate_priority_score(
                deadline_str=t_copy.get("deadline"),
                duration_hours=t_copy.get("duration_hours", 1.0),
                importance=t_copy.get("importance", t_copy.get("priority", "MEDIUM")),
                dependency_count=len(t_copy.get("dependencies", []))
            )
            t_copy["priority_score"] = score_meta["score"]
            t_copy["priority"] = score_meta["label"]
            t_copy["priority_explanation"] = score_meta["explanation"]
            t_copy["score_breakdown"] = score_meta["breakdown"]
            scored_tasks.append(t_copy)

        scored_tasks.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored_tasks
