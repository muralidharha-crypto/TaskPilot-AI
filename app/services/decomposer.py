class TaskDecomposer:

    @staticmethod
    def decompose(tasks, fixed_events=None):
        """
        Decompose actionable tasks into subtasks while preserving
        fixed calendar events.

        IMPORTANT:
        Fixed events are NOT tasks.
        They must:
            - remain at their exact date/time
            - never be decomposed
            - never receive study subtasks
            - block that time in the planner
        """

        decomposed = []

        # ---------------------------------------------------------
        # 1. DECOMPOSE ACTIONABLE TASKS
        # ---------------------------------------------------------

        for task in tasks or []:

            task_copy = dict(task)

            event_type = task_copy.get("event_type")
            task_type = task_copy.get("type")

            is_fixed = (
                event_type == "FIXED_EVENT"
                or task_type == "FIXED_EVENT"
            )

            # -----------------------------------------------------
            # FIXED EVENT
            # -----------------------------------------------------

            if is_fixed:

                task_copy["event_type"] = "FIXED_EVENT"
                task_copy["type"] = "FIXED_EVENT"

                task_copy["subtasks"] = []
                task_copy["subtask_count"] = 0

                task_copy["blocks_schedule"] = True
                task_copy["is_actionable"] = False

                decomposed.append(task_copy)

                continue

            # -----------------------------------------------------
            # ACTIONABLE TASK
            # -----------------------------------------------------

            subtasks = task_copy.get("subtasks", [])

            title = task_copy.get(
                "title",
                "Untitled Task"
            )

            title_lower = title.lower()

            try:
                duration = float(
                    task_copy.get(
                        "duration_hours",
                        2.0
                    )
                )
            except (TypeError, ValueError):
                duration = 2.0

            # -----------------------------------------------------
            # Use existing subtasks if already supplied
            # -----------------------------------------------------

            if not subtasks:

                # -------------------------------------------------
                # JAVA EXAM
                # -------------------------------------------------

                if (
                    "java" in title_lower
                    and (
                        "exam" in title_lower
                        or "test" in title_lower
                        or "prep" in title_lower
                    )
                ):

                    subtasks = [

                        {
                            "title":
                                "Review Java fundamentals & core syntax",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Review OOP principles & "
                                "inheritance/polymorphism",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Practice Collections framework "
                                "(List, Set, Map)",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Review Exception handling "
                                "& multithreading",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Solve coding practice problems",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Take comprehensive mock test",
                            "duration_hours": 0.5
                        }
                    ]

                # -------------------------------------------------
                # DBMS / DATABASE
                # -------------------------------------------------

                elif (
                    "dbms" in title_lower
                    or "database" in title_lower
                ):

                    subtasks = [

                        {
                            "title":
                                "Understand assignment requirements "
                                "& schema scope",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Research required concepts "
                                "& design ER diagram",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Write SQL queries and "
                                "normalization solution "
                                "(3NF/BCNF)",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Verify query output "
                                "against test cases",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Review and finalize documentation",
                            "duration_hours": 0.5
                        }
                    ]

                # -------------------------------------------------
                # PRESENTATION
                # -------------------------------------------------

                elif (
                    "presentation" in title_lower
                    or "slides" in title_lower
                ):

                    subtasks = [

                        {
                            "title":
                                "Prepare project explanation "
                                "& narrative flow",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Prepare architecture diagram "
                                "& visual assets",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Build presentation slides "
                                "& speaker notes",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Practice explanation "
                                "& demo walkthrough",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Final timing rehearsal "
                                "& peer review",
                            "duration_hours": 0.5
                        }
                    ]

                # -------------------------------------------------
                # GENERIC EXAM
                # -------------------------------------------------

                elif (
                    "exam" in title_lower
                    or "test" in title_lower
                ):

                    subtasks = [

                        {
                            "title":
                                f"Comprehensive syllabus review "
                                f"for {title}",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Core concept study "
                                "& high-yield note condensation",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Practice problems "
                                "and formula recall",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Timed mock test "
                                "& error analysis",
                            "duration_hours": 0.5
                        }
                    ]

                # -------------------------------------------------
                # ASSIGNMENT
                # -------------------------------------------------

                elif (
                    "assignment" in title_lower
                    or "homework" in title_lower
                    or (
                        "lab" in title_lower
                        and task_type != "FIXED_EVENT"
                    )
                ):

                    subtasks = [

                        {
                            "title":
                                f"Review assignment rubric "
                                f"and guidelines for {title}",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Draft core solution "
                                "& implementation",
                            "duration_hours": 1.0
                        },

                        {
                            "title":
                                "Verify results "
                                "and test edge cases",
                            "duration_hours": 0.5
                        },

                        {
                            "title":
                                "Final formatting "
                                "and submission",
                            "duration_hours": 0.3
                        }
                    ]

                # -------------------------------------------------
                # GENERIC TASK
                # -------------------------------------------------

                else:

                    if duration >= 1.5:
                        part = round(
                            duration / 3.0,
                            1
                        )
                    else:
                        part = 0.5

                    execution_duration = max(
                        0.5,
                        round(
                            duration - (2 * part),
                            1
                        )
                    )

                    subtasks = [

                        {
                            "title":
                                f"Requirements review "
                                f"and outline for {title}",
                            "duration_hours": part
                        },

                        {
                            "title":
                                f"Core execution and "
                                f"deliverable development "
                                f"for {title}",
                            "duration_hours":
                                execution_duration
                        },

                        {
                            "title":
                                f"Verification, testing, "
                                f"and final review for {title}",
                            "duration_hours": part
                        }
                    ]

            # -----------------------------------------------------
            # Mark as actionable
            # -----------------------------------------------------

            task_copy["event_type"] = "TASK_STUDY"
            task_copy["type"] = "ACTIONABLE_TASK"

            task_copy["blocks_schedule"] = False
            task_copy["is_actionable"] = True

            task_copy["subtasks"] = subtasks

            task_copy["subtask_count"] = len(
                subtasks
            )

            decomposed.append(task_copy)

        # ---------------------------------------------------------
        # 2. PRESERVE FIXED EVENTS
        # ---------------------------------------------------------

        for event in fixed_events or []:

            event_copy = dict(event)

            # Force correct classification.
            event_copy["event_type"] = "FIXED_EVENT"
            event_copy["type"] = "FIXED_EVENT"

            # Fixed events have NO subtasks.
            event_copy["subtasks"] = []
            event_copy["subtask_count"] = 0

            # Fixed events block planner availability.
            event_copy["blocks_schedule"] = True

            # They are not something the agent should "do".
            event_copy["is_actionable"] = False

            # Make sure required scheduling fields exist.
            if not event_copy.get("date_str"):
                event_copy["date_str"] = None

            if not event_copy.get("start_time"):
                event_copy["start_time"] = None

            if not event_copy.get("end_time"):
                event_copy["end_time"] = None

            decomposed.append(event_copy)

        return decomposed