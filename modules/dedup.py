"""
BiscoFootball — Deduplication & Smart Rules
Prevents duplicate content and enforces topic cooldown.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import config


class DedupChecker:
    """Tracks published content and prevents duplicates."""

    def __init__(self):
        self.history_path = config.DATA_DIR / "history.json"
        self.history = self._load_history()

    def _load_history(self) -> list:
        try:
            if self.history_path.exists():
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
        return []

    def _save_history(self):
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def is_duplicate(self, title: str) -> bool:
        """Check if this topic was published recently."""
        if not config.ENABLE_DEDUP_CHECK:
            return False

        fingerprint = self._fingerprint(title)
        cooldown = timedelta(days=config.TOPIC_COOLDOWN_DAYS)
        cutoff = datetime.now() - cooldown

        for entry in self.history:
            entry_fp = entry.get("fingerprint", "")
            entry_date = datetime.fromisoformat(entry.get("timestamp", "2000-01-01"))

            if entry_date > cutoff and self._similar(fingerprint, entry_fp):
                logger.info(f"⚠️ Duplicate detected: \"{title}\" matches \"{entry.get('title', '')}\"")
                return True

        return False

    def record_published(self, title: str, category: str, score: float, urls: dict):
        """Record a published content item."""
        entry = {
            "title": title,
            "category": category,
            "score": score,
            "fingerprint": self._fingerprint(title),
            "timestamp": datetime.now().isoformat(),
            "urls": urls,
        }
        self.history.append(entry)
        self._save_history()
        logger.info(f"📝 Recorded: \"{title}\" (Total history: {len(self.history)})")

    def _fingerprint(self, text: str) -> str:
        """Create a normalized fingerprint of the text."""
        text = text.lower().strip()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        words = sorted(set(text.split()))
        return " ".join(words)

    def _similar(self, fp1: str, fp2: str) -> bool:
        """Check if two fingerprints are similar enough to be duplicates."""
        words1 = set(fp1.split())
        words2 = set(fp2.split())
        if not words1 or not words2:
            return False
        intersection = words1 & words2
        union = words1 | words2
        jaccard = len(intersection) / len(union)
        return jaccard > 0.6  # 60% similarity threshold

    def get_recent_topics(self, days: int = 7) -> list:
        """Get topics published in the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for entry in self.history:
            try:
                entry_date = datetime.fromisoformat(entry.get("timestamp", "2000-01-01"))
                if entry_date > cutoff:
                    recent.append(entry)
            except Exception:
                continue
        return recent

    def get_stats(self) -> dict:
        """Get publishing statistics."""
        total = len(self.history)
        last_7 = len(self.get_recent_topics(7))
        last_30 = len(self.get_recent_topics(30))
        categories = {}
        for entry in self.history:
            cat = entry.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_published": total,
            "last_7_days": last_7,
            "last_30_days": last_30,
            "categories": categories,
        }
