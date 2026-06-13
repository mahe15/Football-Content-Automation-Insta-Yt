"""
BiscoFootball AI Automation — Main Orchestrator
Entry point: schedules and runs the full content pipeline.

Pipeline: Collect → Candidates → Score → Research → Image → Caption → Video → Publish → Notify

Usage:
    python main.py              # Start with scheduler + Telegram bot
    python main.py --run        # Run pipeline once immediately
    python main.py --test       # Dry run (no publishing)
"""

import asyncio
import sys
import signal
import traceback
from datetime import datetime
from loguru import logger

import config

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(
    str(config.LOG_FILE),
    rotation=config.LOG_ROTATION,
    retention=config.LOG_RETENTION,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {module}:{function}:{line} | {message}",
)

# Import modules
from modules.collector import EventCollector
from modules.candidates import CandidateGenerator
from modules.scorer import ViralScorer
from modules.researcher import ContentResearcher
from modules.chatgpt_image import ImageGenerator
from modules.caption import CaptionGenerator
from modules.video import VideoCreator
from modules.publisher_ig import InstagramPublisher
from modules.publisher_yt import YouTubePublisher
from modules.telegram_bot import TelegramBot
from modules.notifier import get_notifier
from modules.dedup import DedupChecker
from modules.chatgpt_browser import close_chatgpt


class BiscoFootballPipeline:
    """Main pipeline orchestrator."""

    def __init__(self):
        self.collector = EventCollector()
        self.candidate_gen = CandidateGenerator()
        self.scorer = ViralScorer()
        self.researcher = ContentResearcher()
        self.image_gen = ImageGenerator()
        self.caption_gen = CaptionGenerator()
        self.video_creator = VideoCreator()
        self.ig_publisher = InstagramPublisher()
        self.yt_publisher = YouTubePublisher()
        self.dedup = DedupChecker()
        self.notifier = get_notifier()
        self.telegram_bot = TelegramBot(pipeline_callback=self.run_pipeline)
        self.is_running = False
        self.dry_run = False

    async def run_pipeline(self, manual_topic: str = None):
        """Execute the full content pipeline."""
        if self.is_running:
            logger.warning("Pipeline already running — skipping")
            return

        self.is_running = True
        self.telegram_bot.is_running = True
        start_time = datetime.now()

        results = {
            "title": "",
            "score": 0,
            "ig_url": "",
            "yt_url": "",
        }

        try:
            self.notifier.notify_pipeline_start()
            logger.info("=" * 60)
            logger.info("🚀 PIPELINE STARTED")
            logger.info("=" * 60)

            # ============================================
            # STEP 1: Collect or use manual topic
            # ============================================
            if manual_topic:
                logger.info(f"🎯 Manual topic: {manual_topic}")
                self.telegram_bot.current_task = "Manual Research"
                events = [{"title": manual_topic, "source": "Manual", "category": "manual", "details": manual_topic}]
                candidates = [{"title": manual_topic, "category": "manual", "hook": manual_topic, "data": [], "viral_angle": manual_topic}]

                # Skip to scoring (auto-pass for manual)
                selected = candidates[0]
                selected["score"] = 10.0
                selected["selection_reason"] = "Manual override"
            else:
                # STEP 1a: Collect events
                self.telegram_bot.current_task = "Collecting Events"
                logger.info("📡 STEP 1: Collecting football events...")
                events = await self.collector.collect_all()

                if not events:
                    logger.warning("No events collected — skipping cycle")
                    self.notifier.notify_error("Collection", "No events found from any source")
                    return

                logger.info(f"📊 Collected {len(events)} events")

                # STEP 2: Generate candidates
                self.telegram_bot.current_task = "Generating Candidates"
                logger.info("💡 STEP 2: Generating content candidates...")
                candidates = await self.candidate_gen.generate(events)

                if not candidates:
                    logger.warning("No candidates generated — skipping cycle")
                    self.notifier.notify_error("Candidates", "Failed to generate candidates")
                    return

                # Filter out duplicates before scoring
                non_duplicate_candidates = [c for c in candidates if not self.dedup.is_duplicate(c.get("title", ""))]
                if not non_duplicate_candidates:
                    logger.warning("All candidates are duplicates — skipping cycle")
                    self.notifier.send_text("⚠️ All candidates are duplicates — skipping cycle")
                    return

                # STEP 3: Score and select
                self.telegram_bot.current_task = "Scoring Candidates"
                logger.info(f"🏆 STEP 3: Scoring {len(non_duplicate_candidates)} candidates...")
                selected = await self.scorer.score_and_select(non_duplicate_candidates)

                if not selected:
                    logger.warning("Scoring failed — skipping cycle")
                    return

                # Check threshold
                if not self.scorer.check_threshold(selected):
                    self.notifier.notify_cycle_skipped(
                        selected.get("score", 0),
                        config.VIRAL_SCORE_THRESHOLD
                    )
                    return

            # Check for duplicates
            if self.dedup.is_duplicate(selected.get("title", "")):
                logger.info("⚠️ Duplicate topic — skipping")
                self.notifier.send_text(f"⚠️ Skipped duplicate: {selected.get('title', '')}")
                return

            self.notifier.notify_content_selected(selected)
            results["title"] = selected.get("title", "")
            results["score"] = selected.get("score", 0)

            # ============================================
            # STEP 4: Research
            # ============================================
            self.telegram_bot.current_task = "Researching Topic"
            logger.info("🔬 STEP 4: Researching topic...")
            research = await self.researcher.research_topic(selected)
            self.notifier.notify_research_complete(research)

            if self.telegram_bot.skip_requested:
                logger.info("⏭️ Skip requested")
                self.telegram_bot.skip_requested = False
                return

            # ============================================
            # STEP 5: Generate Image
            # ============================================
            self.telegram_bot.current_task = "Generating Image"
            logger.info("🎨 STEP 5: Generating infographic...")
            image_path = await self.image_gen.generate(research)

            if not image_path:
                logger.error("Image generation failed!")
                self.notifier.notify_error("Image Generation", "Failed to generate infographic")
                return

            self.notifier.notify_image_generated(image_path, selected.get("title", ""))

            if self.telegram_bot.skip_requested:
                logger.info("⏭️ Skip requested")
                self.telegram_bot.skip_requested = False
                return

            # ============================================
            # STEP 6: Generate Caption
            # ============================================
            self.telegram_bot.current_task = "Generating Caption"
            logger.info("✍️ STEP 6: Generating captions...")
            caption_data = await self.caption_gen.generate(research)

            # ============================================
            # STEP 7: Generate Video
            # ============================================
            self.telegram_bot.current_task = "Creating Video"
            logger.info("🎬 STEP 7: Creating video...")
            video_path = self.video_creator.create(image_path)

            if video_path:
                self.notifier.notify_video_generated(video_path, selected.get("title", ""), caption_data)

            if self.telegram_bot.skip_requested:
                logger.info("⏭️ Skip requested")
                self.telegram_bot.skip_requested = False
                return

            # ============================================
            # STEP 8: Publish (skip in dry run)
            # ============================================
            if self.dry_run:
                logger.info("🧪 DRY RUN — skipping publishing")
                self.notifier.send_text("🧪 Dry run complete — no publishing")
            else:
                self.telegram_bot.current_task = "Publishing"
                logger.info("📤 STEP 8: Publishing...")

                # Instagram
                if config.ENABLE_INSTAGRAM_UPLOAD:
                    ig_caption = f"{caption_data.get('short_caption', '')}\n\n{caption_data.get('description', '')}\n\n{' '.join(caption_data.get('hashtags', []))}"
                    
                    if video_path:
                        logger.info("🎥 Publishing Reel to Instagram...")
                        ig_result = self.ig_publisher.publish_reel(video_path, ig_caption)
                        if ig_result and "id" in ig_result:
                            results["ig_url"] = self.ig_publisher.last_post_url
                            self.notifier.notify_upload_complete("Instagram", results["ig_url"])
                        else:
                            self.notifier.notify_upload_failed("Instagram", str(ig_result.get("error", "Unknown error")))
                    elif image_path:
                        logger.info("📸 Publishing Image Post to Instagram...")
                        ig_result = self.ig_publisher.publish_post(image_path, ig_caption)
                        if ig_result and "id" in ig_result:
                            results["ig_url"] = self.ig_publisher.last_post_url
                            self.notifier.notify_upload_complete("Instagram", results["ig_url"])
                        else:
                            self.notifier.notify_upload_failed("Instagram", str(ig_result.get("error", "Unknown error")))

                # YouTube
                if config.ENABLE_YOUTUBE_UPLOAD and video_path:
                    yt_title = caption_data.get("youtube_title", selected.get("title", ""))
                    yt_desc = caption_data.get("youtube_description", "")
                    yt_tags = caption_data.get("youtube_tags", [])
                    yt_result = self.yt_publisher.upload_short(video_path, yt_title, yt_desc, yt_tags)

                    if yt_result and "id" in yt_result:
                        results["yt_url"] = self.yt_publisher.last_video_url
                        self.notifier.notify_upload_complete("YouTube", results["yt_url"])
                    elif yt_result:
                        self.notifier.notify_upload_failed("YouTube", str(yt_result.get("error", "")))

            # ============================================
            # STEP 9: Record & Report
            # ============================================
            self.dedup.record_published(
                title=selected.get("title", ""),
                category=selected.get("category", ""),
                score=selected.get("score", 0),
                urls={"instagram": results["ig_url"], "youtube": results["yt_url"]},
            )

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ PIPELINE COMPLETE in {elapsed:.0f}s")
            logger.info("=" * 60)

            results["elapsed_seconds"] = elapsed
            self.notifier.notify_pipeline_complete(results)

        except Exception as e:
            logger.error(f"❌ PIPELINE ERROR: {e}")
            logger.error(traceback.format_exc())
            self.notifier.notify_error("Pipeline", str(e))

        finally:
            self.is_running = False
            self.telegram_bot.is_running = False
            self.telegram_bot.current_task = None

    async def start(self, run_once=False, dry_run=False):
        """Start the system."""
        self.dry_run = dry_run

        logger.info("=" * 60)
        logger.info("⚽ BISCOFOOTBALL AI AUTOMATION SYSTEM")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
        logger.info(f"Schedule: Every {config.SCHEDULE_INTERVAL_MINUTES} minutes")

        self.notifier.notify_system_start()

        if run_once:
            logger.info("Running pipeline once...")
            await self.run_pipeline()
            await close_chatgpt()
            return

        # Start Telegram bot
        await self.telegram_bot.start_bot()

        # Run scheduler loop
        try:
            while True:
                logger.info(f"⏰ Running scheduled pipeline cycle...")
                await self.run_pipeline()

                wait_minutes = config.SCHEDULE_INTERVAL_MINUTES
                logger.info(f"⏳ Next cycle in {wait_minutes} minutes...")

                # Wait in 10-second intervals (allows Telegram bot to process)
                for _ in range(wait_minutes * 6):
                    await asyncio.sleep(10)

        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt")
        finally:
            await self.telegram_bot.stop_bot()
            await close_chatgpt()
            logger.info("🔒 System shutdown complete")


async def main():
    """Entry point."""
    pipeline = BiscoFootballPipeline()

    run_once = "--run" in sys.argv
    dry_run = "--test" in sys.argv

    await pipeline.start(run_once=run_once, dry_run=dry_run)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
