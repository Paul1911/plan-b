import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Config:
    """Central configuration loaded from environment variables."""

    # Spotify
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REDIRECT_URI: str = os.getenv(
        "SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"
    )
    SPOTIFY_SCOPE: str = "playlist-modify-public playlist-modify-private"

    # Tidal
    TIDAL_SESSION_FILE: str = os.getenv("TIDAL_SESSION_FILE", ".tidal_session.json")
    # Full session JSON (contents of the session file) for headless/CI use,
    # e.g. a GitHub Actions secret. Takes precedence over the session file.
    TIDAL_SESSION_JSON: str = os.getenv("TIDAL_SESSION_JSON", "")

    # Scraping - OnlineRadioBox
    ONLINERADIOBOX_URL: str = "https://onlineradiobox.com/de/einslive/playlist/"

    # Timezone the radio station broadcasts in (playlist times are local Berlin time)
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Berlin")

    # Plan B time window (on main 1LIVE channel)
    PLAN_B_START_HOUR: int = 20  # 20:00
    PLAN_B_END_HOUR: int = 23  # 23:00
    # Plan B airs Mon(0) through Thu(3)
    PLAN_B_WEEKDAYS: list[int] = [0, 1, 2, 3]

    # Matching
    FUZZY_MATCH_THRESHOLD: int = int(os.getenv("FUZZY_MATCH_THRESHOLD", "75"))
    SEARCH_RESULT_LIMIT: int = 5

    # Playlist
    PLAYLIST_NAME: str = "1Live Plan B"
    PLAYLIST_DESCRIPTION: str = (
        "Automatisch generierte Playlist mit Songs aus der "
        "1LIVE Plan B Sendung (Mo-Do, 20-23 Uhr)."
    )
    MAX_PLAYLIST_TRACKS: int = 200

    # Scheduling
    SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "09:00")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "plan_b.log")

    @classmethod
    def validate_tidal(cls) -> list[str]:
        """Return list of Tidal configuration errors (none expected — auth is interactive)."""
        return []

    @classmethod
    def validate_spotify(cls) -> list[str]:
        """Return list of Spotify configuration errors."""
        errors = []
        if not cls.SPOTIFY_CLIENT_ID:
            errors.append("SPOTIFY_CLIENT_ID is not set")
        if not cls.SPOTIFY_CLIENT_SECRET:
            errors.append("SPOTIFY_CLIENT_SECRET is not set")
        return errors
