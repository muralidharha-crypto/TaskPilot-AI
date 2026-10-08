import sqlite3
import json
from pathlib import Path
from flask import g, has_app_context, current_app
from app.config import Config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT 'MEDIUM',
    priority_score REAL DEFAULT 0.0,
    deadline TEXT,
    duration_hours REAL DEFAULT 1.0,
    status TEXT DEFAULT 'PENDING',
    dependencies TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subtasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    duration_hours REAL DEFAULT 0.5,
    order_idx INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    title TEXT NOT NULL,
    date_str TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_hours REAL DEFAULT 1.0,
    status TEXT DEFAULT 'SCHEDULED',
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    total_estimated_hours REAL DEFAULT 0.0,
    daily_hours_limit REAL DEFAULT 3.0,
    constraints TEXT,
    status TEXT DEFAULT 'ACTIVE',
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    timeline_json TEXT DEFAULT '[]',
    proposed_actions_json TEXT DEFAULT '[]',
    execution_summary_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    tool_name TEXT NOT NULL,
    function_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    status TEXT DEFAULT 'SUCCESS',
    timestamp TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES agent_runs (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    proposed_actions_json TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    user_action_at TEXT,
    executed_at TEXT,
    comments TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES agent_runs (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    description TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    old_plan_json TEXT,
    new_plan_json TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES agent_runs (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS research_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    findings_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    action_items_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

class Database:
    @staticmethod
    def get_connection(db_path=None):
        if db_path is None:
            if has_app_context():
                db_path = current_app.config.get("DB_PATH", Config.DB_PATH)
            else:
                db_path = Config.DB_PATH

        # Ensure database tables exist
        Database.init_db(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @staticmethod
    def init_db(db_path=None):
        if db_path is None:
            if has_app_context():
                db_path = current_app.config.get("DB_PATH", Config.DB_PATH)
            else:
                db_path = Config.DB_PATH

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

def get_db():
    if 'db' not in g:
        g.db = Database.get_connection()
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
