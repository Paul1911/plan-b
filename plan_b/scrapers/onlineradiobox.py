import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from plan_b.config import Config
from plan_b.fetch import LiveFetcher
from plan_b.models import Song
from plan_b.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class OnlineRadioBoxScraper(BaseScraper):
    """
    Scrapes the 1LIVE playlist from OnlineRadioBox and filters to the
    Plan B time window (Mon-Thu 20:00-23:00, Europe/Berlin).

    OnlineRadioBox stores playlists for the past 7 days.
    URL pattern: /de/einslive/playlist/{day_offset} where 0=today, 1=yesterday, etc.

    Fetching is delegated to a pluggable fetcher so the parsing can be tested
    and debugged offline (see plan_b.fetch).
    """

    name = "onlineradiobox"

    def __init__(self, fetcher=None):
        self.fetcher = fetcher or LiveFetcher()
        self.tz = ZoneInfo(Config.TIMEZONE)

    def scrape(self) -> list[Song]:
        """Scrape Plan B songs from the most recent show only."""
        now = datetime.now(self.tz)
        # Find the most recent day that was a Plan B show (Mon-Thu)
        for day_offset in range(7):
            target_date = now - timedelta(days=day_offset)
            if target_date.weekday() not in Config.PLAN_B_WEEKDAYS:
                continue

            songs = self._scrape_day(day_offset, target_date)
            if songs:
                day_name = target_date.strftime("%A %Y-%m-%d")
                logger.info(f"OnlineRadioBox: {len(songs)} songs from latest show ({day_name})")
                return songs

        logger.warning("OnlineRadioBox: no Plan B songs found in the last 7 days")
        return []

    def _scrape_day(self, day_offset: int, target_date: datetime) -> list[Song]:
        """Scrape a single day and filter to Plan B time window."""
        url = f"{Config.ONLINERADIOBOX_URL}{day_offset}"
        params = {"cs": "de.einslive"}

        try:
            html = self.fetcher.get(url, params=params)
        except Exception as e:
            logger.warning(f"OnlineRadioBox fetch failed for day offset {day_offset}: {e}")
            return []

        songs = self._parse_html(html, target_date)
        day_name = target_date.strftime("%A %Y-%m-%d")
        logger.info(f"OnlineRadioBox {day_name}: {len(songs)} songs in Plan B window")
        return songs

    def _parse_html(self, html: str, target_date: datetime) -> list[Song]:
        """Parse OnlineRadioBox HTML and filter to Plan B time window (20:00-23:00)."""
        soup = BeautifulSoup(html, "html.parser")
        songs = []

        # Strategy 1: Look for table rows or list items with timestamps and track info
        # OnlineRadioBox typically uses a playlist table with time and track columns
        for row in soup.select("table tr, .playlist__item, li"):
            text = row.get_text(strip=True)
            if not text:
                continue

            # Try to extract timestamp (HH:MM pattern at start)
            time_match = re.match(r"(\d{1,2}):(\d{2})", text)
            if not time_match:
                continue

            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

            # Filter to Plan B window
            if not (Config.PLAN_B_START_HOUR <= hour < Config.PLAN_B_END_HOUR):
                continue

            # Extract artist - title from the remaining text
            played_at = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Try to find a track link within this row
            track_link = row.select_one('a[href*="/track/"]')
            if track_link:
                song = self._parse_artist_title(track_link.get_text(strip=True))
                if song:
                    song.played_at = played_at
                    songs.append(song)
                continue

            # Fallback: parse from raw text (remove the timestamp prefix)
            remaining = text[time_match.end() :].strip()
            song = self._parse_artist_title(remaining)
            if song:
                song.played_at = played_at
                songs.append(song)

        # Strategy 2: If structured parsing found nothing, try broader approach
        if not songs:
            songs = self._fallback_parse(soup, target_date)

        return songs

    def _fallback_parse(self, soup: BeautifulSoup, target_date: datetime) -> list[Song]:
        """Broader fallback parsing when structured selectors fail."""
        songs = []
        # Look for any element containing time + song info patterns
        for element in soup.find_all(string=re.compile(r"\d{1,2}:\d{2}")):
            parent = element.parent
            if not parent:
                continue

            full_text = parent.get_text(strip=True)
            time_match = re.match(r"(\d{1,2}):(\d{2})\s*(.*)", full_text)
            if not time_match:
                continue

            hour = int(time_match.group(1))
            if not (Config.PLAN_B_START_HOUR <= hour < Config.PLAN_B_END_HOUR):
                continue

            remaining = time_match.group(3).strip()
            song = self._parse_artist_title(remaining)
            if song:
                song.played_at = target_date.replace(
                    hour=hour, minute=int(time_match.group(2)), second=0, microsecond=0
                )
                songs.append(song)

        return songs

    def _parse_artist_title(self, text: str) -> Song | None:
        """Parse 'Artist - Title' text into a Song."""
        for sep in [" - ", " – ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                if artist and title and len(artist) > 1 and len(title) > 1:
                    return Song(artist=artist, title=title, source=self.name)
        return None
