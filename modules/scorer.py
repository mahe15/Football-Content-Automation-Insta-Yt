"""
BiscoFootball — Viral Content Scorer
Sends 5 candidates to ChatGPT for scoring and selects the best one.
"""

import json
from loguru import logger
from modules.chatgpt_browser import get_chatgpt
import config


class ViralScorer:
    """Scores content candidates for virality using ChatGPT."""

    def __init__(self):
        self.scores = []
        self.selected = None

    async def score_and_select(self, candidates: list) -> dict:
        """Score all candidates and return the highest scoring one."""
        if not candidates:
            logger.warning("No candidates to score")
            return {}

        if not config.ENABLE_CHATGPT_SCORING:
            logger.info("⏭️ Scoring disabled — selecting first candidate")
            self.selected = candidates[0]
            self.selected["score"] = 10.0
            return self.selected

        logger.info(f"🏆 Scoring {len(candidates)} candidates for virality...")

        # Format candidates for scoring
        candidates_text = ""
        for i, c in enumerate(candidates, 1):
            candidates_text += f"""
Candidate {i}:
Title: {c.get('title', '')}
Category: {c.get('category', '')}
Hook: {c.get('hook', '')}
Viral Angle: {c.get('viral_angle', '')}
"""

        prompt = f"""You are a viral content expert for football social media.

Score each content idea from 1-10 on these criteria:
- Curiosity (1-10): How much does it make people want to know more?
- Shock Factor (1-10): How surprising or unexpected is it?
- Shareability (1-10): How likely are people to share it?
- Historical Significance (1-10): How important is this in football history?
- Debate Potential (1-10): Will people argue about this in comments?
- Emotional Impact (1-10): How much emotion does it trigger?

Here are the candidates:
{candidates_text}

For each candidate, calculate the AVERAGE score across all 6 criteria.

Then choose ONLY ONE — the highest scoring candidate.

Return ONLY valid JSON like this:
{{
  "scores": [
    {{"candidate": 1, "curiosity": 8, "shock": 7, "shareability": 9, "historical": 8, "debate": 9, "emotion": 8, "average": 8.2}},
    {{"candidate": 2, "curiosity": 6, "shock": 5, "shareability": 6, "historical": 4, "debate": 5, "emotion": 5, "average": 5.2}}
  ],
  "selected": 1,
  "reason": "Why this candidate was chosen"
}}

Return ONLY the JSON, nothing else."""

        try:
            chatgpt = await get_chatgpt()
            response = await chatgpt.send_prompt(prompt)

            if response:
                result = self._parse_scores(response, candidates)
                if result:
                    self._save_scores()
                    return result

            # Fallback: select first candidate
            logger.warning("Scoring failed, selecting first candidate")
            self.selected = candidates[0]
            self.selected["score"] = 7.0
            return self.selected

        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            self.selected = candidates[0]
            self.selected["score"] = 7.0
            return self.selected

    def _parse_scores(self, response: str, candidates: list) -> dict:
        """Parse scoring response from ChatGPT."""
        try:
            text = response.strip()

            # Remove markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            # Find JSON object
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            data = json.loads(text)

            self.scores = data.get("scores", [])
            selected_idx = data.get("selected", 1) - 1  # Convert to 0-based
            reason = data.get("reason", "")

            if 0 <= selected_idx < len(candidates):
                self.selected = candidates[selected_idx].copy()

                # Add score info
                if self.scores and selected_idx < len(self.scores):
                    self.selected["score"] = self.scores[selected_idx].get("average", 7.0)
                else:
                    self.selected["score"] = 8.0

                self.selected["selection_reason"] = reason

                logger.success(
                    f"🏆 Selected: \"{self.selected['title']}\" "
                    f"(Score: {self.selected['score']})"
                )
                return self.selected
            else:
                logger.warning(f"Invalid selected index: {selected_idx}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scores JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}")

        return None

    def check_threshold(self, candidate: dict) -> bool:
        """Check if the candidate's score meets the viral threshold."""
        score = candidate.get("score", 0)
        threshold = config.VIRAL_SCORE_THRESHOLD
        passes = score >= threshold

        if passes:
            logger.info(f"✅ Score {score} >= threshold {threshold} — PUBLISHING")
        else:
            logger.info(f"⏭️ Score {score} < threshold {threshold} — SKIPPING CYCLE")

        return passes

    def _save_scores(self):
        """Save scores to file."""
        try:
            path = config.DATA_DIR / "latest_scores.json"
            data = {
                "scores": self.scores,
                "selected": self.selected,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save scores: {e}")
