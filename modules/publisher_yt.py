"""
BiscoFootball — YouTube Publisher via YouTube Data API v3
"""

import json
import os
from datetime import datetime
from pathlib import Path
from loguru import logger

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    logger.warning("Google API libraries not installed")

import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublisher:
    """Publishes videos to YouTube Shorts."""

    def __init__(self):
        self.last_video_url = ""
        self.last_video_id = ""
        self.service = None

    def _authenticate(self):
        """Authenticate with YouTube API."""
        creds = None
        token_path = config.DATA_DIR / "youtube_token.json"

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client_secret = config.YOUTUBE_CLIENT_SECRET_PATH
                if not Path(client_secret).exists():
                    logger.error(f"YouTube client secret not found: {client_secret}")
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as f:
                f.write(creds.to_json())

        self.service = build("youtube", "v3", credentials=creds)
        return True

    def upload_short(self, video_path: str, title: str, description: str, tags: list) -> dict:
        """Upload a video as YouTube Short."""
        if not config.ENABLE_YOUTUBE_UPLOAD:
            logger.info("⏭️ YouTube upload disabled")
            return {}

        if not video_path or not Path(video_path).exists():
            logger.error(f"Video not found: {video_path}")
            return {}

        logger.info(f"📺 Uploading to YouTube: {title}")

        try:
            if not self.service:
                if not self._authenticate():
                    return {}

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:30],
                    "categoryId": "17",  # Sports
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                    "madeForKids": False,
                },
            }

            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

            request = self.service.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )

            response = request.execute()
            video_id = response.get("id", "")
            self.last_video_id = video_id
            self.last_video_url = f"https://youtube.com/shorts/{video_id}"

            logger.success(f"✅ YouTube Short uploaded: {self.last_video_url}")
            self._save_record(response)
            return response

        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return {"error": str(e)}

    def _save_record(self, data: dict):
        try:
            record = {
                "platform": "youtube",
                "video_id": data.get("id", ""),
                "url": self.last_video_url,
                "timestamp": datetime.now().isoformat(),
            }
            path = config.UPLOADS_DIR / f"youtube_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save record: {e}")
