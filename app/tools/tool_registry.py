import json
from datetime import datetime
from app.models.database import Database

class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._metadata = {}

    def register(self, tool_name, func_name, func, description="", params_schema=None):
        key = f"{tool_name}.{func_name}"
        self._tools[key] = func
        self._metadata[key] = {
            "tool_name": tool_name,
            "func_name": func_name,
            "description": description,
            "params_schema": params_schema or {}
        }

    def execute(self, tool_name, func_name, kwargs=None, run_id=None, db_conn=None):
        kwargs = kwargs or {}
        key = f"{tool_name}.{func_name}"
        
        if key not in self._tools:
            err_msg = f"Security Violation or Tool Not Found: '{key}' is not in allowlisted tools."
            self._log_call(run_id, tool_name, func_name, kwargs, {"error": err_msg}, "FAILED", db_conn)
            raise ValueError(err_msg)

        func = self._tools[key]
        try:
            result = func(**kwargs)
            self._log_call(run_id, tool_name, func_name, kwargs, result, "SUCCESS", db_conn)
            return {"success": True, "data": result}
        except Exception as e:
            err_msg = str(e)
            self._log_call(run_id, tool_name, func_name, kwargs, {"error": err_msg}, "FAILED", db_conn)
            return {"success": False, "error": err_msg}

    def _log_call(self, run_id, tool_name, func_name, args, result, status, db_conn=None):
        timestamp = datetime.now().isoformat()
        conn = db_conn
        should_close = False
        try:
            if conn is None:
                conn = Database.get_connection()
                should_close = True
            
            conn.execute(
                """
                INSERT INTO tool_calls (run_id, tool_name, function_name, arguments_json, result_json, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tool_name,
                    func_name,
                    json.dumps(args, default=str),
                    json.dumps(result, default=str),
                    status,
                    timestamp
                )
            )
            conn.commit()
        except Exception as ex:
            # Prevent logging failure from breaking app
            print(f"[ToolRegistry Log Error] {ex}")
        finally:
            if should_close and conn:
                conn.close()

    def get_tool_definitions(self):
        return list(self._metadata.values())

# Global registry instance
registry = ToolRegistry()
