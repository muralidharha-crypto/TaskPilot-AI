class TaskDecomposer:
    @staticmethod
    def decompose(tasks):
        """
        Decomposes high-level tasks into actionable subtasks with time estimates.
        Ensures all tasks have clearly defined modular components.
        """
        decomposed = []
        for t in tasks:
            t_copy = dict(t)
            subtasks = t_copy.get("subtasks", [])
            
            if not subtasks:
                title = t_copy.get("title", "")
                dur = float(t_copy.get("duration_hours", 2.0))
                part1_dur = round(dur * 0.4, 1)
                part2_dur = round(dur * 0.4, 1)
                part3_dur = round(dur - part1_dur - part2_dur, 1)
                if part3_dur <= 0:
                    part3_dur = 0.5
                
                subtasks = [
                    {"title": f"Initial research & prep for {title}", "duration_hours": max(0.5, part1_dur)},
                    {"title": f"Core execution for {title}", "duration_hours": max(0.5, part2_dur)},
                    {"title": f"Review & final validation for {title}", "duration_hours": max(0.5, part3_dur)}
                ]
            
            t_copy["subtasks"] = subtasks
            t_copy["subtask_count"] = len(subtasks)
            decomposed.append(t_copy)

        return decomposed
