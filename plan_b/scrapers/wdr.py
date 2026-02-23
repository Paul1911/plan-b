import logging
import re

import requests
from bs4 import BeautifulSoup

from plan_b.config import Config
from plan_b.models import Song
from plan_b.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class WDRScraper(BaseScraper):
    """
    Scrapes the WDR 1LIVE Plan B pages for song listings.

    Tries the channel playlist page first, then the day-specific show pages.
    Uses multiple CSS selector strategies since the HTML structure is unknown,
    with a regex fallback.
    """

    name = "wdr"

    # Ordered list of CSS selector strategies to try
    SELECTOR_STRATEGIES = [
        # Strategy 1: WDR typical playlist structure
        {
            "container": ".playlist .entry, .playlist-item, .musicItem, .playlistItem",
            "artist": ".artist, .interpret, .musicArtist, .playlistArtist",
            "title": ".title, .song, .musicTitle, .trackname, .playlistTitle",
        },
        # Strategy 2: Table-based layout
        {
            "container": "table.playlist tr, table tr.song, .playlistTable tr",
            "artist": "td.artist, td:nth-child(1)",
            "title": "td.title, td:nth-child(2)",
        },
        # Strategy 3: List-based layout
        {
            "container": "ul.playlist li, ol.playlist li, .songlist li, .trackList li",
            "artist": ".artist, strong, b",
            "title": ".title, em, span.song",
        },
        # Strategy 4: Div-based with data attributes
        {
            "container": "[data-song], [data-track], .track, .song-entry",
            "artist": "[data-artist], .artist, .performer",
            "title": "[data-title], .title, .track-title",
        },
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            }
        )

    def scrape(self) -> list[Song]:
        """Scrape songs from WDR Plan B pages."""
        songs = []

        # Try the channel playlist page first
        channel_songs = self._scrape_url(Config.WDR_PLAN_B_CHANNEL_URL)
        if channel_songs:
            logger.info(f"WDR channel page: {len(channel_songs)} songs")
            songs.extend(channel_songs)

        # Also try the day-specific show pages
        for day, url in Config.WDR_PLAN_B_SHOW_URLS.items():
            day_songs = self._scrape_url(url)
            if day_songs:
                logger.info(f"WDR {day} show page: {len(day_songs)} songs")
                songs.extend(day_songs)

        # Deduplicate within WDR results
        unique = list(dict.fromkeys(songs))
        logger.info(f"WDR total: {len(unique)} unique songs (from {len(songs)} raw)")
        return unique

    def _scrape_url(self, url: str) -> list[Song]:
        """Scrape a single WDR URL."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        logger.debug(f"WDR page title: {soup.title.string if soup.title else 'N/A'}")
        logger.debug(f"WDR page length: {len(response.text)} chars")

        # Try structured selector strategies
        for i, strategy in enumerate(self.SELECTOR_STRATEGIES):
            songs = self._try_selector_strategy(soup, strategy)
            if songs:
                logger.info(f"WDR selector strategy {i + 1} matched: {len(songs)} songs")
                return songs

        # Fallback: regex-based extraction
        songs = self._regex_fallback(soup)
        if songs:
            logger.info(f"WDR regex fallback: {len(songs)} songs")
            return songs

        logger.warning(f"WDR: no songs found at {url}")
        return []

    def _try_selector_strategy(self, soup: BeautifulSoup, strategy: dict) -> list[Song]:
        """Try a CSS selector strategy to extract songs."""
        songs = []
        entries = soup.select(strategy["container"])
        for entry in entries:
            artist_el = entry.select_one(strategy["artist"])
            title_el = entry.select_one(strategy["title"])
            if artist_el and title_el:
                artist = artist_el.get_text(strip=True)
                title = title_el.get_text(strip=True)
                if artist and title and len(artist) > 1 and len(title) > 1:
                    songs.append(Song(artist=artist, title=title, source=self.name))
        return songs

    def _regex_fallback(self, soup: BeautifulSoup) -> list[Song]:
        """Extract 'Artist - Title' patterns from page text."""
        songs = []
        text = soup.get_text()

        # Pattern: lines that look like "Artist - Title" or "Artist – Title"
        pattern = re.compile(
            r"^\s*"
            r"([A-Za-z\u00C0-\u024F\u00DF][\w\s&.,'\-]+?)"
            r"\s*[-\u2013\u2014]\s*"
            r"([A-Za-z\u00C0-\u024F\u00DF][\w\s&.,'\-()!?]+?)"
            r"\s*$",
            re.MULTILINE,
        )

        for match in pattern.finditer(text):
            artist, title = match.group(1).strip(), match.group(2).strip()
            if 2 <= len(artist) <= 80 and 2 <= len(title) <= 120:
                songs.append(Song(artist=artist, title=title, source=self.name))

        return songs
