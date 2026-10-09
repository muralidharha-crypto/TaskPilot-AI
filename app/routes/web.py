from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, render_template

from app.config import Config

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def dashboard():
    return render_template('dashboard.html', active_tab='dashboard')

@web_bp.route('/tasks')
def tasks_page():
    return render_template('tasks.html', active_tab='tasks')

@web_bp.route('/planner')
def planner_page():
    return render_template('planner.html', active_tab='planner')

@web_bp.route('/runs')
def runs_page():
    return render_template('runs.html', active_tab='runs')

@web_bp.route('/approvals')
def approvals_page():
    return render_template('approvals.html', active_tab='approvals')

@web_bp.route('/calendar')
def calendar_page():
    return render_template('calendar.html', active_tab='calendar')

@web_bp.route('/research')
def research_page():
    return render_template('research.html', active_tab='research')

@web_bp.route('/analytics')
def analytics_page():
    return render_template('analytics.html', active_tab='analytics')

@web_bp.route('/health')
def health_check():
    """Production health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "TaskPilot AI",
        "version": "1.0.0",
        "timestamp": datetime.now(ZoneInfo(Config.TIMEZONE)).isoformat()
    }), 200
