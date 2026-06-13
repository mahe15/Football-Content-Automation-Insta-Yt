"""
BiscoFootball — Instagram Publisher via Meta Graph API
"""

import json
import time
import requests
from datetime import datetime
from loguru import logger
import config


class InstagramPublisher:
    """Publishes content to Instagram via Meta Graph API."""

    def __init__(self):
        self.last_post_url = ""
        self.last_post_id = ""

    def _upload_to_litterbox(self, file_path: str) -> str:
        """Uploads a file to Litterbox for temporary hosting (expires in 1h)."""
        logger.info(f"📤 Uploading local file {Path(file_path).name} to Litterbox for Instagram to fetch...")
        try:
            url = "https://litterbox.catbox.moe/resources/internals/api.php"
            with open(file_path, "rb") as f:
                files = {"fileToUpload": f}
                data = {
                    "reqtype": "fileupload",
                    "time": "1h"
                }
                resp = requests.post(url, data=data, files=files, timeout=60)
                if resp.status_code == 200 and resp.text.strip().startswith("https://"):
                    public_url = resp.text.strip()
                    logger.success(f"🔗 Temporarily hosted at: {public_url}")
                    return public_url
                else:
                    logger.error(f"Litterbox upload failed: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to upload to Litterbox: {e}")
        return ""

    def publish_post(self, image_url: str, caption: str) -> dict:
        """Publish an image post to Instagram.
        Supports both public URLs and local file paths.
        """
        if not config.ENABLE_INSTAGRAM_UPLOAD:
            logger.info("⏭️ Instagram upload disabled")
            return {}

        token = config.INSTAGRAM_ACCESS_TOKEN
        account_id = config.INSTAGRAM_BUSINESS_ACCOUNT_ID

        if not token or not account_id:
            logger.error("Instagram credentials not configured in .env")
            return {}

        from pathlib import Path
        if Path(image_url).exists():
            hosted_url = self._upload_to_litterbox(image_url)
            if not hosted_url:
                logger.error("Failed to host local image for publishing")
                return {"error": "Local hosting failed"}
            image_url = hosted_url

        logger.info("📸 Publishing to Instagram...")

        try:
            # Step 1: Create media container
            container_url = f"https://graph.facebook.com/v21.0/{account_id}/media"
            container_data = {
                "image_url": image_url,
                "caption": caption,
                "access_token": token,
            }

            resp = requests.post(container_url, data=container_data, timeout=60)
            resp_json = resp.json()

            if "id" not in resp_json:
                logger.error(f"Container creation failed: {resp_json}")
                return {"error": resp_json}

            container_id = resp_json["id"]
            logger.info(f"📦 Media container created: {container_id}")

            # Step 2: Wait for processing
            time.sleep(10)

            # Step 3: Publish the container
            publish_url = f"https://graph.facebook.com/v21.0/{account_id}/media_publish"
            publish_data = {
                "creation_id": container_id,
                "access_token": token,
            }

            pub_resp = requests.post(publish_url, data=publish_data, timeout=60)
            pub_json = pub_resp.json()

            if "id" in pub_json:
                self.last_post_id = pub_json["id"]
                self.last_post_url = f"https://www.instagram.com/p/{pub_json['id']}/"
                logger.success(f"✅ Instagram post published! ID: {self.last_post_id}")

                self._save_upload_record("instagram", pub_json)
                return pub_json
            else:
                logger.error(f"Publishing failed: {pub_json}")
                return {"error": pub_json}

        except Exception as e:
            logger.error(f"Instagram publish failed: {e}")
            return {"error": str(e)}

    def publish_reel(self, video_url: str, caption: str) -> dict:
        """Publish a reel/video to Instagram.
        Supports both public URLs and local file paths.
        """
        if not config.ENABLE_INSTAGRAM_UPLOAD:
            logger.info("⏭️ Instagram upload disabled")
            return {}

        token = config.INSTAGRAM_ACCESS_TOKEN
        account_id = config.INSTAGRAM_BUSINESS_ACCOUNT_ID

        if not token or not account_id:
            logger.error("Instagram credentials not configured")
            return {}

        from pathlib import Path
        if Path(video_url).exists():
            hosted_url = self._upload_to_litterbox(video_url)
            if not hosted_url:
                logger.error("Failed to host local video for Instagram Reels publishing")
                return {"error": "Local hosting failed"}
            video_url = hosted_url

        logger.info("🎬 Publishing reel to Instagram...")

        try:
            # Step 1: Create video container
            container_url = f"https://graph.facebook.com/v21.0/{account_id}/media"
            container_data = {
                "video_url": video_url,
                "caption": caption,
                "media_type": "REELS",
                "access_token": token,
            }

            resp = requests.post(container_url, data=container_data, timeout=120)
            resp_json = resp.json()

            if "id" not in resp_json:
                logger.error(f"Reel container failed: {resp_json}")
                return {"error": resp_json}

            container_id = resp_json["id"]
            logger.info(f"📦 Reel container created: {container_id}")

            # Step 2: Wait for video processing (can take longer)
            max_wait = 120
            waited = 0
            while waited < max_wait:
                status_url = f"https://graph.facebook.com/v21.0/{container_id}"
                status_params = {
                    "fields": "status_code",
                    "access_token": token,
                }
                status_resp = requests.get(status_url, params=status_params, timeout=30)
                status_json = status_resp.json()
                status_code = status_json.get("status_code", "")

                if status_code == "FINISHED":
                    break
                elif status_code == "ERROR":
                    logger.error(f"Reel processing error: {status_json}")
                    return {"error": status_json}

                time.sleep(10)
                waited += 10

            # Step 3: Publish
            publish_url = f"https://graph.facebook.com/v21.0/{account_id}/media_publish"
            publish_data = {
                "creation_id": container_id,
                "access_token": token,
            }

            pub_resp = requests.post(publish_url, data=publish_data, timeout=60)
            pub_json = pub_resp.json()

            if "id" in pub_json:
                self.last_post_id = pub_json["id"]
                self.last_post_url = f"https://www.instagram.com/p/{pub_json['id']}/"
                logger.success(f"✅ Instagram reel published! ID: {self.last_post_id}")
                self._save_upload_record("instagram_reel", pub_json)
                return pub_json
            else:
                logger.error(f"Reel publishing failed: {pub_json}")
                return {"error": pub_json}

        except Exception as e:
            logger.error(f"Instagram reel failed: {e}")
            return {"error": str(e)}

    def _save_upload_record(self, platform: str, data: dict):
        try:
            record = {
                "platform": platform,
                "post_id": data.get("id", ""),
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            path = config.UPLOADS_DIR / f"{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save upload record: {e}")
