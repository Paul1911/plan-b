from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Song:
    """A song scraped from a radio source."""

    artist: str
    title: str
    played_at: Optional[datetime] = None
    source: str = ""

    @property
    def search_query(self) -> str:
        """Combined query for music service search."""
        return f"{self.artist} {self.title}"

    def __eq__(self, other):
        if not isinstance(other, Song):
            return False
        return (
            self._normalize(self.artist) == self._normalize(other.artist)
            and self._normalize(self.title) == self._normalize(other.title)
        )

    def __hash__(self):
        return hash((self._normalize(self.artist), self._normalize(self.title)))

    def __repr__(self):
        return f"Song('{self.artist}' - '{self.title}', source={self.source})"

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, strip, collapse whitespace."""
        return " ".join(text.lower().strip().split())


@dataclass
class MatchResult:
    """Result of matching a Song to a music service."""

    song: Song
    service_name: str  # "spotify" or "tidal"
    track_id: Optional[str] = None
    track_uri: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0
    matched_artist: str = ""
    matched_title: str = ""
    matched: bool = False


@dataclass
class PlaylistInfo:
    """Metadata about a managed playlist."""

    service_name: str
    playlist_id: str
    playlist_url: str
    name: str
    track_count: int = 0
