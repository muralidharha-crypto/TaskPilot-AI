import json
from datetime import datetime
from app.tools.research_tool import ResearchTool
from app.models.database import Database

class ResearchService:
    @staticmethod
    def run_research(topic):
        """
        Executes the 5-step autonomous research workflow:
        1. Understand Goal
        2. Gather Information (Sources)
        3. Organize Findings
        4. Summarize
        5. Produce Action Items
        """
        now = datetime.now().isoformat()
        
        # Step 1 & 2: Search sources
        search_results = ResearchTool.search_information(topic)
        
        # Step 3, 4 & 5: Summarize, extract findings and action items
        summary_results = ResearchTool.summarize_information(topic, search_results.get("sources"))

        # Log into agent runs for visibility in Agent Run page
        conn = Database.get_connection()
        try:
            cursor = conn.cursor()
            timeline = [
                {"step": "INTENT_ANALYSIS", "time": now, "details": f"Classified inquiry as academic research on: '{topic}'"},
                {"step": "GATHER_INFORMATION", "time": now, "details": f"Gathered {len(summary_results['sources'])} authoritative citations via {search_results['provider']}"},
                {"step": "EXTRACT_FINDINGS", "time": now, "details": f"Extracted {len(summary_results['findings'])} core empirical findings and trade-offs"},
                {"step": "SYNTHESIZE_OUTPUT", "time": now, "details": f"Generated executive summary and {len(summary_results['action_items'])} actionable recommendations"}
            ]
            cursor.execute(
                """
                INSERT INTO agent_runs (goal, intent, status, timeline_json, created_at, updated_at)
                VALUES (?, 'research_inquiry', 'COMPLETED', ?, ?, ?)
                """,
                (f"Research: {topic}", json.dumps(timeline), now, now)
            )
            run_id = cursor.lastrowid
            conn.commit()

            return {
                "run_id": run_id,
                "research_id": summary_results.get("id"),
                "goal": topic,
                "provider": search_results.get("provider"),
                "sources": summary_results["sources"],
                "findings": summary_results["findings"],
                "summary": summary_results["summary"],
                "action_items": summary_results["action_items"],
                "completed_at": now
            }
        finally:
            conn.close()
