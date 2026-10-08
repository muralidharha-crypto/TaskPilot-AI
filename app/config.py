import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / ".env")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "taskpilot-secret-dev-key-change-in-prod-987654")
    
    # Instance directory for database
    INSTANCE_DIR = basedir / "instance"
    INSTANCE_DIR.mkdir(exist_ok=True)
    
    DB_PATH = os.getenv("DB_PATH", str(INSTANCE_DIR / "taskpilot.db"))
    
    # AI Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").lower()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "gemini-1.5-flash")
    
    # Agent constraints
    DEFAULT_EVENING_HOURS = float(os.getenv("DEFAULT_EVENING_HOURS", "3.0"))
    MAX_DAILY_HOURS = float(os.getenv("MAX_DAILY_HOURS", "8.0"))
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

    # Cloud & Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "0") in ("true", "1", "yes")
