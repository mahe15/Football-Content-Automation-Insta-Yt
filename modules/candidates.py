"""
BiscoFootball — Content Candidate Generator
Takes collected events and generates 5 viral content candidates via ChatGPT.
"""

import json
from loguru import logger
from modules.chatgpt_browser import get_chatgpt
import config


class CandidateGenerator:
    """Generates 5 content candidates from collected events using ChatGPT."""

    def __init__(self):
        self.candidates = []

    async def generate(self, events: list) -> list:
        """Generate 5 content candidates from collected events."""
        if not events:
            logger.warning("No events to generate candidates from")
            return []

        logger.info(f"💡 Generating {config.NUM_CANDIDATES} content candidates...")

        # Build event summary for ChatGPT
        event_summary = self._format_events(events)

        prompt = f"""You are a viral football content strategist for an Instagram page called "biscofootball".
 
 Here are the latest football events and trends:
 
 {event_summary}
 
 Based on these events, generate exactly {config.NUM_CANDIDATES} viral football content ideas for Instagram infographic posts.
 
 Each idea should be designed to go VIRAL on social media.
 
 Focus on these categories (in priority order), ensuring you pull relevant facts, statistics, player comparisons, and milestones spanning the last 100 years of football history (from 1926 to the current day):
 1. World Cup content (historical and modern)
 2. Record-breaking achievements
 3. Player comparisons (including legends across different eras like Pelé, Maradona, Cruyff, Zidane, Messi, Ronaldo This ar Jsut For EXample Make Comaparison of All Fomous Players)
 4. Rankings and statistics
 5. Shocking/surprising football facts
 6. Historical football events
 7. Match predictions
 8. Legendary player tributes

For each idea, provide:
- Title: Short catchy title (max 10 words)
- Category: One of the categories above
- Hook: The curiosity hook that makes people stop scrolling
- Data: Key facts/stats needed for the infographic
- Viral_angle: Why this will go viral

Return ONLY valid JSON array format like this:
[
  {{
    "title": "...",
    "category": "...",
    "hook": "...",
    "data": ["fact1", "fact2", "fact3"],
    "viral_angle": "..."
  }}
]

Return ONLY the JSON array, nothing else."""

        try:
            chatgpt = await get_chatgpt()
            response = await chatgpt.send_prompt(prompt)

            if response:
                self.candidates = self._parse_candidates(response)
                logger.success(f"✅ Generated {len(self.candidates)} candidates")

                # Save candidates
                self._save_candidates()
                return self.candidates
            else:
                logger.error("Empty response from ChatGPT")
                return []

        except Exception as e:
            logger.error(f"Candidate generation failed: {e}")
            return []

    def _format_events(self, events: list) -> str:
        """Format events into a readable summary for ChatGPT."""
        lines = []
        for i, event in enumerate(events[:20], 1):
            source = event.get("source", "Unknown")
            title = event.get("title", "")
            category = event.get("category", "")
            details = event.get("details", "")
            lines.append(f"{i}. [{source}] [{category}] {title}")
            if details:
                lines.append(f"   Details: {details[:150]}")
        return "\n".join(lines)

    def _parse_candidates(self, response: str) -> list:
        """Parse ChatGPT response into structured candidates."""
        try:
            # Try to extract JSON from response
            # Handle cases where ChatGPT wraps JSON in code blocks
            text = response.strip()

            # Remove markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            # Find the JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            candidates = json.loads(text)

            if isinstance(candidates, list):
                # Ensure each candidate has required fields
                valid = []
                for c in candidates:
                    if isinstance(c, dict) and "title" in c:
                        valid.append({
                            "title": c.get("title", ""),
                            "category": c.get("category", "general"),
                            "hook": c.get("hook", ""),
                            "data": c.get("data", []),
                            "viral_angle": c.get("viral_angle", ""),
                        })
                return valid[:config.NUM_CANDIDATES]

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse candidates JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}")

        return []

    def _save_candidates(self):
        """Save candidates to file for review."""
        try:
            path = config.DATA_DIR / "latest_candidates.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.candidates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save candidates: {e}")
