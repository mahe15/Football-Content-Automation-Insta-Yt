"""
BiscoFootball — Telegram Notifications
Sends status updates, previews, and alerts to Telegram.
"""

import json
import requests
from pathlib import Path
from loguru import logger
import config


class TelegramNotifier:
    """Sends notifications to Telegram."""

    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
        self.chat_id = config.TELEGRAM_CHAT_ID

    def _can_send(self):
        if not config.ENABLE_TELEGRAM_NOTIFICATIONS:
            return False
        if not config.TELEGRAM_BOT_TOKEN or not self.chat_id:
            logger.warning("Telegram credentials not configured")
            return False
        return True

    def send_text(self, text: str, parse_mode: str = "HTML"):
        if not self._can_send():
            return
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}
            resp = requests.post(url, data=data, timeout=30)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")

    def send_photo(self, photo_path: str, caption: str = ""):
        if not self._can_send():
            return
        if not photo_path or not Path(photo_path).exists():
            logger.error(f"Photo not found: {photo_path}")
            return
        try:
            url = f"{self.base_url}/sendPhoto"
            with open(photo_path, "rb") as f:
                data = {"chat_id": self.chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
                files = {"photo": f}
                resp = requests.post(url, data=data, files=files, timeout=60)
                if resp.status_code != 200:
                    logger.error(f"Telegram photo failed: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Telegram photo error: {e}")

    def send_video(self, video_path: str, caption: str = ""):
        if not self._can_send():
            return
        if not video_path or not Path(video_path).exists():
            logger.error(f"Video not found: {video_path}")
            return
        try:
            url = f"{self.base_url}/sendVideo"
            with open(video_path, "rb") as f:
                data = {"chat_id": self.chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
                files = {"video": f}
                resp = requests.post(url, data=data, files=files, timeout=120)
                if resp.status_code != 200:
                    logger.error(f"Telegram video failed: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Telegram video error: {e}")

    # --- Stage Notifications ---

    def notify_research_complete(self, research: dict):
        title = research.get("title", "Unknown")
        facts_count = len(research.get("facts", []))
        self.send_text(
            f"🔬 <b>Research Complete</b>\n\n"
            f"📌 Topic: {title}\n"
            f"📊 Facts gathered: {facts_count}\n"
            f"🎯 Key takeaway: {research.get('key_takeaway', 'N/A')}"
        )

    def notify_content_selected(self, candidate: dict):
        self.send_text(
            f"🏆 <b>Content Selected</b>\n\n"
            f"📌 {candidate.get('title', '')}\n"
            f"📊 Score: {candidate.get('score', 'N/A')}\n"
            f"🔥 Category: {candidate.get('category', '')}\n"
            f"💡 Reason: {candidate.get('selection_reason', 'Highest score')}"
        )

    def notify_image_generated(self, image_path: str, title: str):
        self.send_photo(image_path, f"🎨 <b>Infographic Generated</b>\n📌 {title}")

    def notify_video_generated(self, video_path: str, title: str, caption_data: dict = None):
        caption_text = f"🎬 <b>Video Generated</b>\n📌 <b>{title}</b>"
        if caption_data:
            short = caption_data.get("short_caption", "")
            if short:
                caption_text += f"\n\n📝 {short}"
        
        # Send the video first
        self.send_video(video_path, caption_text)
        
        # Now send the full copy-pasteable caption details in a separate message
        if caption_data:
            full_text = (
                f"📝 <b>COPY-PASTE CAPTIONS FOR:</b>\n📌 <i>{title}</i>\n\n"
                f"<b>Instagram Caption:</b>\n{caption_data.get('short_caption', '')}\n\n"
                f"<b>Instagram Description:</b>\n{caption_data.get('description', '')}\n\n"
                f"<b>Instagram Hashtags:</b>\n{' '.join(caption_data.get('hashtags', []))}\n\n"
                f"-----------------------------------\n\n"
                f"<b>YouTube Shorts Title:</b>\n{caption_data.get('youtube_title', '')}\n\n"
                f"<b>YouTube Shorts Description:</b>\n{caption_data.get('youtube_description', '')}\n\n"
                f"<b>YouTube Tags:</b>\n{', '.join(caption_data.get('youtube_tags', []))}"
            )
            self.send_text(full_text)

    def notify_upload_complete(self, platform: str, url: str):
        emoji = "📸" if platform == "instagram" else "📺"
        self.send_text(
            f"{emoji} <b>Upload Complete — {platform.title()}</b>\n\n"
            f"🔗 {url}"
        )

    def notify_upload_failed(self, platform: str, error: str):
        self.send_text(
            f"❌ <b>Upload Failed — {platform.title()}</b>\n\n"
            f"Error: {error[:500]}"
        )

    def notify_cycle_skipped(self, score: float, threshold: float):
        self.send_text(
            f"⏭️ <b>Cycle Skipped</b>\n\n"
            f"Score: {score} < Threshold: {threshold}\n"
            f"No content published this cycle."
        )

    def notify_error(self, stage: str, error: str):
        self.send_text(
            f"🚨 <b>Error — {stage}</b>\n\n"
            f"<code>{error[:500]}</code>"
        )

    def notify_system_start(self):
        self.send_text(
            "🚀 <b>BiscoFootball System Started</b>\n\n"
            f"⏱️ Schedule: Every {config.SCHEDULE_INTERVAL_MINUTES} min\n"
            f"📊 Threshold: {config.VIRAL_SCORE_THRESHOLD}\n"
            f"📸 Instagram: {'✅' if config.ENABLE_INSTAGRAM_UPLOAD else '❌'}\n"
            f"📺 YouTube: {'✅' if config.ENABLE_YOUTUBE_UPLOAD else '❌'}\n"
            f"🤖 ChatGPT Image: {'✅' if config.ENABLE_CHATGPT_IMAGE else '❌'}"
        )

    def notify_pipeline_start(self):
        self.send_text("🔄 <b>Pipeline cycle starting...</b>")

    def notify_pipeline_complete(self, results: dict):
        self.send_text(
            f"✅ <b>Pipeline Complete</b>\n\n"
            f"📌 Topic: {results.get('title', 'N/A')}\n"
            f"📊 Score: {results.get('score', 'N/A')}\n"
            f"📸 IG: {results.get('ig_url', 'N/A')}\n"
            f"📺 YT: {results.get('yt_url', 'N/A')}"
        )


# Singleton
_notifier = None

def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
