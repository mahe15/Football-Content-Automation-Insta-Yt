"""
BiscoFootball — Caption Generator
Generates short captions, descriptions, and hashtags via ChatGPT.
"""

import json
from datetime import datetime
from pathlib import Path
from loguru import logger
from modules.chatgpt_browser import get_chatgpt
import config


class CaptionGenerator:
    """Generates Instagram/YouTube captions and hashtags."""

    def __init__(self):
        self.caption_data = {}

    async def generate(self, research: dict) -> dict:
        """Generate caption, description, and hashtags for the content."""
        if not config.ENABLE_CHATGPT_CAPTION:
            logger.info("⏭️ Caption generation disabled — using defaults")
            return self._default_caption(research)

        logger.info("✍️ Generating captions...")

        title = research.get("title", "Football Stats")
        facts = research.get("facts", [])
        key_takeaway = research.get("key_takeaway", "")
        viral_angle = research.get("viral_angle", "")

        prompt = f"""You are a social media copywriter for a football Instagram page called "biscofootball".

Topic: {title}
Key Facts: {json.dumps(facts[:5])}
Key Takeaway: {key_takeaway}
Viral Angle: {viral_angle}

Generate engaging social media copy:

Return ONLY valid JSON:
{{
  "short_caption": "3 lines maximum. Punchy, attention-grabbing. Include 1-2 emojis. No hashtags here.",
  "description": "6-8 lines. Engaging description with facts. Tell a story. Include emojis. End with a CTA like 'Follow @biscofootball for more!'",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "youtube_title": "Catchy YouTube Shorts title (max 60 chars)",
  "youtube_description": "YouTube description with relevant keywords",
  "youtube_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}

Rules:
- Short caption must be max 3 lines
- Description must be 6-8 lines
- Exactly 5 hashtags (no # symbol, just the text)
- Make it emotionally engaging
- Use football-related emojis ⚽🏆🔥
- YouTube title should be curiosity-driven

Return ONLY the JSON, nothing else."""

        try:
            chatgpt = await get_chatgpt()
            response = await chatgpt.send_prompt(prompt)

            if response:
                self.caption_data = self._parse_caption(response, research)
                self._save_caption()
                logger.success("✅ Captions generated")
                return self.caption_data

        except Exception as e:
            logger.error(f"Caption generation failed: {e}")

        return self._default_caption(research)

    def _parse_caption(self, response: str, research: dict) -> dict:
        """Parse caption response from ChatGPT."""
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

            # Ensure hashtags have # prefix
            hashtags = data.get("hashtags", [])
            hashtags = [f"#{h.replace('#', '')}" for h in hashtags]

            return {
                "short_caption": data.get("short_caption", ""),
                "description": data.get("description", ""),
                "hashtags": hashtags,
                "youtube_title": data.get("youtube_title", research.get("title", "")),
                "youtube_description": data.get("youtube_description", ""),
                "youtube_tags": data.get("youtube_tags", []),
                "full_instagram_caption": (
                    data.get("short_caption", "") + "\n\n" +
                    data.get("description", "") + "\n\n" +
                    " ".join(hashtags)
                ),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse caption JSON: {e}")

        return self._default_caption(research)

    def _default_caption(self, research: dict) -> dict:
        """Generate a default caption when ChatGPT fails."""
        title = research.get("title", "Football Facts")
        return {
            "short_caption": f"⚽ {title}\n🔥 Did you know?\n👇 Check it out!",
            "description": f"⚽ {title}\n\nFollow @biscofootball for more football content!",
            "hashtags": ["#football", "#soccer", "#worldcup", "#biscofootball", "#footballfacts"],
            "youtube_title": title,
            "youtube_description": f"{title} | Football Facts by BiscoFootball",
            "youtube_tags": ["football", "soccer", "world cup", "facts", "biscofootball"],
            "full_instagram_caption": (
                f"⚽ {title}\n🔥 Did you know?\n👇 Check it out!\n\n"
                f"Follow @biscofootball for more!\n\n"
                f"#football #soccer #worldcup #biscofootball #footballfacts"
            ),
        }

    def _save_caption(self):
        """Save caption to file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = config.CAPTIONS_DIR / f"caption_{timestamp}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.caption_data, f, indent=2, ensure_ascii=False)

            # Also save as latest
            latest_path = config.DATA_DIR / "latest_caption.json"
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(self.caption_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save caption: {e}")
