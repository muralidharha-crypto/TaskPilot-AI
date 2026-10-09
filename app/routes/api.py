import logging

from flask import Blueprint, jsonify, request

from app.models.database import Database
from app.services.agent import AgentService
from app.services.replanner import ReplannerService
from app.services.research_service import ResearchService
from app.tools.monitor_tool import MonitorTool
from app.tools.planner_tool import PlannerTool
from app.tools.scheduler_tool import SchedulerTool
from app.tools.task_tool import TaskTool

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# --- Shared Helpers ---


def _handle_api_error(operation):
    """Log an unexpected API failure and return a safe error response."""
    logger.exception("Unexpected error during API operation: %s", operation)
    return jsonify({"error": "An internal server error occurred."}), 500


def _get_json_object():
    """Return a JSON object or a 400 response for invalid request bodies."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, (jsonify({"error": "Request body must be a JSON object"}), 400)

    return data, None


def _get_daily_hours(data):
    """Validate and return the requested daily available hours."""
    try:
        daily_hours = float(data.get("daily_hours", 3.0))
    except (TypeError, ValueError):
        raise ValueError("'daily_hours' must be a valid number") from None

    if not 0 < daily_hours <= 24:
        raise ValueError("'daily_hours' must be greater than 0 and at most 24")

    return daily_hours


# --- Agent Endpoints ---


@api_bp.route("/agent/run", methods=["POST"])
def run_agent():
    """Analyze a natural-language goal and prepare an agent plan."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    goal = data.get("goal", "")

    if not isinstance(goal, str) or not goal.strip():
        return jsonify({"error": "A non-empty 'goal' string is required"}), 400

    try:
        result = AgentService.process_goal(goal.strip())
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("run_agent")


@api_bp.route("/agent/approve", methods=["POST"])
def approve_agent():
    """Execute proposed tool actions after human approval."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    approval_id = data.get("approval_id")

    if not approval_id:
        return jsonify({"error": "'approval_id' is required"}), 400

    try:
        result = AgentService.approve_and_execute(approval_id)
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("approve_agent")


@api_bp.route("/agent/reject", methods=["POST"])
def reject_agent():
    """Reject a proposed agent plan."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    approval_id = data.get("approval_id")
    comments = data.get("comments", "Rejected by user")

    if not approval_id:
        return jsonify({"error": "'approval_id' is required"}), 400

    try:
        result = AgentService.reject_plan(approval_id, comments)
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("reject_agent")


@api_bp.route("/agent/runs", methods=["GET"])
def list_agent_runs():
    """List past and current agent runs."""
    try:
        return jsonify(AgentService.list_runs()), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("list_agent_runs")


@api_bp.route("/agent/runs/<int:run_id>", methods=["GET"])
def get_agent_run(run_id):
    """Retrieve an agent run's execution history and tool calls."""
    try:
        run_data = AgentService.get_run(run_id)

        if not run_data:
            return jsonify({"error": f"Agent run {run_id} not found"}), 404

        return jsonify(run_data), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("get_agent_run")


# --- Task Endpoints ---


@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    """List tasks, optionally filtered by status."""
    try:
        tasks = TaskTool.list_tasks(status=request.args.get("status"))
        return jsonify(tasks), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("list_tasks")


@api_bp.route("/tasks", methods=["POST"])
def create_task():
    """Create a task."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    title = data.get("title", "")

    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "'title' is required"}), 400

    try:
        task = TaskTool.create_task(
            title=title.strip(),
            description=data.get("description", ""),
            priority=data.get("priority", "MEDIUM"),
            priority_score=data.get("priority_score", 50.0),
            deadline=data.get("deadline"),
            duration_hours=data.get("duration_hours", 1.0),
            dependencies=data.get("dependencies", []),
            subtasks=data.get("subtasks", []),
        )
        return jsonify(task), 201
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("create_task")


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """Retrieve a task by ID."""
    try:
        task = TaskTool.get_task(task_id)

        if not task:
            return jsonify({"error": f"Task {task_id} not found"}), 404

        return jsonify(task), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("get_task")


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    """Update an existing task."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    try:
        task = TaskTool.update_task(
            task_id=task_id,
            title=data.get("title"),
            description=data.get("description"),
            priority=data.get("priority"),
            priority_score=data.get("priority_score"),
            deadline=data.get("deadline"),
            duration_hours=data.get("duration_hours"),
            status=data.get("status"),
        )
        return jsonify(task), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("update_task")


@api_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    """Mark a task as complete."""
    try:
        result = TaskTool.complete_task(task_id)
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("complete_task")


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    """Delete a task."""
    try:
        result = TaskTool.delete_task(task_id)
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("delete_task")


# --- Schedule Endpoints ---


@api_bp.route("/schedule", methods=["GET"])
def get_schedule():
    """Retrieve schedules, optionally filtered by date or task."""
    try:
        schedules = SchedulerTool.get_schedule(
            date_str=request.args.get("date"),
            task_id=request.args.get("task_id"),
        )
        return jsonify(schedules), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("get_schedule")


# --- Planner Endpoints ---


@api_bp.route("/planner/generate", methods=["POST"])
def generate_plan():
    """Generate a study plan."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    try:
        daily_hours = _get_daily_hours(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    try:
        plan = PlannerTool.generate_plan(daily_hours=daily_hours)
        return jsonify(plan), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("generate_plan")


@api_bp.route("/planner/replan", methods=["POST"])
def trigger_replan():
    """Manually trigger replanning."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    reason = data.get("reason", "Manual replan requested")

    try:
        daily_hours = _get_daily_hours(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    try:
        result = ReplannerService.simulate_delay_and_replan(
            reason=reason,
            daily_hours=daily_hours,
        )
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("trigger_replan")


@api_bp.route("/planner/simulate-delay", methods=["POST"])
def simulate_delay():
    """Simulate a missed study session and replan."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    reason = data.get("reason", "I couldn't study today")
    target_date = data.get("date")

    try:
        daily_hours = _get_daily_hours(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    try:
        result = ReplannerService.simulate_delay_and_replan(
            reason=reason,
            target_date=target_date,
            daily_hours=daily_hours,
        )
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("simulate_delay")


# --- Research Endpoint ---


@api_bp.route("/research", methods=["POST"])
def run_research():
    """Research a topic and return the results."""
    data, error_response = _get_json_object()
    if error_response:
        return error_response

    topic = data.get("topic", "")

    if not isinstance(topic, str) or not topic.strip():
        return jsonify({"error": "'topic' is required"}), 400

    try:
        result = ResearchService.run_research(topic.strip())
        return jsonify(result), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("run_research")


# --- Monitoring and Analytics ---


@api_bp.route("/analytics", methods=["GET"])
def get_analytics():
    """Return progress, conflicts, and overdue tasks."""
    try:
        return jsonify(
            {
                "progress": MonitorTool.get_progress(),
                "conflicts": MonitorTool.detect_conflict(),
                "overdue_tasks": MonitorTool.detect_overdue_tasks(),
            }
        ), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("get_analytics")


# --- Demo and Seeding Endpoints ---


@api_bp.route("/demo/seed", methods=["POST"])
def seed_demo():
    """Seed the TaskPilot AI demonstration scenario."""
    scenario_prompt = (
        "I have a Java exam on Monday, DBMS assignment due tomorrow, "
        "and project presentation on Wednesday. I have 3 hours available every evening. "
        "Create a study plan."
    )

    try:
        result = AgentService.process_goal(scenario_prompt)

        return jsonify(
            {
                "message": "Demo goal initialized successfully. Ready for Human Approval.",
                "prompt": scenario_prompt,
                "result": result,
            }
        ), 200
    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        return _handle_api_error("seed_demo")


@api_bp.route("/demo/reset", methods=["POST"])
def reset_db():
    """Clear application data tables for clean testing."""
    conn = None

    try:
        conn = Database.get_connection()

        tables = (
            "schedules",
            "subtasks",
            "tasks",
            "plans",
            "agent_runs",
            "tool_calls",
            "approvals",
            "conflicts",
            "research_queries",
        )

        for table in tables:
            conn.execute(f"DELETE FROM {table}")

        conn.commit()
        return jsonify({"status": "Database cleared successfully"}), 200

    except Exception:  # noqa: BLE001 — HTTP boundary handles unexpected failures.
        if conn is not None:
            conn.rollback()
        return _handle_api_error("reset_db")

    finally:
        if conn is not None:
            conn.close()