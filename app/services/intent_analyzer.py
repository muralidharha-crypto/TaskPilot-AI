import re
import json
from datetime import datetime, date, timedelta
from app.config import Config


class IntentAnalyzer:

    WEEKDAYS = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }

    FIXED_EVENT_KEYWORDS = [
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
        "flight"
    ]

    # ---------------------------------------------------------
    # DATE PARSING
    # ---------------------------------------------------------

    @staticmethod
    def resolve_relative_date(text_reference, base_date=None):
        """
        Converts phrases such as:

            today
            tomorrow
            Monday
            in 3 days
            2026-10-12

        into YYYY-MM-DD.
        """

        if not base_date:
            base_date = date.today()

        ref = text_reference.lower().strip()

        if "day after tomorrow" in ref:
            return (
                base_date + timedelta(days=2)
            ).isoformat()

        if "tomorrow" in ref:
            return (
                base_date + timedelta(days=1)
            ).isoformat()

        if "today" in ref:
            return base_date.isoformat()

        # Explicit ISO date
        iso_match = re.search(
            r"\b(\d{4}-\d{2}-\d{2})\b",
            ref
        )

        if iso_match:
            return iso_match.group(1)

        # "in X days"
        days_match = re.search(
            r"\bin\s+(\d+)\s+days?\b",
            ref
        )

        if days_match:

            days = int(
                days_match.group(1)
            )

            return (
                base_date + timedelta(days=days)
            ).isoformat()

        # Weekday
        for day_name, day_idx in IntentAnalyzer.WEEKDAYS.items():

            if re.search(
                rf"\b{day_name}\b",
                ref
            ):

                current_day_idx = base_date.weekday()

                days_ahead = (
                    day_idx - current_day_idx
                ) % 7

                # If the user explicitly says a weekday
                # and it is today, interpret it as next week.
                if days_ahead == 0:
                    days_ahead = 7

                return (
                    base_date
                    + timedelta(days=days_ahead)
                ).isoformat()

        # Default
        return (
            base_date + timedelta(days=1)
        ).isoformat()

    # ---------------------------------------------------------
    # DURATION EXTRACTION
    # ---------------------------------------------------------

    @staticmethod
    def extract_duration_hours(text, default=None):
        """
        Extracts an explicit duration from natural language.

        Examples:

            "I need 2 hours"
            "for 3 hours"
            "takes 1.5 hours"
            "need 90 minutes"

        Returns:
            float hours or default.
        """

        # Hours
        hour_patterns = [
            r"\b(\d+(?:\.\d+)?)\s*hours?\b",
            r"\b(\d+(?:\.\d+)?)\s*hrs?\b"
        ]

        for pattern in hour_patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:
                return float(
                    match.group(1)
                )

        # Minutes
        minute_match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*minutes?\b",
            text,
            re.IGNORECASE
        )

        if minute_match:

            minutes = float(
                minute_match.group(1)
            )

            return round(
                minutes / 60.0,
                2
            )

        return default

    # ---------------------------------------------------------
    # SUBTASK GENERATION
    # ---------------------------------------------------------

    @staticmethod
    def _build_dbms_subtasks(total_hours):
        """
        Creates DBMS subtasks whose total duration exactly
        matches the requested duration.

        For example:

            2 hours

            0.5h requirements
            0.5h ER/schema
            0.5h SQL/normalization
            0.5h review

        For 3 hours:

            0.5h requirements
            0.5h ER/schema
            1.0h SQL/normalization
            0.5h verification
            0.5h final review
        """

        total_hours = float(
            total_hours
        )

        if total_hours <= 0:
            total_hours = 1.0

        # -----------------------------------------------------
        # Short task: <= 1 hour
        # -----------------------------------------------------

        if total_hours <= 1.0:

            return [
                {
                    "title": (
                        "Review requirements and "
                        "complete DBMS work"
                    ),
                    "duration_hours": round(
                        total_hours,
                        2
                    )
                }
            ]

        # -----------------------------------------------------
        # 1 - 2 hours
        # -----------------------------------------------------

        if total_hours <= 2.0:

            first = min(
                0.5,
                total_hours
            )

            remaining = total_hours - first

            second = min(
                0.5,
                remaining
            )

            remaining -= second

            third = min(
                0.5,
                remaining
            )

            remaining -= third

            fourth = max(
                0.0,
                remaining
            )

            subtasks = []

            if first > 0:
                subtasks.append({
                    "title": (
                        "Understand assignment "
                        "requirements"
                    ),
                    "duration_hours": round(
                        first,
                        2
                    )
                })

            if second > 0:
                subtasks.append({
                    "title": (
                        "Review ER diagram, "
                        "schema and constraints"
                    ),
                    "duration_hours": round(
                        second,
                        2
                    )
                })

            if third > 0:
                subtasks.append({
                    "title": (
                        "Write SQL queries "
                        "and normalization solution"
                    ),
                    "duration_hours": round(
                        third,
                        2
                    )
                })

            if fourth > 0:
                subtasks.append({
                    "title": (
                        "Verify, review and "
                        "finalize submission"
                    ),
                    "duration_hours": round(
                        fourth,
                        2
                    )
                })

            return subtasks

        # -----------------------------------------------------
        # More than 2 hours
        # -----------------------------------------------------

        base_subtasks = [
            (
                "Understand assignment "
                "requirements & schema design",
                0.5
            ),
            (
                "Draft ER diagram and "
                "identify constraints",
                0.5
            ),
            (
                "Write SQL queries and "
                "normalization solution",
                1.0
            ),
            (
                "Verify results and "
                "query execution plan",
                0.5
            ),
            (
                "Review, format check & submit",
                0.5
            )
        ]

        base_total = sum(
            duration
            for _, duration
            in base_subtasks
        )

        # If requested duration is exactly 3h,
        # use the standard breakdown.
        if abs(total_hours - base_total) < 0.001:

            return [
                {
                    "title": title,
                    "duration_hours": duration
                }
                for title, duration
                in base_subtasks
            ]

        # For durations greater than 3h,
        # preserve the normal breakdown and add
        # the remaining time to SQL/practical work.
        extra = total_hours - base_total

        result = []

        for title, duration in base_subtasks:

            if (
                "SQL queries" in title
                and extra > 0
            ):
                duration += extra
                extra = 0

            result.append({
                "title": title,
                "duration_hours": round(
                    duration,
                    2
                )
            })

        return result

    # ---------------------------------------------------------
    # TIME PARSING
    # ---------------------------------------------------------

    @staticmethod
    def parse_time_string(text):
        """
        Extract a reliable time from phrases such as:

            6 PM
            7:30 PM
            at 7 PM
            18:00
            07:30
            at 6
        """

        patterns = [

            r"\b(?:at\s+)?"
            r"(\d{1,2}):(\d{2})\s*"
            r"(am|pm)?\b",

            r"\b(?:at\s+)?"
            r"(\d{1,2})\s*"
            r"(am|pm)\b",

            r"\b(?:at\s+)"
            r"(\d{1,2})\b"
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if not match:
                continue

            hour = int(
                match.group(1)
            )

            minute = 0

            meridiem = ""

            if match.lastindex >= 2:

                group2 = match.group(2)

                if group2:

                    if group2.lower() in (
                        "am",
                        "pm"
                    ):
                        meridiem = (
                            group2.lower()
                        )

                    else:
                        minute = int(
                            group2
                        )

            if match.lastindex >= 3:

                group3 = match.group(3)

                if group3:
                    meridiem = (
                        group3.lower()
                    )

            if hour > 23 or minute > 59:
                continue

            if (
                meridiem == "pm"
                and hour < 12
            ):
                hour += 12

            elif (
                meridiem == "am"
                and hour == 12
            ):
                hour = 0

            elif (
                not meridiem
                and hour < 7
            ):
                # "at 6" → 18:00
                hour += 12

            return (
                f"{hour:02d}:{minute:02d}"
            )

        return None

    # ---------------------------------------------------------
    # END TIME
    # ---------------------------------------------------------

    @staticmethod
    def calculate_end_time(
        start_str,
        duration_hours=1.0
    ):
        """
        Calculates the end time from a start time
        and duration.
        """

        h, m = map(
            int,
            start_str.split(":")
        )

        total_minutes = (
            h * 60
            + m
            + int(
                float(duration_hours)
                * 60
            )
        )

        end_h = (
            total_minutes // 60
        ) % 24

        end_m = (
            total_minutes % 60
        )

        return (
            f"{end_h:02d}:{end_m:02d}"
        )

    # ---------------------------------------------------------
    # MAIN INTENT ANALYSIS
    # ---------------------------------------------------------

    @staticmethod
    def analyze(user_prompt):

        prompt = user_prompt.strip()

        p_lower = prompt.lower()

        # -----------------------------------------------------
        # 1. REPLANNING
        # -----------------------------------------------------

        if re.search(
            r"\b("
            r"couldn't study|"
            r"could not study|"
            r"didn't study|"
            r"missed study|"
            r"cancel today|"
            r"reschedule today|"
            r"fell behind"
            r")\b",
            p_lower
        ):

            return {
                "intent": "REPLANNING_REQUEST",
                "goal": prompt,
                "reason": prompt,
                "summary": (
                    "Detected schedule disruption requiring "
                    "autonomous conflict detection and replanning."
                )
            }

        # -----------------------------------------------------
        # 2. RESEARCH REQUEST
        # -----------------------------------------------------

        research_pattern = (
            r"^(?:"
            r"tell\s+me\s+about|"
            r"what\s+is|"
            r"what\s+are|"
            r"explain|"
            r"overview\s+of|"
            r"research\b|"
            r"explore\b|"
            r"how\s+does|"
            r"pros\s+and\s+cons|"
            r"advantages\s+and\s+disadvantages"
            r")"
        )

        if re.search(
            research_pattern,
            p_lower
        ) or (
            re.search(
                r"\b("
                r"research|"
                r"literature|"
                r"investigate"
                r")\b",
                p_lower
            )
            and not re.search(
                r"\b("
                r"due|"
                r"exam|"
                r"assignment|"
                r"class|"
                r"tutoring"
                r")\b",
                p_lower
            )
        ):

            clean_topic = re.sub(
                r"^(?:"
                r"tell\s+me\s+about\s+(?:the\s+)?|"
                r"what\s+is\s+(?:the\s+)?|"
                r"what\s+are\s+(?:the\s+)?|"
                r"explain\s+(?:the\s+)?|"
                r"overview\s+of\s+(?:the\s+)?|"
                r"research\s+(?:on\s+|about\s+|the\s+)?|"
                r"research\s+the\s+advantages\s+and\s+disadvantages\s+of\s+"
                r")",
                "",
                prompt,
                flags=re.IGNORECASE
            ).strip(" ?.")

            return {
                "intent": "RESEARCH_REQUEST",
                "goal": prompt,
                "topic": clean_topic,
                "summary": (
                    "Identified academic/factual research "
                    f"inquiry on: '{clean_topic}'."
                )
            }

        # -----------------------------------------------------
        # 3. PLANNING / EVENT EXTRACTION
        # -----------------------------------------------------

        base_date = date.today()

        # Daily available hours
        hours_match = re.search(
            r"(\d+(?:\.\d+)?)\s*"
            r"(?:hours?|hrs?)\s*"
            r"(?:available|free|every\s*evening|per\s*day|daily)?",
            p_lower
        )

        daily_hours = (
            float(
                hours_match.group(1)
            )
            if hours_match
            else Config.DEFAULT_EVENING_HOURS
        )

        fixed_events = (
            IntentAnalyzer._extract_fixed_events(
                prompt,
                base_date
            )
        )

        actionable_tasks = (
            IntentAnalyzer._extract_actionable_tasks(
                prompt,
                base_date
            )
        )

        # -----------------------------------------------------
        # 4. MASTER CLASSIFICATION
        # -----------------------------------------------------

        if fixed_events and actionable_tasks:

            intent = "MIXED_REQUEST"

        elif fixed_events:

            intent = "FIXED_EVENT"

        else:

            intent = "ACTIONABLE_TASK"

        total_workload = sum(
            task["duration_hours"]
            for task in actionable_tasks
        )

        return {

            "intent": intent,

            "goal": prompt,

            "fixed_events": fixed_events,

            "detected_tasks": actionable_tasks,

            "total_tasks": len(
                actionable_tasks
            ),

            "total_fixed_events": len(
                fixed_events
            ),

            "total_estimated_hours": total_workload,

            "constraints": {

                "daily_hours": daily_hours,

                "schedule_timing": (
                    "evening (6:00 PM - 9:00 PM)"
                ),

                "fixed_event_blocks": len(
                    fixed_events
                )
            },

            "summary": (
                f"Classified as {intent}: "
                f"{len(fixed_events)} fixed event(s) and "
                f"{len(actionable_tasks)} actionable task(s) detected."
            )
        }

    # ---------------------------------------------------------
    # FIXED EVENT EXTRACTION
    # ---------------------------------------------------------

    @staticmethod
    def _extract_fixed_events(
        prompt,
        base_date
    ):

        events = []

        clauses = re.split(
            r"\band\b|[,;]",
            prompt,
            flags=re.IGNORECASE
        )

        for clause in clauses:

            c = clause.strip()

            if not c:
                continue

            c_lower = c.lower()

            time_str = (
                IntentAnalyzer.parse_time_string(c)
            )

            is_fixed = (
                any(
                    re.search(
                        rf"\b{re.escape(keyword)}\b",
                        c_lower
                    )
                    for keyword
                    in IntentAnalyzer.FIXED_EVENT_KEYWORDS
                )
                and time_str is not None
            )

            if not is_fixed:
                continue

            # -------------------------------------------------
            # Title
            # -------------------------------------------------

            title = "Fixed Event"

            if "tutoring" in c_lower:
                title = "Tutoring Class"

            elif "lecture" in c_lower:
                title = "Lecture"

            elif "lab" in c_lower:
                title = "Lab"

            elif "meeting" in c_lower:
                title = "Meeting"

            elif "appointment" in c_lower:
                title = "Appointment"

            elif "interview" in c_lower:
                title = "Interview"

            elif "webinar" in c_lower:
                title = "Webinar"

            elif "seminar" in c_lower:
                title = "Seminar"

            elif "class" in c_lower:
                title = "Class"

            elif "call" in c_lower:
                title = "Call"

            elif "travel" in c_lower:
                title = "Travel"

            elif "flight" in c_lower:
                title = "Flight"

            # -------------------------------------------------
            # Duration
            # -------------------------------------------------

            duration = (
                IntentAnalyzer.extract_duration_hours(
                    c_lower,
                    default=None
                )
            )

            # Do not accidentally use the user's task duration
            # as the event duration.
            if duration is None:
                duration = 1.0

            # -------------------------------------------------
            # Date
            # -------------------------------------------------

            if "day after tomorrow" in c_lower:

                event_date = (
                    IntentAnalyzer.resolve_relative_date(
                        "day after tomorrow",
                        base_date
                    )
                )

            elif "tomorrow" in c_lower:

                event_date = (
                    IntentAnalyzer.resolve_relative_date(
                        "tomorrow",
                        base_date
                    )
                )

            else:

                event_date = base_date.isoformat()

                for weekday in IntentAnalyzer.WEEKDAYS:

                    if re.search(
                        rf"\b{weekday}\b",
                        c_lower
                    ):

                        event_date = (
                            IntentAnalyzer.resolve_relative_date(
                                weekday,
                                base_date
                            )
                        )

                        break

            end_time = (
                IntentAnalyzer.calculate_end_time(
                    time_str,
                    duration
                )
            )

            events.append({

                "id": len(events) + 1,

                "title": title,

                "event_type": "FIXED_EVENT",

                "date_str": event_date,

                "start_time": time_str,

                "end_time": end_time,

                "duration_hours": duration,

                "subtasks": [],

                "notes": (
                    f"Fixed commitment ({title})"
                ),

                "blocks_schedule": True,

                "is_actionable": False
            })

        return events

    # ---------------------------------------------------------
    # ACTIONABLE TASK EXTRACTION
    # ---------------------------------------------------------

    @staticmethod
    def _extract_actionable_tasks(
        prompt,
        base_date
    ):

        tasks = []

        p_lower = prompt.lower()

        # -----------------------------------------------------
        # DBMS ASSIGNMENT
        # -----------------------------------------------------

        if "dbms" in p_lower:

            # -----------------------------------------------
            # Deadline
            # -----------------------------------------------

            if "day after tomorrow" in p_lower:

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "day after tomorrow",
                        base_date
                    )
                )

                deadline_text = (
                    "day after tomorrow"
                )

            elif "tomorrow" in p_lower:

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "tomorrow",
                        base_date
                    )
                )

                deadline_text = "tomorrow"

            elif re.search(
                r"\bmonday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "monday",
                        base_date
                    )
                )

                deadline_text = "Monday"

            elif re.search(
                r"\btuesday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "tuesday",
                        base_date
                    )
                )

                deadline_text = "Tuesday"

            elif re.search(
                r"\bwednesday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "wednesday",
                        base_date
                    )
                )

                deadline_text = "Wednesday"

            elif re.search(
                r"\bthursday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "thursday",
                        base_date
                    )
                )

                deadline_text = "Thursday"

            elif re.search(
                r"\bfriday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "friday",
                        base_date
                    )
                )

                deadline_text = "Friday"

            elif re.search(
                r"\bsaturday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "saturday",
                        base_date
                    )
                )

                deadline_text = "Saturday"

            elif re.search(
                r"\bsunday\b",
                p_lower
            ):

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "sunday",
                        base_date
                    )
                )

                deadline_text = "Sunday"

            else:

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "in 2 days",
                        base_date
                    )
                )

                deadline_text = "2 days"

            # -----------------------------------------------
            # Explicit workload
            # -----------------------------------------------

            requested_duration = (
                IntentAnalyzer.extract_duration_hours(
                    p_lower,
                    default=None
                )
            )

            if requested_duration is None:

                requested_duration = 3.0

            # -----------------------------------------------
            # DBMS subtasks
            # -----------------------------------------------

            subtasks = (
                IntentAnalyzer._build_dbms_subtasks(
                    requested_duration
                )
            )

            # Make absolutely sure the task duration equals
            # the sum of its subtasks.
            actual_duration = round(
                sum(
                    float(
                        st["duration_hours"]
                    )
                    for st in subtasks
                ),
                2
            )

            tasks.append({

                "id": len(tasks) + 1,

                "title": "DBMS Assignment",

                "subject": (
                    "Database Management Systems"
                ),

                "type": "ACTIONABLE_TASK",

                "event_type": "TASK_STUDY",

                "status": "PENDING",

                "deadline": deadline,

                "deadline_text": deadline_text,

                "duration_hours": actual_duration,

                "importance": "HIGH",

                "subtasks": subtasks
            })

        # -----------------------------------------------------
        # JAVA
        # -----------------------------------------------------

        if "java" in p_lower:

            is_exam = (
                "exam" in p_lower
                or "test" in p_lower
            )

            deadline = (
                IntentAnalyzer.resolve_relative_date(
                    "monday"
                    if "monday" in p_lower
                    else "tomorrow",
                    base_date
                )
            )

            duration_match = re.search(
                r"(?:java.*?for|for)\s+"
                r"(\d+(?:\.\d+)?)\s*"
                r"(?:hours?|hrs?)",
                p_lower
            )

            duration = (
                float(
                    duration_match.group(1)
                )
                if duration_match
                else (
                    4.0
                    if is_exam
                    else 2.0
                )
            )

            title = (
                "Java Exam Preparation"
                if is_exam
                else "Java Study"
            )

            if is_exam:

                subtasks = [

                    {
                        "title": (
                            "Review Java fundamentals "
                            "& core syntax"
                        ),
                        "duration_hours": 0.5
                    },

                    {
                        "title": (
                            "Review OOP principles "
                            "& inheritance"
                        ),
                        "duration_hours": 0.5
                    },

                    {
                        "title": (
                            "Practice Collections framework "
                            "(List, Set, Map)"
                        ),
                        "duration_hours": 0.5
                    },

                    {
                        "title": (
                            "Practice Exception handling "
                            "& edge cases"
                        ),
                        "duration_hours": 0.5
                    }
                ]

            else:

                subtasks = [

                    {
                        "title": "Review core Java concepts",
                        "duration_hours": 1.0
                    },

                    {
                        "title": "Practice coding exercises",
                        "duration_hours": 1.0
                    }
                ]

            tasks.append({

                "id": len(tasks) + 1,

                "title": title,

                "subject": "Java Programming",

                "type": "ACTIONABLE_TASK",

                "event_type": "TASK_STUDY",

                "status": "PENDING",

                "deadline": deadline,

                "deadline_text": (
                    "Monday"
                    if "monday" in p_lower
                    else "soon"
                ),

                "duration_hours": duration,

                "importance": (
                    "CRITICAL"
                    if is_exam
                    else "HIGH"
                ),

                "subtasks": subtasks
            })

        # -----------------------------------------------------
        # PROJECT PRESENTATION
        # -----------------------------------------------------

        if (
            "presentation" in p_lower
            or "project presentation" in p_lower
        ):

            deadline = (
                IntentAnalyzer.resolve_relative_date(
                    "wednesday"
                    if "wednesday" in p_lower
                    else "in 3 days",
                    base_date
                )
            )

            tasks.append({

                "id": len(tasks) + 1,

                "title": "Project Presentation",

                "subject": "Course Project",

                "type": "ACTIONABLE_TASK",

                "event_type": "TASK_STUDY",

                "status": "PENDING",

                "deadline": deadline,

                "deadline_text": "Wednesday",

                "duration_hours": 3.0,

                "importance": "HIGH",

                "subtasks": [

                    {
                        "title": (
                            "Prepare presentation structure "
                            "& narrative outline"
                        ),
                        "duration_hours": 0.5
                    },

                    {
                        "title": (
                            "Prepare slides & "
                            "architecture diagrams"
                        ),
                        "duration_hours": 1.0
                    },

                    {
                        "title": (
                            "Practice explanation "
                            "& demo walkthrough"
                        ),
                        "duration_hours": 1.0
                    },

                    {
                        "title": (
                            "Final peer review and "
                            "timing rehearsal"
                        ),
                        "duration_hours": 0.5
                    }
                ]
            })

        # -----------------------------------------------------
        # GENERIC EXAM
        # -----------------------------------------------------

        if (
            "exam" in p_lower
            and not any(
                "exam" in task["title"].lower()
                for task in tasks
            )
        ):

            deadline = (
                IntentAnalyzer.resolve_relative_date(
                    "monday"
                    if "monday" in p_lower
                    else "in 4 days",
                    base_date
                )
            )

            tasks.append({

                "id": len(tasks) + 1,

                "title": "Exam Preparation",

                "subject": "Academics",

                "type": "ACTIONABLE_TASK",

                "event_type": "TASK_STUDY",

                "status": "PENDING",

                "deadline": deadline,

                "deadline_text": "Monday",

                "duration_hours": 3.0,

                "importance": "CRITICAL",

                "subtasks": [

                    {
                        "title": (
                            "Comprehensive syllabus review"
                        ),
                        "duration_hours": 0.5
                    },

                    {
                        "title": (
                            "High-yield concept study "
                            "& note condensation"
                        ),
                        "duration_hours": 1.0
                    },

                    {
                        "title": (
                            "Practice problems "
                            "& active recall"
                        ),
                        "duration_hours": 1.0
                    },

                    {
                        "title": (
                            "Timed mock test "
                            "& performance assessment"
                        ),
                        "duration_hours": 0.5
                    }
                ]
            })

        # -----------------------------------------------------
        # GENERIC ACTIONABLE TASKS
        # -----------------------------------------------------

        if not tasks:

            clauses = re.split(
                r"\band\b|[,;]",
                prompt,
                flags=re.IGNORECASE
            )

            for clause in clauses:

                clean_clause = clause.strip()

                if not clean_clause:
                    continue

                clean_lower = (
                    clean_clause.lower()
                )

                # Ignore fixed events
                is_fixed = (
                    any(
                        re.search(
                            rf"\b{re.escape(keyword)}\b",
                            clean_lower
                        )
                        for keyword
                        in IntentAnalyzer.FIXED_EVENT_KEYWORDS
                    )
                    and IntentAnalyzer.parse_time_string(
                        clean_clause
                    )
                )

                if is_fixed:
                    continue

                # Actionable language
                if not re.search(
                    r"\b("
                    r"study|"
                    r"prepare|"
                    r"work|"
                    r"finish|"
                    r"complete|"
                    r"write|"
                    r"do|"
                    r"assignment|"
                    r"project|"
                    r"exam|"
                    r"lab"
                    r")\b",
                    clean_lower
                ):
                    continue

                duration = (
                    IntentAnalyzer.extract_duration_hours(
                        clean_lower,
                        default=2.0
                    )
                )

                deadline = (
                    IntentAnalyzer.resolve_relative_date(
                        "tomorrow"
                        if "tomorrow" in clean_lower
                        else "in 2 days",
                        base_date
                    )
                )

                title = (
                    clean_clause.capitalize()
                )[:50]

                tasks.append({

                    "id": len(tasks) + 1,

                    "title": title,

                    "subject": "General",

                    "type": "ACTIONABLE_TASK",

                    "event_type": "TASK_STUDY",

                    "status": "PENDING",

                    "deadline": deadline,

                    "deadline_text": "flexible",

                    "duration_hours": duration,

                    "importance": "MEDIUM",

                    "subtasks": [

                        {
                            "title": (
                                f"Review requirements for "
                                f"{title[:25]}"
                            ),
                            "duration_hours": 0.5
                        },

                        {
                            "title": (
                                f"Implement core deliverables "
                                f"for {title[:25]}"
                            ),
                            "duration_hours": 1.0
                        },

                        {
                            "title": (
                                f"Verify and finalize "
                                f"{title[:25]}"
                            ),
                            "duration_hours": 0.5
                        }
                    ]
                })

        return tasks