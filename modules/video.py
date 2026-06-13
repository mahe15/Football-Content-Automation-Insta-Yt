"""
BiscoFootball — Video Creator
Creates short-form videos from infographic images using FFmpeg.
"""

import subprocess
import random
from datetime import datetime
from pathlib import Path
from loguru import logger
import config


class VideoCreator:
    """Creates short videos from infographic images with zoom and music."""

    def __init__(self):
        self.last_video_path = ""

    def create(self, image_path: str) -> str:
        if not config.ENABLE_VIDEO_GENERATION:
            logger.info("⏭️ Video generation disabled")
            return ""
        if not image_path or not Path(image_path).exists():
            logger.error(f"Image not found: {image_path}")
            return ""
        if not self._check_ffmpeg():
            logger.error("FFmpeg not found!")
            return ""

        logger.info(f"🎬 Creating video from: {image_path}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_name = Path(image_path).stem
        output_path = config.VIDEOS_DIR / f"{timestamp}_{img_name}.mp4"

        try:
            cmd = self._build_cmd(image_path, str(output_path))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0 and output_path.exists():
                self.last_video_path = str(output_path)
                sz = output_path.stat().st_size / (1024 * 1024)
                logger.success(f"✅ Video created: {output_path} ({sz:.1f} MB)")
                return str(output_path)
            else:
                logger.error(f"FFmpeg failed: {result.stderr[:500]}")
                return self._simple_video(image_path, str(output_path))
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
        except Exception as e:
            logger.error(f"Video creation failed: {e}")
        return ""

    def _build_cmd(self, image_path, output_path):
        d = config.VIDEO_DURATION_SECONDS
        w, h, fps = config.VIDEO_WIDTH, config.VIDEO_HEIGHT, config.VIDEO_FPS
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"

        music = self._get_music()
        if music and config.ENABLE_MUSIC_IN_VIDEO:
            logger.info(f"🎵 Adding music: {Path(music).name}")
            return ["ffmpeg","-y","-loop","1","-i",image_path,"-i",music,
                    "-vf",vf,"-c:v","libx264","-preset","medium","-crf","18",
                    "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",
                    "-af",f"loudnorm=I=-14:TP=-1:LRA=11,afade=t=out:st={d-1}:d=1",
                    "-shortest","-t",str(d),"-r",str(fps),output_path]
        else:
            if not music:
                logger.info("🔇 No music — silent video")
            return ["ffmpeg","-y","-loop","1","-i",image_path,
                    "-vf",vf,"-c:v","libx264","-preset","medium","-crf","18",
                    "-pix_fmt","yuv420p","-t",str(d),"-r",str(fps),"-an",output_path]

    def _simple_video(self, image_path, output_path):
        try:
            d = config.VIDEO_DURATION_SECONDS
            w, h, fps = config.VIDEO_WIDTH, config.VIDEO_HEIGHT, config.VIDEO_FPS
            cmd = ["ffmpeg","-y","-loop","1","-i",image_path,
                   "-vf",f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
                   "-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",
                   "-t",str(d),"-r",str(fps),"-an",output_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and Path(output_path).exists():
                self.last_video_path = output_path
                logger.success(f"✅ Simple video created: {output_path}")
                return output_path
            logger.error(f"Simple FFmpeg failed: {result.stderr[:300]}")
        except Exception as e:
            logger.error(f"Simple video failed: {e}")
        return ""

    def _get_music(self):
        exts = {".mp3",".wav",".aac",".m4a",".ogg",".flac"}
        files = [f for f in config.MUSIC_DIR.iterdir() if f.suffix.lower() in exts] if config.MUSIC_DIR.exists() else []
        return str(random.choice(files)) if files else ""

    def _check_ffmpeg(self):
        try:
            return subprocess.run(["ffmpeg","-version"],capture_output=True,timeout=10).returncode == 0
        except Exception:
            return False
