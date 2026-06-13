"""
BiscoFootball — Telegram Bot Control Center
Commands: /start /status /run /skip /news /logs /upload /man <content>
"""

import asyncio
import json
import traceback
from datetime import datetime
from loguru import logger

try:
    from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
    )
except ImportError:
    logger.warning("python-telegram-bot not installed")

import config
from modules.dedup import DedupChecker


class TelegramBot:
    """Telegram bot for controlling the BiscoFootball pipeline."""

    def __init__(self, pipeline_callback=None):
        """
        Args:
            pipeline_callback: async function to run the pipeline.
                              Signature: async def run_pipeline(manual_topic=None)
        """
        self.pipeline_callback = pipeline_callback
        self.app = None
        self.is_running = False
        self.current_task = None
        self.skip_requested = False

    async def start_bot(self):
        """Start the Telegram bot."""
        if not config.ENABLE_TELEGRAM_BOT:
            logger.info("⏭️ Telegram bot disabled")
            return

        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("No Telegram bot token configured")
            return

        logger.info("🤖 Starting Telegram bot...")

        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("run", self._cmd_run))
        self.app.add_handler(CommandHandler("skip", self._cmd_skip))
        self.app.add_handler(CommandHandler("news", self._cmd_news))
        self.app.add_handler(CommandHandler("logs", self._cmd_logs))
        self.app.add_handler(CommandHandler("upload", self._cmd_upload))
        self.app.add_handler(CommandHandler("man", self._cmd_manual))
        self.app.add_handler(CommandHandler("music", self._cmd_music))
        self.app.add_handler(CommandHandler("toggles", self._cmd_toggles))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CallbackQueryHandler(self._button_callback))

        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        logger.success("✅ Telegram bot started!")

    async def stop_bot(self):
        """Stop the Telegram bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("🤖 Telegram bot stopped")

    # --- Command Handlers ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system status and welcome message."""
        dedup = DedupChecker()
        stats = dedup.get_stats()

        text = (
            "⚽ <b>BiscoFootball AI Automation</b>\n\n"
            f"📊 Schedule: Every {config.SCHEDULE_INTERVAL_MINUTES} min\n"
            f"🎯 Threshold: {config.VIRAL_SCORE_THRESHOLD}\n"
            f"📸 Instagram: {'✅ ON' if config.ENABLE_INSTAGRAM_UPLOAD else '❌ OFF'}\n"
            f"📺 YouTube: {'✅ ON' if config.ENABLE_YOUTUBE_UPLOAD else '❌ OFF'}\n"
            f"🎨 ChatGPT Image: {'✅ ON' if config.ENABLE_CHATGPT_IMAGE else '❌ OFF'}\n\n"
            f"📈 <b>Stats</b>\n"
            f"Total published: {stats['total_published']}\n"
            f"Last 7 days: {stats['last_7_days']}\n"
            f"Last 30 days: {stats['last_30_days']}\n\n"
            "📋 <b>Commands</b>\n"
            "/status — Pipeline status\n"
            "/run — Run pipeline now\n"
            "/skip — Cancel current task\n"
            "/news — Latest events\n"
            "/logs — Recent logs\n"
            "/upload — Upload latest content\n"
            "/man &lt;topic&gt; — Manual content\n"
            "/music &lt;url&gt; — Download audio\n"
            "/toggles — View feature flags\n"
            "/help — Show help"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current pipeline status."""
        status = "🟢 Running" if self.is_running else "🔵 Idle"
        task = self.current_task or "None"

        # Check latest data files
        events_exists = (config.DATA_DIR / "latest_events.json").exists()
        research_exists = (config.DATA_DIR / "latest_research.json").exists()

        text = (
            f"📊 <b>Pipeline Status</b>\n\n"
            f"Status: {status}\n"
            f"Current Task: {task}\n\n"
            f"📂 <b>Data Files</b>\n"
            f"Events: {'✅' if events_exists else '❌'}\n"
            f"Research: {'✅' if research_exists else '❌'}\n"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Trigger immediate pipeline run."""
        if self.is_running:
            await update.message.reply_text("⚠️ Pipeline is already running!")
            return

        await update.message.reply_text("🚀 Starting pipeline run...")

        if self.pipeline_callback:
            asyncio.create_task(self._run_pipeline_safe())
        else:
            await update.message.reply_text("❌ Pipeline callback not configured")

    async def _run_pipeline_safe(self, manual_topic=None):
        """Run pipeline with error handling."""
        try:
            self.is_running = True
            if self.pipeline_callback:
                await self.pipeline_callback(manual_topic=manual_topic)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.is_running = False
            self.current_task = None

    async def _cmd_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current task."""
        if not self.is_running:
            await update.message.reply_text("ℹ️ No pipeline running to skip.")
            return
        self.skip_requested = True
        await update.message.reply_text("⏭️ Skip requested — will cancel after current step.")

    async def _cmd_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show latest collected events."""
        events_path = config.DATA_DIR / "latest_events.json"
        if not events_path.exists():
            await update.message.reply_text("ℹ️ No events collected yet. Run /run first.")
            return

        try:
            with open(events_path, "r", encoding="utf-8") as f:
                events = json.load(f)

            text = "📰 <b>Latest Events</b>\n\n"
            for i, e in enumerate(events[:10], 1):
                text += f"{i}. [{e.get('source', '')}] {e.get('title', '')}\n"

            text += f"\nTotal: {len(events)} events"
            await update.message.reply_text(text, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error reading events: {e}")

    async def _cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent log entries."""
        log_path = config.LOG_FILE
        if not log_path.exists():
            await update.message.reply_text("ℹ️ No logs yet.")
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            recent = lines[-20:]  # Last 20 lines
            text = "📋 <b>Recent Logs</b>\n\n<code>" + "".join(recent)[-3500:] + "</code>"
            await update.message.reply_text(text, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error reading logs: {e}")

    async def _cmd_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Upload latest generated content."""
        await update.message.reply_text("📤 Uploading latest content...")

        if self.pipeline_callback:
            asyncio.create_task(self._run_pipeline_safe())
        else:
            await update.message.reply_text("❌ Pipeline callback not configured")

    async def _cmd_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual content pipeline: /man <content topic>"""
        if not context.args:
            await update.message.reply_text(
                "Usage: /man <topic>\n"
                "Example: /man Messi vs Ronaldo World Cup comparison"
            )
            return

        topic = " ".join(context.args)
        await update.message.reply_text(f"🎯 Manual pipeline for: <b>{topic}</b>", parse_mode="HTML")

        if self.pipeline_callback:
            asyncio.create_task(self._run_pipeline_safe(manual_topic=topic))
        else:
            await update.message.reply_text("❌ Pipeline callback not configured")

    async def _cmd_music(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Download music from a link: /music <url>"""
        if not context.args:
            await update.message.reply_text(
                "Usage: /music <url>\n"
                "Example: /music https://www.instagram.com/reel/DZT4POQttCp/"
            )
            return

        url = context.args[0]
        await update.message.reply_text(f"⏳ Downloading audio from: {url}...")

        try:
            cmd = [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "-o", str(config.MUSIC_DIR / "%(id)s.%(ext)s"),
                url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=180)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                await update.message.reply_text("❌ Download timed out after 3 minutes.")
                return
            
            if process.returncode == 0:
                await update.message.reply_text("✅ Music downloaded successfully and stored in the music folder!")
            else:
                err_msg = stderr.decode(errors="ignore").strip()[:300]
                await update.message.reply_text(f"❌ Failed to download audio. Error:\n<code>{err_msg}</code>", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to download music via Telegram: {e}")
            await update.message.reply_text(f"❌ Exception occurred: {e}")

    async def _cmd_toggles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all feature toggle states with inline button to toggle Instagram upload."""
        status_ig = "✅ Enabled" if config.ENABLE_INSTAGRAM_UPLOAD else "❌ Disabled"
        
        text = (
            "🔧 <b>Feature Toggles</b>\n\n"
            f"📸 <b>Instagram Upload:</b> {status_ig}\n"
            f"⚽ Football API: {'✅' if config.ENABLE_FOOTBALL_API else '❌'}\n"
            f"📈 Google Trends: {'✅' if config.ENABLE_GOOGLE_TRENDS else '❌'}\n"
            f"🔴 Reddit: {'✅' if config.ENABLE_REDDIT_SCRAPING else '❌'}\n"
            f"📰 RSS Feeds: {'✅' if config.ENABLE_RSS_FEEDS else '❌'}\n"
            f"🏆 ChatGPT Scoring: {'✅' if config.ENABLE_CHATGPT_SCORING else '❌'}\n"
            f"🔬 ChatGPT Research: {'✅' if config.ENABLE_CHATGPT_RESEARCH else '❌'}\n"
            f"🎨 ChatGPT Image: {'✅' if config.ENABLE_CHATGPT_IMAGE else '❌'}\n"
            f"✍️ ChatGPT Caption: {'✅' if config.ENABLE_CHATGPT_CAPTION else '❌'}\n"
            f"🎬 Video Gen: {'✅' if config.ENABLE_VIDEO_GENERATION else '❌'}\n"
            f"🎵 Music in Video: {'✅' if config.ENABLE_MUSIC_IN_VIDEO else '❌'}\n"
            f"📺 YouTube Shorts: {'✅' if config.ENABLE_YOUTUBE_UPLOAD else '❌'}\n"
            f"🔁 Dedup Check: {'✅' if config.ENABLE_DEDUP_CHECK else '❌'}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📸 Enable IG Upload", callback_data="ig_on"),
                InlineKeyboardButton("📸 Disable IG Upload", callback_data="ig_off")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks to toggle Instagram upload."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data == "ig_on":
            config.ENABLE_INSTAGRAM_UPLOAD = True
            self._update_env_var("ENABLE_INSTAGRAM_UPLOAD", "True")
            await query.edit_message_text(
                "📸 <b>Instagram Upload:</b> ✅ Enabled\n\nRun /toggles to modify again.",
                parse_mode="HTML"
            )
        elif data == "ig_off":
            config.ENABLE_INSTAGRAM_UPLOAD = False
            self._update_env_var("ENABLE_INSTAGRAM_UPLOAD", "False")
            await query.edit_message_text(
                "📸 <b>Instagram Upload:</b> ❌ Disabled\n\nRun /toggles to modify again.",
                parse_mode="HTML"
            )

    def _update_env_var(self, name: str, value: str):
        """Update a variable inside the .env file."""
        env_path = config.BASE_DIR / ".env"
        if not env_path.exists():
            return
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
            updated = False
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{name}="):
                    new_lines.append(f"{name}={value}")
                    updated = True
                else:
                    new_lines.append(line)
            if not updated:
                new_lines.append(f"{name}={value}")
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            logger.info(f"Updated .env var {name} to {value}")
        except Exception as e:
            logger.error(f"Failed to update .env: {e}")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message."""
        text = (
            "📖 <b>BiscoFootball Commands</b>\n\n"
            "/start — System overview\n"
            "/status — Current pipeline status\n"
            "/run — Run full pipeline now\n"
            "/skip — Cancel current task\n"
            "/news — Show latest events\n"
            "/logs — Show recent logs\n"
            "/upload — Upload latest content\n"
            "/man &lt;topic&gt; — Manual content on any topic\n"
            "/music &lt;url&gt; — Download reel/video audio\n"
            "/toggles — View feature flags\n"
            "/help — This message\n\n"
            "Example:\n"
            "<code>/music https://www.instagram.com/reel/DZT4POQttCp/</code>"
        )
        await update.message.reply_text(text, parse_mode="HTML")
