"""
BiscoFootball — ChatGPT Login Helper
Run this script to manually log in to ChatGPT and save your session.
This avoids typing passwords automatically and handles 2FA/Captchas.
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright

import config

async def main():
    logger.info("================================================")
    logger.info("🤖 ChatGPT Manual Login Helper")
    logger.info("================================================")
    logger.info("This script will open a browser window for you to log in to ChatGPT.")
    logger.info("Once logged in, the session will be saved for the automated bot.")
    logger.info("================================================")

    session_dir = config.DATA_DIR / "chatgpt_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    user_data_dir = session_dir / "chrome_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        logger.info("🌐 Launching Chromium browser with persistent context...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        logger.info("🔗 Navigating to ChatGPT...")
        await page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=60000)

        logger.warning("🔑 PLEASE LOG IN TO CHATGPT MANUALLY NOW in the opened browser window.")
        logger.warning("⏳ You have 90 seconds to complete the login/2FA...")

        # Wait and poll for login success
        logged_in = False
        for i in range(90):
            await asyncio.sleep(1)
            if i % 10 == 0 and i > 0:
                logger.info(f"⏳ {90 - i} seconds remaining...")
            
            # Check if chat input textarea is present (indicates successful login)
            try:
                chat_box = await page.query_selector(
                    'div[id="prompt-textarea"], textarea[id="prompt-textarea"], [contenteditable="true"][id="prompt-textarea"]'
                )
                if chat_box:
                    logged_in = True
                    logger.success("🎉 Detected successful login!")
                    break
            except Exception:
                pass

        if logged_in:
            logger.info("💾 Saving session state...")
            await asyncio.sleep(5)
            logger.success("✅ Session successfully saved in chrome_profile!")
            logger.success("You can now close this browser and run 'python main.py'!")
        else:
            logger.error("❌ Login detection timed out or failed.")

        await context.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
