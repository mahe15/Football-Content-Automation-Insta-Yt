"""
BiscoFootball AI Automation — Central Configuration
All toggle flags and settings in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================
# BASE PATHS
# ============================================
BASE_DIR = Path(__file__).parent
CONTENT_DIR = BASE_DIR / "content"
IMAGES_DIR = CONTENT_DIR / "images"
VIDEOS_DIR = CONTENT_DIR / "videos"
CAPTIONS_DIR = CONTENT_DIR / "captions"
MUSIC_DIR = CONTENT_DIR / "music"
LOGS_DIR = CONTENT_DIR / "logs"
UPLOADS_DIR = CONTENT_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"

# Ensure all dirs exist
for d in [IMAGES_DIR, VIDEOS_DIR, CAPTIONS_DIR, MUSIC_DIR, LOGS_DIR, UPLOADS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================
# FEATURE TOGGLES (True/False)
# ============================================

# --- Data Collection Sources ---
ENABLE_FOOTBALL_API = True           # api-football.com
ENABLE_GOOGLE_TRENDS = True          # Google Trends scraping
ENABLE_REDDIT_SCRAPING = True        # Reddit r/soccer
ENABLE_RSS_FEEDS = True              # Football RSS feeds

# --- AI Layer ---
ENABLE_CHATGPT_SCORING = True        # Viral scoring via ChatGPT
ENABLE_CHATGPT_RESEARCH = True       # Deep research via ChatGPT
ENABLE_CHATGPT_IMAGE = True          # Image generation via ChatGPT
ENABLE_CHATGPT_CAPTION = True        # Caption generation via ChatGPT

# --- Content Generation ---
ENABLE_VIDEO_GENERATION = True       # FFmpeg video creation
ENABLE_MUSIC_IN_VIDEO = True         # Add music to video (disable if no music files)

# --- Publishing ---
ENABLE_INSTAGRAM_UPLOAD = True       # Instagram publishing
ENABLE_YOUTUBE_UPLOAD = True         # YouTube Shorts publishing

# --- Telegram ---
ENABLE_TELEGRAM_BOT = True           # Telegram control center
ENABLE_TELEGRAM_NOTIFICATIONS = True # Telegram status notifications

# --- Smart Rules ---
ENABLE_DEDUP_CHECK = True            # Duplicate content checking
TOPIC_COOLDOWN_DAYS = 30             # Days before same topic can repeat

# ============================================
# SCHEDULING
# ============================================
SCHEDULE_INTERVAL_MINUTES = 30       # Run pipeline every N minutes

# ============================================
# SCORING
# ============================================
VIRAL_SCORE_THRESHOLD = float(os.getenv("VIRAL_SCORE_THRESHOLD", "7.0"))
NUM_CANDIDATES = 5                   # Number of content candidates per cycle

# ============================================
# VIDEO SETTINGS
# ============================================
VIDEO_DURATION_SECONDS = 6
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1350
VIDEO_FPS = 30
ZOOM_START = 1.05
ZOOM_END = 1.15

# ============================================
# INFOGRAPHIC SETTINGS
# ============================================
INFOGRAPHIC_WIDTH = 1080
INFOGRAPHIC_HEIGHT = 1440            # 3:4 aspect ratio
WATERMARK_TEXT = "biscofootball"

# ============================================
# API CREDENTIALS
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

YOUTUBE_CLIENT_SECRET_PATH = os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "client_secret.json")

CHATGPT_EMAIL = os.getenv("CHATGPT_EMAIL", "")
CHATGPT_PASSWORD = os.getenv("CHATGPT_PASSWORD", "")

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")

# ============================================
# URLS
# ============================================
CHATGPT_URL = "https://chatgpt.com"
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"

# Reddit
REDDIT_SOCCER_URL = "https://www.reddit.com/r/soccer/hot.json"
REDDIT_FOOTBALL_URL = "https://www.reddit.com/r/football/hot.json"

# RSS Feeds
RSS_FEEDS = [
    "https://www.goal.com/feeds/en/news",
    "https://www.espn.com/espn/rss/soccer/news",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
]

# Google Trends
GOOGLE_TRENDS_URL = "https://trends.google.com/trending?geo=US&category=20"  # Sports category

# ============================================
# CONTENT PRIORITIES
# ============================================
PRIORITY_TOPICS = [
    "World Cup",
    "Records",
    "Comparisons",
    "Rankings",
    "Shocking statistics",
    "Historical events",
    "Predictions",
    "Legendary players",
]

# ============================================
# LOGGING
# ============================================
LOG_FILE = LOGS_DIR / "biscofootball.log"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "30 days"
