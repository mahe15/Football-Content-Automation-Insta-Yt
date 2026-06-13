"""
BiscoFootball — ChatGPT Image Generation
Generates premium football infographic images via ChatGPT's image generation.
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from loguru import logger
from modules.chatgpt_browser import get_chatgpt
import config


class ImageGenerator:
    """Generates infographic images via ChatGPT image generation."""

    def __init__(self):
        self.last_image_path = ""

    async def generate(self, research: dict) -> str:
        """Generate a premium football infographic image via ChatGPT."""
        if not config.ENABLE_CHATGPT_IMAGE:
            logger.info("⏭️ Image generation disabled")
            return ""

        logger.info("🎨 Generating infographic via ChatGPT...")

        # Build the image generation prompt
        prompt = self._build_image_prompt(research)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() else "_" for c in research.get("title", "post")[:30])
        filename = f"{timestamp}_{safe_title}.png"
        save_path = config.IMAGES_DIR / filename

        try:
            chatgpt = await get_chatgpt()
            result = await chatgpt.generate_image(prompt, save_path, wait_timeout=180)

            if result:
                self.last_image_path = result
                logger.success(f"✅ Infographic generated: {result}")
                return result
            else:
                logger.error("Image generation returned empty result")

                # Retry once with a simplified prompt
                logger.info("🔄 Retrying with simplified prompt...")
                simple_prompt = self._build_simple_prompt(research)
                result = await chatgpt.generate_image(simple_prompt, save_path, wait_timeout=180)

                if result:
                    self.last_image_path = result
                    logger.success(f"✅ Infographic generated (retry): {result}")
                    return result

                return ""

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ""

    def _build_image_prompt(self, research: dict) -> str:
        """Build a detailed prompt for ChatGPT image generation matching the reference style."""
        title = research.get("title", "Football Stats")
        infographic_data = research.get("infographic_data", {})

        headline = infographic_data.get("headline", title)
        subheadline = infographic_data.get("subheadline", "")
        main_stats = infographic_data.get("main_stats", [])
        comparisons = infographic_data.get("comparison_items", [])
        footer = infographic_data.get("footer_text", "Follow @biscofootball")

        facts = research.get("facts", [])
        statistics = research.get("statistics", [])

        # Build data section
        data_text = ""
        if main_stats:
            data_text += "Key Statistics:\n"
            for stat in main_stats:
                data_text += f"- {stat}\n"

        if comparisons:
            data_text += "\nComparisons:\n"
            for comp in comparisons:
                data_text += f"- {comp.get('name', '')}: {comp.get('value', '')}\n"

        if facts:
            data_text += "\nFacts:\n"
            for fact in facts[:4]:
                data_text += f"- {fact}\n"

        prompt = f"""Create a premium football infographic image with these specifications:

CONTENT:
Headline: {headline}
{f'Subheadline: {subheadline}' if subheadline else ''}
{data_text}
{f'Footer: {footer}' if footer else ''}
Watermark: biscofootball

DESIGN REQUIREMENTS:
- Aspect ratio: 3:4 (portrait, {config.INFOGRAPHIC_WIDTH}x{config.INFOGRAPHIC_HEIGHT} pixels)
- Style: Premium sports media infographic (like ESPN, Bleacher Report, 433 style)
- Background: Dark gradient (very dark navy/black, #0a0a0a to #1a2a3a)
- Typography: Bold, high-contrast white text with accent colors (gold, green, or red)
- Layout: Clean, professional, mobile-first design
- Include relevant football imagery (player silhouettes, team badges, trophies, stadiums)
- Strong visual hierarchy — headline should be the largest text
- Use contrasting sections/cards with slight transparency
- Include country flags if relevant
- Use big bold numbers for statistics
- Professional sports broadcast quality design
- No generic clip art — real football aesthetics
- High contrast for mobile readability
- Modern glassmorphism or card-based layout elements

IMPORTANT: This should look like a professional sports network graphic, NOT a simple text on background.
Include the watermark "biscofootball" in small text at the bottom.

Generate exactly ONE image. Do not ask any questions."""

        return prompt

    def _build_simple_prompt(self, research: dict) -> str:
        """Build a simpler fallback prompt."""
        title = research.get("title", "Football Stats")
        facts = research.get("facts", [])
        facts_text = "\n".join(f"• {f}" for f in facts[:3])

        return f"""Create a football infographic image:

Title: {title}
{facts_text}

Design: Dark background, bold white text, football theme, 3:4 aspect ratio, sports media style, premium quality.
Watermark: biscofootball

Generate the image now."""
