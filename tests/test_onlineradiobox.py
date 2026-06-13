"""Offline tests for the OnlineRadioBox scraper, run against a saved page.

These let us iterate on the parsing logic without hitting the network or
deploying anything. Re-capture the fixture with:
    python -m plan_b scrape --save-html tests/fixtures
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from plan_b.config import Config
from plan_b.fetch import FixtureFetcher, SavingFetcher, slugify_request
from plan_b.scrapers.onlineradiobox import OnlineRadioBoxScraper

FIXTURE = Path(__file__).parent / "fixtures" / "onlineradiobox_latest_show.html"
TARGET_DATE = datetime(2026, 6, 11, tzinfo=ZoneInfo("Europe/Berlin"))  # a Thursday


def test_parses_songs_from_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = OnlineRadioBoxScraper(fetcher=None)
    songs = scraper._parse_html(html, TARGET_DATE)

    assert len(songs) >= 5, "expected a normal Plan B night's worth of songs"
    for song in songs:
        assert song.artist and len(song.artist) > 1
        assert song.title and len(song.title) > 1
        assert song.source == "onlineradiobox"


def test_all_songs_within_plan_b_window():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = OnlineRadioBoxScraper(fetcher=None)
    songs = scraper._parse_html(html, TARGET_DATE)

    for song in songs:
        assert song.played_at is not None
        assert Config.PLAN_B_START_HOUR <= song.played_at.hour < Config.PLAN_B_END_HOUR


def test_scrape_via_fixture_fetcher(tmp_path):
    """End-to-end scrape() using a FixtureFetcher (no network)."""
    html = FIXTURE.read_text(encoding="utf-8")
    # Place the fixture under every day-offset URL the scraper might request,
    # so whichever Plan B day it lands on, it finds the page.
    for off in range(7):
        name = slugify_request(
            f"{Config.ONLINERADIOBOX_URL}{off}", {"cs": "de.einslive"}
        )
        (tmp_path / name).write_text(html, encoding="utf-8")

    scraper = OnlineRadioBoxScraper(fetcher=FixtureFetcher(tmp_path))
    songs = scraper.scrape()
    assert len(songs) >= 5


def test_saving_then_replaying_roundtrip(tmp_path):
    """SavingFetcher writes a file that FixtureFetcher can read back."""

    class StubFetcher:
        def get(self, url, params=None):
            return "<html>hello</html>"

    saver = SavingFetcher(StubFetcher(), tmp_path)
    url, params = "https://example.com/x", {"a": "1"}
    saver.get(url, params=params)

    replayer = FixtureFetcher(tmp_path)
    assert replayer.get(url, params=params) == "<html>hello</html>"
