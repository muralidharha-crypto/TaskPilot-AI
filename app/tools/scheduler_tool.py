from datetime import datetime
from app.models.database import Database


class SchedulerTool:

    @staticmethod
    def create_schedule(
        title,
        date_str,
        start_time,
        end_time,
        duration_hours=1.0,
        task_id=None,
        notes=None,
        event_type="TASK_STUDY"
    ):
        """
        Creates an idempotent schedule entry.

        Supported event types:
            TASK_STUDY
            FIXED_EVENT

        FIXED_EVENT:
            - Represents a real-world commitment.
            - Blocks that time in the planner.
            - Is never converted into a study task.
            - Can exist without a task_id.
        """

        # ---------------------------------------------------------
        # VALIDATION
        # ---------------------------------------------------------

        if not title:
            raise ValueError("Title is required")

        if not date_str:
            raise ValueError("date_str is required")

        if not start_time:
            raise ValueError("start_time is required")

        if not end_time:
            raise ValueError("end_time is required")

        clean_title = title.strip()

        if not clean_title:
            raise ValueError("Title cannot be empty")

        # ---------------------------------------------------------
        # NORMALIZE EVENT TYPE
        # ---------------------------------------------------------

        event_type = (
            event_type or "TASK_STUDY"
        ).strip().upper()

        allowed_event_types = {
            "TASK_STUDY",
            "FIXED_EVENT"
        }

        if event_type not in allowed_event_types:
            event_type = "TASK_STUDY"

        # Fixed events should not accidentally receive a task ID.
        if event_type == "FIXED_EVENT":
            task_id = None

        try:
            duration_hours = float(duration_hours)
        except (TypeError, ValueError):
            duration_hours = 1.0

        if duration_hours <= 0:
            duration_hours = 1.0

        now = datetime.now().isoformat()

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            # -----------------------------------------------------
            # 1. DUPLICATE DETECTION
            # -----------------------------------------------------
            #
            # For fixed events:
            #
            # date + start + end + title + FIXED_EVENT
            #
            # For task schedules:
            #
            # same task + same date + start time
            #
            # This prevents repeated planner/API calls from
            # creating duplicate calendar entries.
            # -----------------------------------------------------

            if event_type == "FIXED_EVENT":

                cursor.execute(
                    """
                    SELECT *
                    FROM schedules
                    WHERE date_str = ?
                      AND start_time = ?
                      AND end_time = ?
                      AND title = ?
                      AND event_type = 'FIXED_EVENT'
                    LIMIT 1
                    """,
                    (
                        date_str,
                        start_time,
                        end_time,
                        clean_title
                    )
                )

            elif task_id is not None:

                cursor.execute(
                    """
                    SELECT *
                    FROM schedules
                    WHERE task_id = ?
                      AND date_str = ?
                      AND start_time = ?
                      AND event_type = 'TASK_STUDY'
                    LIMIT 1
                    """,
                    (
                        task_id,
                        date_str,
                        start_time
                    )
                )

            else:

                cursor.execute(
                    """
                    SELECT *
                    FROM schedules
                    WHERE date_str = ?
                      AND start_time = ?
                      AND end_time = ?
                      AND title = ?
                      AND event_type = 'TASK_STUDY'
                    LIMIT 1
                    """,
                    (
                        date_str,
                        start_time,
                        end_time,
                        clean_title
                    )
                )

            existing = cursor.fetchone()

            # -----------------------------------------------------
            # 2. UPDATE EXISTING ENTRY
            # -----------------------------------------------------

            if existing:

                existing_dict = dict(existing)

                schedule_id = existing_dict["id"]

                cursor.execute(
                    """
                    UPDATE schedules
                    SET
                        title = ?,
                        end_time = ?,
                        duration_hours = ?,
                        task_id = ?,
                        event_type = ?,
                        notes = ?,
                        status = 'SCHEDULED'
                    WHERE id = ?
                    """,
                    (
                        clean_title,
                        end_time,
                        duration_hours,
                        task_id,
                        event_type,
                        notes,
                        schedule_id
                    )
                )

                conn.commit()

                return SchedulerTool.get_schedule_by_id(
                    schedule_id
                )

            # -----------------------------------------------------
            # 3. INSERT NEW ENTRY
            # -----------------------------------------------------

            cursor.execute(
                """
                INSERT INTO schedules (
                    task_id,
                    title,
                    date_str,
                    start_time,
                    end_time,
                    duration_hours,
                    event_type,
                    status,
                    notes,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?, ?)
                """,
                (
                    task_id,
                    clean_title,
                    date_str,
                    start_time,
                    end_time,
                    duration_hours,
                    event_type,
                    notes,
                    now
                )
            )

            schedule_id = cursor.lastrowid

            conn.commit()

            return {
                "id": schedule_id,
                "task_id": task_id,
                "title": clean_title,
                "date_str": date_str,
                "start_time": start_time,
                "end_time": end_time,
                "duration_hours": duration_hours,
                "event_type": event_type,
                "status": "SCHEDULED",
                "notes": notes,
                "created_at": now
            }

        finally:
            conn.close()

    # -------------------------------------------------------------
    # GET ONE SCHEDULE
    # -------------------------------------------------------------

    @staticmethod
    def get_schedule_by_id(schedule_id):

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM schedules
                WHERE id = ?
                """,
                (schedule_id,)
            )

            row = cursor.fetchone()

            return dict(row) if row else None

        finally:
            conn.close()

    # -------------------------------------------------------------
    # UPDATE SCHEDULE
    # -------------------------------------------------------------

    @staticmethod
    def update_schedule(
        schedule_id,
        title=None,
        date_str=None,
        start_time=None,
        end_time=None,
        duration_hours=None,
        status=None,
        notes=None,
        event_type=None
    ):
        """
        Updates an existing schedule entry.

        event_type is optional so existing callers continue
        working without modification.
        """

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM schedules
                WHERE id = ?
                """,
                (schedule_id,)
            )

            row = cursor.fetchone()

            if not row:
                raise ValueError(
                    f"Schedule with ID {schedule_id} not found"
                )

            updates = []
            params = []

            # -----------------------------------------------------
            # TITLE
            # -----------------------------------------------------

            if title is not None:

                updates.append(
                    "title = ?"
                )

                params.append(
                    title.strip()
                )

            # -----------------------------------------------------
            # DATE
            # -----------------------------------------------------

            if date_str is not None:

                updates.append(
                    "date_str = ?"
                )

                params.append(
                    date_str
                )

            # -----------------------------------------------------
            # START
            # -----------------------------------------------------

            if start_time is not None:

                updates.append(
                    "start_time = ?"
                )

                params.append(
                    start_time
                )

            # -----------------------------------------------------
            # END
            # -----------------------------------------------------

            if end_time is not None:

                updates.append(
                    "end_time = ?"
                )

                params.append(
                    end_time
                )

            # -----------------------------------------------------
            # DURATION
            # -----------------------------------------------------

            if duration_hours is not None:

                updates.append(
                    "duration_hours = ?"
                )

                params.append(
                    float(duration_hours)
                )

            # -----------------------------------------------------
            # STATUS
            # -----------------------------------------------------

            if status is not None:

                updates.append(
                    "status = ?"
                )

                params.append(
                    status.upper()
                )

            # -----------------------------------------------------
            # NOTES
            # -----------------------------------------------------

            if notes is not None:

                updates.append(
                    "notes = ?"
                )

                params.append(
                    notes
                )

            # -----------------------------------------------------
            # EVENT TYPE
            # -----------------------------------------------------

            if event_type is not None:

                normalized_event_type = (
                    event_type.upper()
                )

                if normalized_event_type not in {
                    "TASK_STUDY",
                    "FIXED_EVENT"
                }:
                    normalized_event_type = "TASK_STUDY"

                updates.append(
                    "event_type = ?"
                )

                params.append(
                    normalized_event_type
                )

            # Nothing to update.
            if not updates:

                cursor.execute(
                    """
                    SELECT *
                    FROM schedules
                    WHERE id = ?
                    """,
                    (schedule_id,)
                )

                return dict(
                    cursor.fetchone()
                )

            params.append(schedule_id)

            cursor.execute(
                f"""
                UPDATE schedules
                SET {', '.join(updates)}
                WHERE id = ?
                """,
                params
            )

            conn.commit()

            cursor.execute(
                """
                SELECT *
                FROM schedules
                WHERE id = ?
                """,
                (schedule_id,)
            )

            return dict(
                cursor.fetchone()
            )

        finally:
            conn.close()

    # -------------------------------------------------------------
    # REMOVE
    # -------------------------------------------------------------

    @staticmethod
    def remove_schedule(schedule_id):

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM schedules
                WHERE id = ?
                """,
                (schedule_id,)
            )

            conn.commit()

            return {
                "schedule_id": schedule_id,
                "deleted": True
            }

        finally:
            conn.close()

    # -------------------------------------------------------------
    # GET SCHEDULE
    # -------------------------------------------------------------

    @staticmethod
    def get_schedule(
        date_str=None,
        task_id=None,
        event_type=None
    ):
        """
        Returns schedules chronologically.

        Can optionally filter by:
            date
            task
            event type
        """

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            query = """
                SELECT
                    s.*,
                    t.priority,
                    t.deadline
                FROM schedules s
                LEFT JOIN tasks t
                    ON s.task_id = t.id
                WHERE 1=1
            """

            params = []

            # -----------------------------------------------------
            # DATE FILTER
            # -----------------------------------------------------

            if date_str:

                query += """
                    AND s.date_str = ?
                """

                params.append(
                    date_str
                )

            # -----------------------------------------------------
            # TASK FILTER
            # -----------------------------------------------------

            if task_id:

                query += """
                    AND s.task_id = ?
                """

                params.append(
                    task_id
                )

            # -----------------------------------------------------
            # EVENT TYPE FILTER
            # -----------------------------------------------------

            if event_type:

                query += """
                    AND s.event_type = ?
                """

                params.append(
                    event_type.upper()
                )

            # -----------------------------------------------------
            # ORDER
            # -----------------------------------------------------

            query += """
                ORDER BY
                    s.date_str ASC,
                    s.start_time ASC
            """

            cursor.execute(
                query,
                params
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

        finally:
            conn.close()

    # -------------------------------------------------------------
    # MARK MISSED
    # -------------------------------------------------------------

    @staticmethod
    def mark_missed(schedule_id):
        """
        Marks a study schedule as missed.

        Fixed events should generally not be marked as
        missed study sessions.
        """

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT event_type
                FROM schedules
                WHERE id = ?
                """,
                (schedule_id,)
            )

            row = cursor.fetchone()

            if not row:
                raise ValueError(
                    f"Schedule with ID {schedule_id} not found"
                )

            if row["event_type"] == "FIXED_EVENT":

                return SchedulerTool.get_schedule_by_id(
                    schedule_id
                )

        finally:
            conn.close()

        return SchedulerTool.update_schedule(
            schedule_id,
            status="MISSED"
        )

    # -------------------------------------------------------------
    # CLEAR ALL
    # -------------------------------------------------------------

    @staticmethod
    def clear_all_schedules():
        """
        Clears all schedules.

        Used when completely rebuilding the plan.
        """

        conn = Database.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM schedules
                """
            )

            conn.commit()

            return {
                "cleared": True
            }

        finally:
            conn.close()