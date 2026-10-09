import re
from datetime import datetime, timedelta
from types import MappingProxyType
from zoneinfo import ZoneInfo

from app.config import Config


class IntentAnalyzer:
    """Analyze user goals and extract events, tasks, and scheduling constraints."""

    WEEKDAYS = MappingProxyType(
        {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
    )

    FIXED_EVENT_KEYWORDS = (
        "class",
        "tutoring",
        "lecture",
        "lab",
        "meeting",
        "appointment",
        "call",
        "interview",
        "webinar",
        "seminar",
        "travel",
        "flight",
    )

    @staticmethod
    def _today():
        """Return today's date in the configured application timezone."""
        timezone = ZoneInfo(Config.TIMEZONE)
        return datetime.now(timezone).date()

    @staticmethod
    def resolve_relative_date(text_reference, base_date=None):
        """Convert relative dates into ISO YYYY-MM-DD format."""
        if base_date is None:
            base_date = IntentAnalyzer._today()

        ref = text_reference.lower().strip()

        if "day after tomorrow" in ref:
            return (base_date + timedelta(days=2)).isoformat()

        if "tomorrow" in ref:
            return (base_date + timedelta(days=1)).isoformat()

        if "today" in ref:
            return base_date.isoformat()

        days_match = re.search(r"\bin\s+(\d+)\s+days?\b", ref)
        if days_match:
            days = int(days_match.group(1))
            return (base_date + timedelta(days=days)).isoformat()

        iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", ref)
        if iso_match:
            return iso_match.group(1)

        for day_name, day_idx in IntentAnalyzer.WEEKDAYS.items():
            if re.search(rf"\b{day_name}\b", ref):
                days_ahead = (day_idx - base_date.weekday()) % 7

                if days_ahead == 0:
                    days_ahead = 7

                return (base_date + timedelta(days=days_ahead)).isoformat()

        return (base_date + timedelta(days=1)).isoformat()

    @staticmethod
    def parse_time_string(text):
        """Extract a time and convert it to 24-hour HH:MM format."""
        match = re.search(
            r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = (match.group(3) or "").lower()

        if hour > 23 or minute > 59:
            return None

        if meridiem:
            if hour < 1 or hour > 12:
                return None

            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
        elif hour < 7:
            hour += 12

        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def analyze(user_prompt):
        """
        Classify a user prompt as:
        FIXED_EVENT, ACTIONABLE_TASK, RESEARCH_REQUEST,
        REPLANNING_REQUEST, MIXED_REQUEST, or academic_planning.
        """
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("user_prompt must be a non-empty string")

        prompt = user_prompt.strip()
        p_lower = prompt.lower()

        # 1. Detect requests to replan a disrupted schedule.
        replanning_pattern = (
            r"\b(couldn't study|could not study|didn't study|"
            r"missed study|cancel today|reschedule today|fell behind)\b"
        )

        if re.search(replanning_pattern, p_lower):
            return {
                "intent": "REPLANNING_REQUEST",
                "goal": prompt,
                "reason": prompt,
                "summary": (
                    "Detected schedule disruption requiring "
                    "autonomous conflict detection and replanning."
                ),
            }

        # 2. Detect research questions.
        research_pattern = (
            r"^(?:tell\s+me\s+about|what\s+is|what\s+are|"
            r"explain|overview\s+of|research\b|explore\b|"
            r"how\s+does|pros\s+and\s+cons|"
            r"advantages\s+and\s+disadvantages)"
        )

        is_research = bool(
            re.search(research_pattern, p_lower)
            or (
                re.search(r"\b(research|literature|investigate)\b", p_lower)
                and not re.search(
                    r"\b(due|exam|assignment|class|tutoring)\b",
                    p_lower,
                )
            )
        )

        if is_research:
            clean_topic = re.sub(
                r"^(?:tell\s+me\s+about\s+(?:the\s+)?|"
                r"what\s+is\s+(?:the\s+)?|"
                r"what\s+are\s+(?:the\s+)?|"
                r"explain\s+(?:the\s+)?|"
                r"overview\s+of\s+(?:the\s+)?|"
                r"research\s+(?:on\s+|about\s+|the\s+)?|"
                r"research\s+the\s+advantages\s+and\s+"
                r"disadvantages\s+of\s+)",
                "",
                prompt,
                flags=re.IGNORECASE,
            ).strip(" ?.")

            return {
                "intent": "RESEARCH_REQUEST",
                "goal": prompt,
                "topic": clean_topic,
                "summary": (
                    "Identified academic/factual research inquiry on: "
                    f"'{clean_topic}'."
                ),
            }

        # 3. Extract daily available hours.
        base_date = IntentAnalyzer._today()

        hours_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*"
            r"(?:available|free|every\s*evening|per\s*day|daily)?",
            p_lower,
        )

        daily_hours = (
            float(hours_match.group(1))
            if hours_match
            else Config.DEFAULT_EVENING_HOURS
        )

        # 4. Extract fixed events and actionable tasks.
        fixed_events = IntentAnalyzer._extract_fixed_events(
            prompt,
            base_date,
        )

        actionable_tasks = IntentAnalyzer._extract_actionable_tasks(
            prompt,
            base_date,
        )

        # 5. Detect academic-planning requests.
        academic_keywords = re.search(
            r"\b(exam|exams|assignment|assignments|study|studying|"
            r"academic|presentation|coursework|homework|revision|"
            r"java|dbms)\b",
            p_lower,
        )

        planning_keywords = re.search(
            r"\b(plan|planning|schedule|organize|organise|"
            r"allocate|timetable|create|make|build|prepare)\b",
            p_lower,
        )

        is_academic_planning = bool(
            academic_keywords and planning_keywords
        )

        # 6. Classify the request.
        # Preserve the existing academic-planning classification.
        if is_academic_planning:
            intent = "academic_planning"
        elif fixed_events and actionable_tasks:
            intent = "MIXED_REQUEST"
        elif fixed_events:
            intent = "FIXED_EVENT"
        else:
            intent = "ACTIONABLE_TASK"

        # 7. Calculate estimated workload.
        total_workload = sum(
            float(task.get("duration_hours", 0))
            for task in actionable_tasks
        )

        # 8. Return structured analysis.
        return {
            "intent": intent,
            "goal": prompt,
            "fixed_events": fixed_events,
            "detected_tasks": actionable_tasks,
            "total_tasks": len(actionable_tasks),
            "total_fixed_events": len(fixed_events),
            "total_estimated_hours": total_workload,
            "constraints": {
                "daily_hours": daily_hours,
                "schedule_timing": "evening (6:00 PM - 9:00 PM)",
                "fixed_event_blocks": len(fixed_events),
            },
            "summary": (
                f"Classified as {intent}: "
                f"{len(fixed_events)} fixed event(s) and "
                f"{len(actionable_tasks)} actionable task(s) detected."
            ),
        }

    @staticmethod
    def _extract_fixed_events(prompt, base_date):
        """Extract fixed calendar events that constrain availability."""
        events = []
        clauses = re.split(r"\band\b|[,;]", prompt, flags=re.IGNORECASE)

        for clause in clauses:
            text = clause.strip()
            text_lower = text.lower()

            is_fixed = any(
                keyword in text_lower
                for keyword in IntentAnalyzer.FIXED_EVENT_KEYWORDS
            )

            time_str = IntentAnalyzer.parse_time_string(text)

            if not is_fixed or not time_str:
                continue

            title = "Fixed Event"

            for keyword in IntentAnalyzer.FIXED_EVENT_KEYWORDS:
                if keyword in text_lower:
                    title = keyword.capitalize()

                    if "class" in text_lower and keyword != "class":
                        title = f"{keyword.capitalize()} Class"

                    break

            duration_match = re.search(
                r"\bfor\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
                text_lower,
            )

            duration = (
                float(duration_match.group(1))
                if duration_match
                else 1.0
            )

            event_date = base_date.isoformat()

            if "day after tomorrow" in text_lower:
                event_date = IntentAnalyzer.resolve_relative_date(
                    "day after tomorrow",
                    base_date,
                )
            elif "tomorrow" in text_lower:
                event_date = IntentAnalyzer.resolve_relative_date(
                    "tomorrow",
                    base_date,
                )
            else:
                for weekday in IntentAnalyzer.WEEKDAYS:
                    if re.search(rf"\b{weekday}\b", text_lower):
                        event_date = IntentAnalyzer.resolve_relative_date(
                            weekday,
                            base_date,
                        )
                        break

            end_time = IntentAnalyzer.calculate_end_time(
                time_str,
                duration,
            )

            events.append(
                {
                    "id": len(events) + 1,
                    "title": title,
                    "event_type": "FIXED_EVENT",
                    "date_str": event_date,
                    "start_time": time_str,
                    "end_time": end_time,
                    "duration_hours": duration,
                    "subtasks": [],
                    "notes": f"Fixed commitment ({title})",
                }
            )

        return events

    @staticmethod
    def _extract_actionable_tasks(prompt, base_date):
        """Extract actionable study and work tasks."""
        tasks = []
        p_lower = prompt.lower()

        # 1. DBMS assignment.
        if "dbms" in p_lower:
            if "day after tomorrow" in p_lower:
                deadline_text = "day after tomorrow"
            elif "tomorrow" in p_lower:
                deadline_text = "tomorrow"
            elif "monday" in p_lower:
                deadline_text = "monday"
            else:
                deadline_text = "in 2 days"

            deadline = IntentAnalyzer.resolve_relative_date(
                deadline_text,
                base_date,
            )

            tasks.append(
                {
                    "id": len(tasks) + 1,
                    "title": "DBMS Assignment",
                    "subject": "Database Management Systems",
                    "type": "ACTIONABLE_TASK",
                    "status": "PENDING",
                    "deadline": deadline,
                    "deadline_text": deadline_text,
                    "duration_hours": 3.0,
                    "importance": "HIGH",
                    "subtasks": [
                        {
                            "title": (
                                "Understand assignment requirements "
                                "& schema design"
                            ),
                            "duration_hours": 0.5,
                        },
                        {
                            "title": (
                                "Draft ER diagram and identify constraints"
                            ),
                            "duration_hours": 0.5,
                        },
                        {
                            "title": (
                                "Write SQL queries and normalization solution"
                            ),
                            "duration_hours": 1.0,
                        },
                        {
                            "title": (
                                "Verify results and query execution plan"
                            ),
                            "duration_hours": 0.5,
                        },
                        {
                            "title": "Review, format check & submit",
                            "duration_hours": 0.5,
                        },
                    ],
                }
            )

        # 2. Java exam preparation or study.
        if "java" in p_lower:
            is_exam = bool(re.search(r"\b(exam|test)\b", p_lower))

            if "monday" in p_lower:
                deadline_text = "monday"
            elif "tomorrow" in p_lower:
                deadline_text = "tomorrow"
            else:
                deadline_text = "in 2 days"

            deadline = IntentAnalyzer.resolve_relative_date(
                deadline_text,
                base_date,
            )

            duration_match = re.search(
                r"(?:java.*?\bfor|for)\s+"
                r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)",
                p_lower,
            )

            duration = (
                float(duration_match.group(1))
                if duration_match
                else (4.0 if is_exam else 2.0)
            )

            title = "Java Exam Preparation" if is_exam else "Java Study"

            if is_exam:
                subtasks = [
                    {
                        "title": "Review Java fundamentals & core syntax",
                        "duration_hours": 0.5,
                    },
                    {
                        "title": "Review OOP principles & inheritance",
                        "duration_hours": 0.5,
                    },
                    {
                        "title": (
                            "Practice Collections framework (List, Set, Map)"
                        ),
                        "duration_hours": 0.5,
                    },
                    {
                        "title": (
                            "Practice Exception handling & edge cases"
                        ),
                        "duration_hours": 0.5,
                    },
                ]
            else:
                subtasks = [
                    {
                        "title": "Review core Java concepts",
                        "duration_hours": 1.0,
                    },
                    {
                        "title": "Practice coding exercises",
                        "duration_hours": 1.0,
                    },
                ]

            tasks.append(
                {
                    "id": len(tasks) + 1,
                    "title": title,
                    "subject": "Java Programming",
                    "type": "ACTIONABLE_TASK",
                    "status": "PENDING",
                    "deadline": deadline,
                    "deadline_text": deadline_text,
                    "duration_hours": duration,
                    "importance": "CRITICAL" if is_exam else "HIGH",
                    "subtasks": subtasks,
                }
            )

        # 3. Project presentation.
        if "presentation" in p_lower:
            if "wednesday" in p_lower:
                deadline_text = "wednesday"
            elif "tomorrow" in p_lower:
                deadline_text = "tomorrow"
            else:
                deadline_text = "in 3 days"

            deadline = IntentAnalyzer.resolve_relative_date(
                deadline_text,
                base_date,
            )

            tasks.append(
                {
                    "id": len(tasks) + 1,
                    "title": "Project Presentation",
                    "subject": "Course Project",
                    "type": "ACTIONABLE_TASK",
                    "status": "PENDING",
                    "deadline": deadline,
                    "deadline_text": deadline_text,
                    "duration_hours": 3.0,
                    "importance": "HIGH",
                    "subtasks": [
                        {
                            "title": (
                                "Prepare presentation structure "
                                "& narrative outline"
                            ),
                            "duration_hours": 0.5,
                        },
                        {
                            "title": (
                                "Prepare slides & architecture diagrams"
                            ),
                            "duration_hours": 1.0,
                        },
                        {
                            "title": (
                                "Practice explanation & demo walkthrough"
                            ),
                            "duration_hours": 1.0,
                        },
                        {
                            "title": (
                                "Final peer review and timing rehearsal"
                            ),
                            "duration_hours": 0.5,
                        },
                    ],
                }
            )

        # 4. Generic exam, if not already captured.
        has_exam_task = any(
            "exam" in task["title"].lower()
            for task in tasks
        )

        if re.search(r"\bexam\b", p_lower) and not has_exam_task:
            deadline_text = (
                "monday" if "monday" in p_lower else "in 4 days"
            )

            deadline = IntentAnalyzer.resolve_relative_date(
                deadline_text,
                base_date,
            )

            tasks.append(
                {
                    "id": len(tasks) + 1,
                    "title": "Exam Preparation",
                    "subject": "Academics",
                    "type": "ACTIONABLE_TASK",
                    "status": "PENDING",
                    "deadline": deadline,
                    "deadline_text": deadline_text,
                    "duration_hours": 3.0,
                    "importance": "CRITICAL",
                    "subtasks": [
                        {
                            "title": "Comprehensive syllabus review",
                            "duration_hours": 0.5,
                        },
                        {
                            "title": (
                                "High-yield concept study "
                                "& note condensation"
                            ),
                            "duration_hours": 1.0,
                        },
                        {
                            "title": "Practice problems & active recall",
                            "duration_hours": 1.0,
                        },
                        {
                            "title": (
                                "Timed mock test & performance assessment"
                            ),
                            "duration_hours": 0.5,
                        },
                    ],
                }
            )

        # 5. Generic actionable tasks.
        if not tasks:
            clauses = re.split(
                r"\band\b|[,;]",
                prompt,
                flags=re.IGNORECASE,
            )

            for clause in clauses:
                clean_clause = clause.strip()
                clean_lower = clean_clause.lower()

                is_fixed_event = (
                    any(
                        keyword in clean_lower
                        for keyword in IntentAnalyzer.FIXED_EVENT_KEYWORDS
                    )
                    and IntentAnalyzer.parse_time_string(clean_clause)
                )

                if is_fixed_event:
                    continue

                has_action = re.search(
                    r"\b(study|prepare|work|finish|complete|write|"
                    r"do|assignment|project|exam|lab)\b",
                    clean_lower,
                )

                if not has_action:
                    continue

                duration_match = re.search(
                    r"\bfor\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
                    clean_lower,
                )

                duration = (
                    float(duration_match.group(1))
                    if duration_match
                    else 2.0
                )

                deadline_text = (
                    "tomorrow"
                    if "tomorrow" in clean_lower
                    else "in 2 days"
                )

                deadline = IntentAnalyzer.resolve_relative_date(
                    deadline_text,
                    base_date,
                )

                title = clean_clause.capitalize()[:50]

                tasks.append(
                    {
                        "id": len(tasks) + 1,
                        "title": title,
                        "subject": "General",
                        "type": "ACTIONABLE_TASK",
                        "status": "PENDING",
                        "deadline": deadline,
                        "deadline_text": deadline_text,
                        "duration_hours": duration,
                        "importance": "MEDIUM",
                        "subtasks": [
                            {
                                "title": (
                                    f"Review requirements for {title[:25]}"
                                ),
                                "duration_hours": 0.5,
                            },
                            {
                                "title": (
                                    f"Implement core deliverables for "
                                    f"{title[:25]}"
                                ),
                                "duration_hours": 1.0,
                            },
                            {
                                "title": (
                                    f"Verify and finalize {title[:25]}"
                                ),
                                "duration_hours": 0.5,
                            },
                        ],
                    }
                )

        return tasks

    @staticmethod
    def calculate_end_time(start_time, duration_hours):
        """Calculate the end time of an event given its start and duration."""
        start_hour, start_minute = map(int, start_time.split(":"))
        total_minutes = start_hour * 60 + start_minute
        total_minutes += round(duration_hours * 60)
        total_minutes %= 24 * 60

        end_hour, end_minute = divmod(total_minutes, 60)
        return f"{end_hour:02d}:{end_minute:02d}"