import json
from flask import Blueprint, request, jsonify
from app.tools.task_tool import TaskTool
from app.tools.scheduler_tool import SchedulerTool
from app.tools.planner_tool import PlannerTool
from app.tools.monitor_tool import MonitorTool
from app.tools.research_tool import ResearchTool
from app.services.agent import AgentService
from app.services.replanner import ReplannerService
from app.services.research_service import ResearchService
from app.models.database import Database

api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- Agent Endpoints ---
@api_bp.route('/agent/run', methods=['POST'])
def run_agent():
    """Receives natural language goal and triggers agent analysis, planning, and approval formulating."""
    data = request.get_json() or {}
    goal = data.get("goal", "").strip()
    if not goal:
        return jsonify({"error": "A non-empty 'goal' string is required"}), 400

    try:
        result = AgentService.process_goal(goal)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/agent/approve', methods=['POST'])
def approve_agent():
    """Human approval endpoint to execute the proposed tool actions."""
    data = request.get_json() or {}
    approval_id = data.get("approval_id")
    if not approval_id:
        return jsonify({"error": "'approval_id' is required"}), 400

    try:
        result = AgentService.approve_and_execute(approval_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/agent/reject', methods=['POST'])
def reject_agent():
    """Human rejection endpoint."""
    data = request.get_json() or {}
    approval_id = data.get("approval_id")
    comments = data.get("comments", "Rejected by user")
    if not approval_id:
        return jsonify({"error": "'approval_id' is required"}), 400

    try:
        result = AgentService.reject_plan(approval_id, comments)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/agent/runs', methods=['GET'])
def list_agent_runs():
    """Lists past and current agent runs."""
    try:
        runs = AgentService.list_runs()
        return jsonify(runs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/agent/runs/<int:run_id>', methods=['GET'])
def get_agent_run(run_id):
    """Retrieves full execution audit trail, timeline, and tool calls for a run."""
    try:
        run_data = AgentService.get_run(run_id)
        if not run_data:
            return jsonify({"error": f"Agent run {run_id} not found"}), 404
        return jsonify(run_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Tasks Endpoints ---
@api_bp.route('/tasks', methods=['GET'])
def list_tasks():
    status = request.args.get('status')
    try:
        tasks = TaskTool.list_tasks(status=status)
        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/tasks', methods=['POST'])
def create_task():
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "'title' is required"}), 400

    try:
        task = TaskTool.create_task(
            title=title,
            description=data.get("description", ""),
            priority=data.get("priority", "MEDIUM"),
            priority_score=data.get("priority_score", 50.0),
            deadline=data.get("deadline"),
            duration_hours=data.get("duration_hours", 1.0),
            dependencies=data.get("dependencies", []),
            subtasks=data.get("subtasks", [])
        )
        return jsonify(task), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = TaskTool.get_task(task_id)
    if not task:
        return jsonify({"error": f"Task {task_id} not found"}), 404
    return jsonify(task), 200

@api_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json() or {}
    try:
        task = TaskTool.update_task(
            task_id=task_id,
            title=data.get("title"),
            description=data.get("description"),
            priority=data.get("priority"),
            priority_score=data.get("priority_score"),
            deadline=data.get("deadline"),
            duration_hours=data.get("duration_hours"),
            status=data.get("status")
        )
        return jsonify(task), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    try:
        result = TaskTool.complete_task(task_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        result = TaskTool.delete_task(task_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Schedule Endpoints ---
@api_bp.route('/schedule', methods=['GET'])
def get_schedule():
    date_str = request.args.get('date')
    task_id = request.args.get('task_id')
    try:
        schedules = SchedulerTool.get_schedule(date_str=date_str, task_id=task_id)
        return jsonify(schedules), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Planner Endpoints ---
@api_bp.route('/planner/generate', methods=['POST'])
def generate_plan():
    data = request.get_json() or {}
    daily_hours = float(data.get("daily_hours", 3.0))
    try:
        plan = PlannerTool.generate_plan(daily_hours=daily_hours)
        return jsonify(plan), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/planner/replan', methods=['POST'])
def trigger_replan():
    data = request.get_json() or {}
    reason = data.get("reason", "Manual replan requested")
    daily_hours = float(data.get("daily_hours", 3.0))
    try:
        replan_res = ReplannerService.simulate_delay_and_replan(reason=reason, daily_hours=daily_hours)
        return jsonify(replan_res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/planner/simulate-delay', methods=['POST'])
def simulate_delay():
    """Hackathon showcase endpoint: Simulates missed session 'I couldn't study today'"""
    data = request.get_json() or {}
    reason = data.get("reason", "I couldn't study today")
    target_date = data.get("date")
    daily_hours = float(data.get("daily_hours", 3.0))
    try:
        replan_res = ReplannerService.simulate_delay_and_replan(
            reason=reason,
            target_date=target_date,
            daily_hours=daily_hours
        )
        return jsonify(replan_res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Research Endpoint ---
@api_bp.route('/research', methods=['POST'])
def run_research():
    data = request.get_json() or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "'topic' is required"}), 400

    try:
        result = ResearchService.run_research(topic)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Monitoring & Analytics ---
@api_bp.route('/analytics', methods=['GET'])
def get_analytics():
    try:
        progress = MonitorTool.get_progress()
        conflicts = MonitorTool.detect_conflict()
        overdue = MonitorTool.detect_overdue_tasks()
        return jsonify({
            "progress": progress,
            "conflicts": conflicts,
            "overdue_tasks": overdue
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Demo & Seeding Endpoints ---
@api_bp.route('/demo/seed', methods=['POST'])
def seed_demo():
    """Seeds the exact Hackathon demonstration scenario in one click."""
    scenario_prompt = (
        "I have a Java exam on Monday, DBMS assignment due tomorrow, "
        "and project presentation on Wednesday. I have 3 hours available every evening. "
        "Create a study plan."
    )
    try:
        result = AgentService.process_goal(scenario_prompt)
        return jsonify({
            "message": "Demo goal initialized successfully. Ready for Human Approval.",
            "prompt": scenario_prompt,
            "result": result
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/demo/reset', methods=['POST'])
def reset_db():
    """Resets tables for clean testing."""
    conn = Database.get_connection()
    try:
        conn.execute("DELETE FROM schedules")
        conn.execute("DELETE FROM subtasks")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM plans")
        conn.execute("DELETE FROM agent_runs")
        conn.execute("DELETE FROM tool_calls")
        conn.execute("DELETE FROM approvals")
        conn.execute("DELETE FROM conflicts")
        conn.execute("DELETE FROM research_queries")
        conn.commit()
        return jsonify({"status": "Database cleared successfully"}), 200
    finally:
        conn.close()
