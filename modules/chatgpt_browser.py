"""
BiscoFootball — ChatGPT Browser Automation via Playwright
Handles all interactions with ChatGPT website: text prompts and image generation.
"""

import asyncio
import time
import re
import os
import json
from pathlib import Path
from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
except ImportError:
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")

import config


class ChatGPTBrowser:
    """Automates ChatGPT via Playwright for text and image generation."""

    def __init__(self):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.playwright = None
        self.is_logged_in = False
        self.session_dir = config.DATA_DIR / "chatgpt_session"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    async def start(self):
        """Launch browser and navigate to ChatGPT."""
        logger.info("🌐 Starting ChatGPT browser with persistent context...")
        self.playwright = await async_playwright().start()

        user_data_dir = self.session_dir / "chrome_profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        # Launch using persistent context to make it a normal (non-incognito) browser
        self.context = await self.playwright.chromium.launch_persistent_context(
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
        
        # In launch_persistent_context, a default page is already created
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Navigate to ChatGPT
        await self.page.goto(config.CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Check if logged in
        await self._check_login_status()

    async def _check_login_status(self):
        """Check if we're logged into ChatGPT."""
        try:
            logger.info("⏳ Checking ChatGPT login status...")
            await asyncio.sleep(5)  # Let any redirects settle

            # 1. Look for prompt-textarea first
            try:
                await self.page.wait_for_selector(
                    'div[id="prompt-textarea"], textarea[id="prompt-textarea"], '
                    '[contenteditable="true"][id="prompt-textarea"]',
                    timeout=15000
                )
                self.is_logged_in = True
                logger.success("✅ Already logged in to ChatGPT!")
                await self._save_session()
                return
            except Exception:
                pass

            # 2. Check current URL and buttons if not found
            current_url = self.page.url
            if "auth" in current_url or "login" in current_url:
                logger.info("🔐 Login/Auth URL detected. Attempting login...")
                await self._login()
            else:
                # Look for a login button
                login_btn = await self.page.query_selector('a[href*="login"], button:has-text("Log in"), button:has-text("Sign up")')
                if login_btn:
                    logger.info("🔐 Login button found on page. Attempting login...")
                    await self._login()
                else:
                    # Final check for text area
                    chat_box = await self.page.query_selector('div[id="prompt-textarea"], textarea[id="prompt-textarea"]')
                    if chat_box:
                        self.is_logged_in = True
                        logger.success("✅ Already logged in to ChatGPT!")
                        await self._save_session()
                    else:
                        logger.info("🔐 Could not find chat input. Attempting login...")
                        await self._login()

        except Exception as e:
            logger.error(f"Login check failed: {e}")
            await self._login()

    async def _login(self):
        """Log into ChatGPT with credentials."""
        try:
            email = config.CHATGPT_EMAIL
            password = config.CHATGPT_PASSWORD

            is_placeholder = (
                not email or not password or
                "your_chatgpt_email" in email or
                "your_chatgpt_password" in password or
                email == ""
            )

            if is_placeholder:
                logger.warning("⚠️ No valid ChatGPT credentials in .env — please log in manually in the browser window")
                logger.info("⏳ Waiting 120 seconds for manual login...")
                await asyncio.sleep(120)
                await self._check_post_login()
                return

            # Navigate to login
            await self.page.goto("https://chatgpt.com/auth/login", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

            # Click "Log in" button
            login_buttons = await self.page.query_selector_all('button')
            for btn in login_buttons:
                text = await btn.inner_text()
                if "log in" in text.lower():
                    await btn.click()
                    break

            await asyncio.sleep(3)

            # Enter email
            email_input = await self.page.wait_for_selector('input[name="email"], input[type="email"], #email-input', timeout=15000)
            await email_input.fill(email)

            # Click continue
            continue_btn = await self.page.query_selector('button[type="submit"]')
            if continue_btn:
                await continue_btn.click()
            await asyncio.sleep(3)

            # Enter password
            password_input = await self.page.wait_for_selector('input[name="password"], input[type="password"]', timeout=15000)
            await password_input.fill(password)

            # Click continue/login
            submit_btn = await self.page.query_selector('button[type="submit"]')
            if submit_btn:
                await submit_btn.click()
            await asyncio.sleep(8)

            await self._check_post_login()

        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            logger.info("⏳ Waiting 120s for manual login...")
            await asyncio.sleep(120)
            await self._check_post_login()

    async def _check_post_login(self):
        """Verify login succeeded and save session."""
        try:
            await self.page.wait_for_selector(
                'div[id="prompt-textarea"], textarea[id="prompt-textarea"], '
                '[contenteditable="true"][id="prompt-textarea"]',
                timeout=30000
            )
            self.is_logged_in = True
            logger.success("✅ Successfully logged into ChatGPT!")
            await self._save_session()
        except Exception:
            logger.error("❌ Could not verify login. Will retry on next operation.")
            self.is_logged_in = False

    async def _save_session(self):
        """Save browser session for reuse."""
        logger.info("💾 Session automatically saved by persistent context.")

    async def new_chat(self):
        """Start a new chat conversation."""
        try:
            await self.page.goto(config.CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            logger.info("🆕 New chat started.")
        except Exception as e:
            logger.error(f"Failed to start new chat: {e}")

    async def send_prompt(self, prompt: str, wait_timeout: int = 120) -> str:
        """Send a text prompt to ChatGPT and return the response."""
        if not self.is_logged_in:
            logger.error("Not logged in to ChatGPT!")
            return ""

        try:
            logger.info(f"📝 Sending prompt ({len(prompt)} chars)...")

            # Start a new chat for clean context
            await self.new_chat()

            # Find the prompt input
            input_selector = (
                'div[id="prompt-textarea"], '
                'textarea[id="prompt-textarea"], '
                '[contenteditable="true"][id="prompt-textarea"]'
            )
            prompt_box = await self.page.wait_for_selector(input_selector, timeout=15000)

            # Clear and type the prompt
            await prompt_box.click()
            await asyncio.sleep(0.5)

            # Use fill for regular input, or set innerHTML for contenteditable
            tag = await prompt_box.evaluate("el => el.tagName.toLowerCase()")
            is_contenteditable = await prompt_box.evaluate("el => el.isContentEditable")

            if is_contenteditable:
                try:
                    await prompt_box.fill(prompt)
                except Exception:
                    # Fallback: type in chunks if fill fails
                    await prompt_box.evaluate("el => el.innerHTML = ''")
                    chunk_size = 200
                    for i in range(0, len(prompt), chunk_size):
                        chunk = prompt[i:i + chunk_size]
                        await self.page.keyboard.type(chunk, delay=5)
                        await asyncio.sleep(0.1)
            else:
                await prompt_box.fill(prompt)

            await asyncio.sleep(1)

            # Click send button
            send_selectors = [
                'button[data-testid="send-button"]',
                'button[aria-label="Send prompt"]',
                'button.btn-send',
            ]

            sent = False
            for sel in send_selectors:
                try:
                    send_btn = await self.page.query_selector(sel)
                    if send_btn:
                        is_visible = await send_btn.is_visible()
                        if is_visible:
                            await send_btn.click()
                            sent = True
                            break
                except Exception:
                    continue

            if not sent:
                # Fallback: press Enter
                await self.page.keyboard.press("Enter")

            logger.info("⏳ Waiting for response...")

            # Wait for response to complete
            response = await self._wait_for_response(wait_timeout)
            logger.success(f"✅ Got response ({len(response)} chars)")
            return response

        except Exception as e:
            logger.error(f"❌ Failed to send prompt: {e}")
            return ""

    async def _wait_for_response(self, timeout: int = 120) -> str:
        """Wait for ChatGPT to finish responding and extract text."""
        start = time.time()
        last_text = ""
        stable_count = 0

        await asyncio.sleep(5)  # Initial wait for response to start

        while time.time() - start < timeout:
            try:
                # Get all assistant message elements
                messages = await self.page.query_selector_all(
                    '[data-message-author-role="assistant"] .markdown, '
                    '.agent-turn .markdown, '
                    '[data-testid^="conversation-turn-"] .markdown'
                )

                if messages:
                    # Get the last (most recent) message
                    last_msg = messages[-1]
                    current_text = await last_msg.inner_text()

                    if current_text and current_text == last_text:
                        stable_count += 1
                        if stable_count >= 3:  # Text stable for ~3 seconds
                            # Check if streaming indicator is gone
                            streaming = await self.page.query_selector(
                                'button[aria-label="Stop generating"], '
                                '.result-streaming, '
                                '[data-testid="stop-button"]'
                            )
                            if not streaming:
                                return current_text.strip()
                    else:
                        stable_count = 0
                        last_text = current_text

            except Exception:
                pass

            await asyncio.sleep(1)

        # Return whatever we have after timeout
        return last_text.strip() if last_text else ""

    async def generate_image(self, prompt: str, save_path: Path, wait_timeout: int = 180) -> str:
        """Generate an image via ChatGPT and download it."""
        if not self.is_logged_in:
            logger.error("Not logged in to ChatGPT!")
            return ""

        try:
            logger.info("🎨 Generating image via ChatGPT...")

            # Send image generation prompt
            await self.new_chat()

            input_selector = (
                'div[id="prompt-textarea"], '
                'textarea[id="prompt-textarea"], '
                '[contenteditable="true"][id="prompt-textarea"]'
            )
            prompt_box = await self.page.wait_for_selector(input_selector, timeout=15000)
            await prompt_box.click()
            await asyncio.sleep(0.5)

            # Type the image prompt
            is_contenteditable = await prompt_box.evaluate("el => el.isContentEditable")
            if is_contenteditable:
                try:
                    await prompt_box.fill(prompt)
                except Exception:
                    await prompt_box.evaluate("el => el.innerHTML = ''")
                    chunk_size = 200
                    for i in range(0, len(prompt), chunk_size):
                        chunk = prompt[i:i + chunk_size]
                        await self.page.keyboard.type(chunk, delay=5)
                        await asyncio.sleep(0.1)
            else:
                await prompt_box.fill(prompt)

            await asyncio.sleep(1)

            # Send
            send_selectors = [
                'button[data-testid="send-button"]',
                'button[aria-label="Send prompt"]',
            ]
            sent = False
            for sel in send_selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        sent = True
                        break
                except Exception:
                    continue
            if not sent:
                await self.page.keyboard.press("Enter")

            logger.info("⏳ Waiting for image generation (this may take 30-90 seconds)...")

            # Wait for image to appear
            image_path = await self._wait_and_download_image(save_path, wait_timeout)
            return image_path

        except Exception as e:
            logger.error(f"❌ Image generation failed: {e}")
            return ""

    async def _wait_and_download_image(self, save_path: Path, timeout: int = 180) -> str:
        """Wait for ChatGPT to generate an image and download it."""
        start = time.time()

        while time.time() - start < timeout:
            try:
                # Look for generated images inside assistant turns
                assistant_turns = await self.page.query_selector_all(
                    '[data-message-author-role="assistant"], .agent-turn, .markdown, [data-testid^="conversation-turn-"]'
                )

                for turn in assistant_turns:
                    images = await turn.query_selector_all("img")
                    for img in images:
                        src = await img.get_attribute("src")
                        alt = await img.get_attribute("alt")
                        
                        if not src:
                            continue

                        # Filter out avatars and small icons
                        is_generated_url = any(k in src for k in ["oaidalleapiprodscus", "dalle", "oaiusercontent", "blob:", "files.oai"])
                        
                        # Bounding box check to ensure it's not a tiny icon/emoji
                        box = await img.bounding_box()
                        is_large_enough = box and box["width"] > 150 and box["height"] > 150

                        if is_generated_url or is_large_enough:
                            logger.info(f"🖼️ Found generated image element (src: {src[:50]}..., alt: {alt})")

                            # Try to download via browser evaluate (this handles blob, permissions, cookies perfectly!)
                            try:
                                download_path = await self._download_via_browser_evaluate(src, save_path)
                                if download_path:
                                    return download_path
                            except Exception as e:
                                logger.warning(f"Browser-context download failed: {e}. Trying other methods...")

                            # Try download button
                            download_path = await self._download_image_via_button(save_path)
                            if download_path:
                                return download_path

                            # Fallback: download via URL
                            if "blob:" not in src:
                                return await self._download_image_url(src, save_path)
                            else:
                                return await self._screenshot_image(img, save_path)

                # Check for generating state
                generating = await self.page.query_selector(
                    'button[aria-label="Stop generating"], .result-streaming, [data-testid="stop-button"]'
                )
                if generating:
                    logger.debug("Still generating image...")

            except Exception as e:
                logger.debug(f"Waiting for image: {e}")

            await asyncio.sleep(3)

        logger.error("⏰ Image generation timed out")
        return ""

    async def _download_via_browser_evaluate(self, url: str, save_path: Path) -> str:
        """Download image by fetching it within the page's logged-in context and converting to base64."""
        try:
            logger.info("💾 Downloading image via browser context fetch...")
            base64_data = await self.page.evaluate("""async (imgUrl) => {
                const resp = await fetch(imgUrl);
                const blob = await resp.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""", url)

            if base64_data and "," in base64_data:
                import base64
                header, encoded = base64_data.split(",", 1)
                data = base64.b64decode(encoded)
                
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(data)
                
                logger.success(f"✅ Downloaded image via browser context to: {save_path}")
                return str(save_path)
        except Exception as e:
            logger.debug(f"Browser evaluate fetch failed: {e}")
        return ""

    async def _download_image_via_button(self, save_path: Path) -> str:
        """Try to download image via ChatGPT's download button."""
        try:
            download_btns = await self.page.query_selector_all(
                'a[download], button[aria-label*="Download"], button[aria-label*="download"], a[href*="oai"]'
            )

            for btn in download_btns:
                async with self.page.expect_download(timeout=15000) as download_info:
                    await btn.click()
                download = await download_info.value
                await download.save_as(str(save_path))
                logger.success(f"✅ Image downloaded via button to: {save_path}")
                return str(save_path)
        except Exception as e:
            logger.debug(f"Download button method failed: {e}")
        return ""

    async def _download_image_url(self, url: str, save_path: Path) -> str:
        """Download image from URL."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(save_path, "wb") as f:
                            f.write(data)
                        logger.success(f"✅ Image downloaded from URL to: {save_path}")
                        return str(save_path)
        except Exception as e:
            logger.error(f"URL download failed: {e}")
        return ""

    async def _screenshot_image(self, element, save_path: Path) -> str:
        """Take a screenshot of the image element as fallback."""
        try:
            save_path = save_path.with_suffix(".png")
            await element.screenshot(path=str(save_path))
            logger.success(f"✅ Image captured via screenshot: {save_path}")
            return str(save_path)
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
        return ""

    async def close(self):
        """Close browser and cleanup."""
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("🔒 Browser closed.")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")


# ============================================
# Singleton instance for reuse
# ============================================
_instance: ChatGPTBrowser = None


async def get_chatgpt() -> ChatGPTBrowser:
    """Get or create the ChatGPT browser instance."""
    global _instance
    if _instance is None or not _instance.is_logged_in:
        _instance = ChatGPTBrowser()
        await _instance.start()
    return _instance


async def close_chatgpt():
    """Close the ChatGPT browser instance."""
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
