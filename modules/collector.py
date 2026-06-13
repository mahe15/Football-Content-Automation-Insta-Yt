"""
BiscoFootball — Football Event Collector
Fetches trending football events from multiple sources with toggle flags.
Sources: Football API, Google Trends, Reddit, RSS Feeds
"""

import asyncio
import json
import time
import re
from datetime import datetime
from pathlib import Path
from loguru import logger

try:
    import aiohttp
except ImportError:
    pass

try:
    import feedparser
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup
except ImportError:
    pass

import config


class EventCollector:
    """Collects trending football events from multiple sources."""

    def __init__(self):
        self.events = []

    async def collect_all(self) -> list:
        """Run all enabled collectors and return aggregated events."""
        self.events = []
        tasks = []

        if config.ENABLE_FOOTBALL_API:
            tasks.append(self._collect_football_api())

        if config.ENABLE_GOOGLE_TRENDS:
            tasks.append(self._collect_google_trends())

        if config.ENABLE_REDDIT_SCRAPING:
            tasks.append(self._collect_reddit())

        if config.ENABLE_RSS_FEEDS:
            tasks.append(self._collect_rss())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Collector error: {r}")

        # Deduplicate by title similarity
        unique = self._deduplicate(self.events)
        logger.info(f"📊 Collected {len(unique)} unique events from {len(tasks)} sources")

        # Save to log
        self._save_events(unique)
        return unique

    async def _collect_football_api(self) -> None:
        """Fetch latest fixtures, standings, and top scorers from API-Football."""
        logger.info("⚽ Collecting from Football API...")
        api_key = config.FOOTBALL_API_KEY

        if not api_key:
            logger.warning("No Football API key configured")
            return

        headers = {
            "x-apisports-key": api_key,
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Current fixtures (today)
                today = datetime.now().strftime("%Y-%m-%d")
                url = f"{config.FOOTBALL_API_BASE}/fixtures?date={today}"

                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        fixtures = data.get("response", [])
                        for fix in fixtures[:15]:
                            teams = fix.get("teams", {})
                            league = fix.get("league", {})
                            home = teams.get("home", {}).get("name", "Unknown")
                            away = teams.get("away", {}).get("name", "Unknown")
                            league_name = league.get("name", "")

                            self.events.append({
                                "title": f"{home} vs {away}",
                                "source": "Football API",
                                "category": "fixture",
                                "league": league_name,
                                "details": f"{league_name}: {home} vs {away}",
                                "timestamp": datetime.now().isoformat(),
                            })

                # Top scorers from major leagues (Premier League = 39)
                now = datetime.now()
                # Most major European leagues start their season around July/August (month >= 7)
                current_season = now.year if now.month >= 7 else now.year - 1

                for league_id in [39, 140, 135, 78, 61]:  # EPL, La Liga, Serie A, Bundesliga, Ligue 1
                    url = f"{config.FOOTBALL_API_BASE}/players/topscorers?season={current_season}&league={league_id}"
                    try:
                        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                scorers = data.get("response", [])[:3]
                                for s in scorers:
                                    player = s.get("player", {})
                                    stats = s.get("statistics", [{}])[0]
                                    goals = stats.get("goals", {}).get("total", 0)
                                    self.events.append({
                                        "title": f"{player.get('name', 'Unknown')} — {goals} goals",
                                        "source": "Football API",
                                        "category": "top_scorer",
                                        "details": f"Top scorer with {goals} goals this season",
                                        "timestamp": datetime.now().isoformat(),
                                    })
                    except Exception:
                        continue

                logger.success(f"✅ Football API: {len([e for e in self.events if e['source'] == 'Football API'])} events")

        except Exception as e:
            logger.error(f"Football API error: {e}")

    async def _collect_google_trends(self) -> None:
        """Scrape trending football topics from Google Trends."""
        logger.info("📈 Collecting from Google Trends...")

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
                    )
                }
                # Use Google Trends RSS for sports
                urls = [
                    "https://trends.google.com/trending/rss?geo=US",
                    "https://trends.google.com/trending/rss?geo=GB",
                ]

                for url in urls:
                    try:
                        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                feed = feedparser.parse(text)

                                football_keywords = [
                                    "football", "soccer", "world cup", "premier league",
                                    "champions league", "messi", "ronaldo", "goal",
                                    "fifa", "transfer", "match", "league", "cup",
                                    "neymar", "mbappe", "haaland", "team", "player",
                                    "coach", "stadium", "penalty", "red card",
                                ]

                                for entry in feed.entries[:20]:
                                    title = entry.get("title", "").lower()
                                    if any(kw in title for kw in football_keywords):
                                        self.events.append({
                                            "title": entry.get("title", ""),
                                            "source": "Google Trends",
                                            "category": "trending",
                                            "details": entry.get("summary", ""),
                                            "timestamp": datetime.now().isoformat(),
                                        })
                    except Exception:
                        continue

                logger.success(f"✅ Google Trends: {len([e for e in self.events if e['source'] == 'Google Trends'])} events")

        except Exception as e:
            logger.error(f"Google Trends error: {e}")

    async def _collect_reddit(self) -> None:
        """Fetch hot posts from football subreddits."""
        logger.info("🔴 Collecting from Reddit...")

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "BiscoFootball/1.0 (by /u/biscofootball)"
                }

                subreddit_urls = [
                    config.REDDIT_SOCCER_URL,
                    config.REDDIT_FOOTBALL_URL,
                ]

                for url in subreddit_urls:
                    try:
                        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                posts = data.get("data", {}).get("children", [])

                                for post in posts[:15]:
                                    pd = post.get("data", {})
                                    title = pd.get("title", "")
                                    score = pd.get("score", 0)
                                    comments = pd.get("num_comments", 0)

                                    # Only high-engagement posts
                                    if score > 100 or comments > 50:
                                        self.events.append({
                                            "title": title,
                                            "source": "Reddit",
                                            "category": "discussion",
                                            "details": f"Score: {score}, Comments: {comments}",
                                            "upvotes": score,
                                            "timestamp": datetime.now().isoformat(),
                                        })
                    except Exception:
                        continue

                logger.success(f"✅ Reddit: {len([e for e in self.events if e['source'] == 'Reddit'])} events")

        except Exception as e:
            logger.error(f"Reddit error: {e}")

    async def _collect_rss(self) -> None:
        """Fetch latest football news from RSS feeds."""
        logger.info("📰 Collecting from RSS feeds...")

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "BiscoFootball/1.0"
                }

                for feed_url in config.RSS_FEEDS:
                    try:
                        async with session.get(feed_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                feed = feedparser.parse(text)

                                for entry in feed.entries[:10]:
                                    self.events.append({
                                        "title": entry.get("title", ""),
                                        "source": "RSS",
                                        "category": "news",
                                        "details": entry.get("summary", "")[:200],
                                        "link": entry.get("link", ""),
                                        "timestamp": datetime.now().isoformat(),
                                    })
                    except Exception:
                        continue

                logger.success(f"✅ RSS: {len([e for e in self.events if e['source'] == 'RSS'])} events")

        except Exception as e:
            logger.error(f"RSS error: {e}")

    def _deduplicate(self, events: list) -> list:
        """Remove duplicate events based on title similarity."""
        seen = set()
        unique = []

        for event in events:
            # Normalize title for comparison
            normalized = re.sub(r'[^a-zA-Z0-9\s]', '', event["title"].lower()).strip()
            # Use first 50 chars as fingerprint
            fingerprint = normalized[:50]

            if fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(event)

        return unique

    def _save_events(self, events: list):
        """Save collected events to a log file."""
        try:
            log_path = config.DATA_DIR / "latest_events.json"
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save events: {e}")


# ============================================
# Module-level test
# ============================================
if __name__ == "__main__":
    async def test():
        collector = EventCollector()
        events = await collector.collect_all()
        for e in events[:5]:
            print(f"[{e['source']}] {e['title']}")
        print(f"\nTotal: {len(events)} events")

    asyncio.run(test())
