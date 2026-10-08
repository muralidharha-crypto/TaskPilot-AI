import os
from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", Config.HOST)
    port = int(os.getenv("PORT", Config.PORT))
    debug = Config.DEBUG
    print(f"[TaskPilot AI] Autonomous Productivity Agent server running at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
