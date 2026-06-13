"""HTTP fetching with pluggable backends.

Separating *fetching* from *parsing* is what makes the scrapers debuggable
without a network round-trip (or a deploy):

- ``LiveFetcher``    - real HTTP via requests (production default).
- ``SavingFetcher``  - wraps another fetcher and writes every response to disk
                       so a live run can be captured as fixtures (``--save-html``).
- ``FixtureFetcher`` - replays previously-saved HTML from disk, no network
                       (``--from-html`` and the test suite).

All three expose the same tiny interface: ``get(url, params=None) -> str``.
"""

import logging
import re
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def slugify_request(url: str, params: dict | None = None) -> str:
    """Build a deterministic, filesystem-safe filename for a URL + params.

    Used by both SavingFetcher (write) and FixtureFetcher (read) so a saved
    response is found again when replayed.
    """
    parsed = urlparse(url)
    base = parsed.netloc + parsed.path
    if parsed.query:
        base += "_" + parsed.query
    if params:
        base += "_" + urlencode(sorted(params.items()))
    safe = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")
    return f"{safe[:150]}.html"


class LiveFetcher:
    """Fetch pages over the network."""

    def __init__(self, headers: dict | None = None, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)
        self.timeout = timeout

    def get(self, url: str, params: dict | None = None) -> str:
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.text


class SavingFetcher:
    """Wrap another fetcher and persist every response to ``directory``."""

    def __init__(self, inner, directory: str | Path):
        self.inner = inner
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, url: str, params: dict | None = None) -> str:
        html = self.inner.get(url, params=params)
        path = self.directory / slugify_request(url, params)
        path.write_text(html, encoding="utf-8")
        logger.info(f"Saved HTML fixture: {path}")
        return html


class FixtureFetcher:
    """Replay saved HTML from ``directory`` instead of hitting the network."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def get(self, url: str, params: dict | None = None) -> str:
        path = self.directory / slugify_request(url, params)
        if not path.exists():
            raise FileNotFoundError(
                f"No saved fixture for {url} (looked for {path}). "
                f"Capture one first with --save-html."
            )
        logger.info(f"Loaded HTML fixture: {path}")
        return path.read_text(encoding="utf-8")
