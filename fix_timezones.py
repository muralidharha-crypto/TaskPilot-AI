import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "app"

FILES = {
    "routes/web.py",
    "services/agent.py",
    "services/approval_manager.py",
    "services/executor.py",
    "services/research_service.py",
    "tools/monitor_tool.py",
    "tools/planner_tool.py",
    "tools/research_tool.py",
    "tools/scheduler_tool.py",
    "tools/task_tool.py",
    "tools/tool_registry.py",
}


def add_imports(source: str) -> str:
    """Add timezone imports if missing."""
    imports = []

    if "from zoneinfo import ZoneInfo" not in source:
        imports.append("from zoneinfo import ZoneInfo")

    if "from app.config import Config" not in source:
        imports.append("from app.config import Config")

    if not imports:
        return source

    lines = source.splitlines()
    insert_at = 0

    while insert_at < len(lines):
        line = lines[insert_at].strip()
        if line.startswith("from __future__ import"):
            insert_at += 1
        else:
            break

    lines[insert_at:insert_at] = imports + [""]
    return "\n".join(lines) + "\n"


def fix_file(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    original = source

    source = re.sub(
        r"datetime\.now\(\)",
        "datetime.now(ZoneInfo(Config.TIMEZONE))",
        source,
    )

    source = re.sub(
        r"date\.today\(\)",
        "datetime.now(ZoneInfo(Config.TIMEZONE)).date()",
        source,
    )

    if source != original:
        source = add_imports(source)
        path.write_text(source, encoding="utf-8")
        print(f"Updated: {path.relative_to(ROOT)}")


def main() -> None:
    for relative in sorted(FILES):
        path = ROOT / relative
        if path.exists():
            fix_file(path)

    print("\nPass 1 complete. strptime() cases have not been changed.")


if __name__ == "__main__":
    main()