"""
BiscoFootball — Content Researcher
Deep-dives into the selected content topic via ChatGPT.
"""

import json
from loguru import logger
from modules.chatgpt_browser import get_chatgpt
import config


class ContentResearcher:
    """Researches selected content topic in-depth using ChatGPT."""

    def __init__(self):
        self.research = {}

    async def research_topic(self, candidate: dict) -> dict:
        """Perform deep research on the selected candidate topic."""
        if not config.ENABLE_CHATGPT_RESEARCH:
            logger.info("⏭️ Research disabled — using candidate data")
            return {
                "title": candidate.get("title", ""),
                "facts": candidate.get("data", []),
                "statistics": [],
                "comparisons": [],
                "historical_context": "",
                "viral_angle": candidate.get("viral_angle", ""),
                "key_takeaway": candidate.get("hook", ""),
            }

        logger.info(f"🔬 Researching: \"{candidate.get('title', '')}\"")

        title = candidate.get("title", "")
        hook = candidate.get("hook", "")
        category = candidate.get("category", "")
        data = candidate.get("data", [])

        prompt = f"""You are a football content researcher with access to deep archives spanning the last 100 years of football history (from 1926 to the current day). Research this topic thoroughly for a viral Instagram infographic. Make sure to draw on historical milestones, player statistics, and comparisons from this 100-year window.

Topic: {title}
Category: {category}
Hook: {hook}
Initial Data Points: {json.dumps(data)}

Provide comprehensive research in this EXACT JSON format:
{{
  "title": "{title}",
  "facts": ["5-8 interesting facts about this topic, including historical trivia/context from the last 100 years where relevant"],
  "statistics": ["3-5 key statistics with numbers"],
  "comparisons": ["2-3 relevant comparisons (e.g. comparisons across different eras/players from the last 100 years)"],
  "historical_context": "2-3 sentences of historical background covering the evolution over the last 100 years The Researched content must Check with todays Date That This is Ture or false",
  "viral_angle": "The main angle that makes this go viral",
  "key_takeaway": "One powerful sentence that summarizes everything",
  "infographic_data": {{
    "headline": "Bold headline for the infographic (max 8 words)",
    "subheadline": "Supporting line (max 12 words)",
    "main_stats": ["Stat 1: Value", "Stat 2: Value", "Stat 3: Value"],
    "comparison_items": [
      {{"name": "Player/Team A", "value": "stat"}},
      {{"name": "Player/Team B", "value": "stat"}}
    ],
    "footer_text": "Short engaging footer line"
  }}
}}

Make sure ALL facts and statistics are ACCURATE.
Return ONLY the JSON, nothing else."""

        try:
            chatgpt = await get_chatgpt()
            response = await chatgpt.send_prompt(prompt)

            if response:
                self.research = self._parse_research(response, candidate)
                self._save_research()
                logger.success(f"✅ Research complete: {len(self.research.get('facts', []))} facts gathered")
                return self.research

        except Exception as e:
            logger.error(f"Research failed: {e}")

        # Fallback
        return {
            "title": title,
            "facts": data,
            "statistics": [],
            "comparisons": [],
            "historical_context": "",
            "viral_angle": candidate.get("viral_angle", ""),
            "key_takeaway": hook,
            "infographic_data": {
                "headline": title,
                "subheadline": hook,
                "main_stats": data[:3],
                "comparison_items": [],
                "footer_text": "Follow @biscofootball for more",
            },
        }

    def _parse_research(self, response: str, candidate: dict) -> dict:
        """Parse research response from ChatGPT."""
        try:
            text = response.strip()

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            data = json.loads(text)
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse research JSON: {e}")

        return {
            "title": candidate.get("title", ""),
            "facts": candidate.get("data", []),
            "statistics": [],
            "comparisons": [],
            "historical_context": "",
            "viral_angle": candidate.get("viral_angle", ""),
            "key_takeaway": candidate.get("hook", ""),
        }

    def _save_research(self):
        """Save research to file."""
        try:
            path = config.DATA_DIR / "latest_research.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.research, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save research: {e}")
