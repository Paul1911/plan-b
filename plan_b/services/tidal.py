import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import tidalapi

from plan_b.config import Config
from plan_b.matchers.fuzzy import FuzzyMatcher
from plan_b.models import MatchResult, PlaylistInfo, Song

logger = logging.getLogger(__name__)


class TidalService:
    """Handles all Tidal API interactions: auth, search, and playlist management."""

    def __init__(self):
        self.session = tidalapi.Session()
        self.matcher = FuzzyMatcher()
        self._login()

    def _login(self):
        """Establish a Tidal session: saved/refresh token first, OAuth as last resort.

        1. Load session data from TIDAL_SESSION_JSON (e.g. a GitHub Actions secret)
           or the on-disk session file.
        2. Try the stored access token; if it's expired, mint a fresh one with the
           refresh token (which Tidal does not rotate, so this keeps working).
        3. Fall back to interactive OAuth - but only in a real terminal. In CI we
           raise instead of hanging forever on input.
        """
        data = self._load_session_data()
        if data and self._restore_from_data(data):
            return

        if os.getenv("CI") or not sys.stdin.isatty():
            raise RuntimeError(
                "No usable Tidal session and not running interactively. "
                "Run 'python -m plan_b login' locally, then supply the resulting "
                "session via the TIDAL_SESSION_JSON secret (GitHub Actions) or the "
                f"{Config.TIDAL_SESSION_FILE} file."
            )

        # Interactive OAuth login (first-time, local only)
        login, future = self.session.login_oauth()
        print(
            f"\n{'=' * 60}\n"
            f"  Tidal Login Required\n"
            f"  Open this URL in your browser:\n\n"
            f"  {login.verification_uri_complete}\n"
            f"\n{'=' * 60}\n"
            f"  Waiting for you to log in..."
        )
        future.result()  # Blocks until user completes login
        print("  Tidal login successful!\n")
        self._save_session()
        logger.info("Tidal login successful, session saved")

    def _load_session_data(self) -> Optional[dict]:
        """Load session JSON from the env var (CI) or the session file."""
        raw = Config.TIDAL_SESSION_JSON
        if raw:
            try:
                logger.info("Loading Tidal session from TIDAL_SESSION_JSON")
                return json.loads(raw)
            except Exception as e:
                logger.warning(f"TIDAL_SESSION_JSON is set but not valid JSON: {e}")

        session_file = Path(Config.TIDAL_SESSION_FILE)
        if session_file.exists():
            try:
                return json.loads(session_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Saved Tidal session file invalid: {e}")
        return None

    def _restore_from_data(self, data: dict) -> bool:
        """Restore a session from saved token data, refreshing the access token if needed.

        tidalapi's load_oauth_session() calls the API to initialise the session, so it
        only works with a *valid* access token. When the stored one has expired we must
        refresh first, then initialise with the fresh token.
        """
        token_type = data.get("token_type") or "Bearer"
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expiry_raw = data.get("expiry_time")
        expiry = datetime.fromisoformat(expiry_raw) if expiry_raw else None

        # Fast path: the stored access token may still be valid.
        if access_token:
            try:
                self.session.load_oauth_session(
                    token_type, access_token, refresh_token, expiry
                )
                if self.session.check_login():
                    logger.info("Tidal session restored from saved token")
                    self._save_session()
                    return True
            except Exception as e:
                logger.info(f"Stored Tidal access token unusable, refreshing: {e}")

        # Refresh path: mint a fresh access token, then initialise the session.
        if refresh_token and self.session.token_refresh(refresh_token):
            try:
                self.session.load_oauth_session(
                    token_type,
                    self.session.access_token,
                    refresh_token,
                    self.session.expiry_time,
                )
                if self.session.check_login():
                    logger.info("Tidal session refreshed via refresh token")
                    self._save_session()
                    return True
            except Exception as e:
                logger.warning(f"Tidal refresh succeeded but session init failed: {e}")

        return False

    def _save_session(self):
        """Persist session tokens to file for reuse."""
        data = {
            "token_type": self.session.token_type,
            "access_token": self.session.access_token,
            "refresh_token": self.session.refresh_token,
            "expiry_time": (
                self.session.expiry_time.isoformat() if self.session.expiry_time else None
            ),
        }
        Path(Config.TIDAL_SESSION_FILE).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def search_and_match(self, song: Song) -> Optional[MatchResult]:
        """Search Tidal for a song and return the best fuzzy match."""
        query = song.search_query
        try:
            results = self.session.search(query, models=[tidalapi.media.Track], limit=Config.SEARCH_RESULT_LIMIT)
        except Exception as e:
            logger.error(f"Tidal search failed for '{query}': {e}")
            return None

        tracks = results.get("tracks", [])
        if not tracks:
            logger.warning(f"  No Tidal results for '{song.artist} - {song.title}'")
            return None

        candidates = []
        for track in tracks:
            artists = ", ".join(a.name for a in track.artists)
            candidates.append(
                {
                    "artist": artists,
                    "title": track.name,
                    "id": str(track.id),
                    "uri": str(track.id),
                    "service": "tidal",
                }
            )

        return self.matcher.best_match(song, candidates)

    def find_or_create_playlist(self) -> PlaylistInfo:
        """Reuse the existing 'Plan B' playlist, or create it once.

        We keep the *same* playlist across runs (and just replace its contents in
        update_playlist) so its share URL stays stable. The old code deleted and
        recreated it every run, which changed the ID/link each time.

        Stores the UserPlaylist object internally for later modification.
        """
        self._user_playlist = None
        try:
            for pl in self.session.user.playlists():
                if pl.name == Config.PLAYLIST_NAME:
                    logger.info(f"Reusing existing Tidal playlist: {pl.id}")
                    self._user_playlist = pl
                    break
        except Exception as e:
            logger.error(f"Failed to list Tidal playlists: {e}")

        if self._user_playlist is None:
            logger.info(f"Creating Tidal playlist: {Config.PLAYLIST_NAME}")
            self._user_playlist = self.session.user.create_playlist(
                Config.PLAYLIST_NAME, Config.PLAYLIST_DESCRIPTION
            )

        url = getattr(self._user_playlist, "share_url", None) or (
            f"https://tidal.com/browse/playlist/{self._user_playlist.id}"
        )
        return PlaylistInfo(
            service_name="tidal",
            playlist_id=str(self._user_playlist.id),
            playlist_url=url,
            name=self._user_playlist.name,
            track_count=self._user_playlist.num_tracks,
        )

    def update_playlist(self, playlist: PlaylistInfo, track_ids: list[str]) -> None:
        """Replace the playlist contents with the given track IDs.

        Clears the existing tracks first so the playlist mirrors the latest show
        (rather than growing without bound), then re-adds in batches.
        """
        if not track_ids:
            logger.warning("No tracks to add to Tidal playlist")
            return

        if not hasattr(self, "_user_playlist") or self._user_playlist is None:
            logger.error("No UserPlaylist available. Call find_or_create_playlist first.")
            return

        track_ids = track_ids[: Config.MAX_PLAYLIST_TRACKS]

        try:
            # Wipe existing contents so we mirror only the latest show.
            self._user_playlist.clear()
            logger.info("Cleared existing Tidal playlist contents")

            # Add in batches to avoid potential API limits
            batch_size = 50
            for i in range(0, len(track_ids), batch_size):
                batch = [int(tid) for tid in track_ids[i : i + batch_size]]
                self._user_playlist.add(batch)
                logger.info(f"Added batch of {len(batch)} tracks to Tidal")

            # Refresh the description timestamp (best effort).
            timestamp = datetime.now(ZoneInfo(Config.TIMEZONE)).strftime("%d.%m.%Y %H:%M")
            description = f"{Config.PLAYLIST_DESCRIPTION} Letztes Update: {timestamp}"
            try:
                self._user_playlist.edit(description=description)
            except Exception as e:
                logger.warning(f"Could not update playlist description: {e}")

            logger.info(f"Tidal playlist updated with {len(track_ids)} tracks")

        except Exception as e:
            logger.error(f"Failed to update Tidal playlist: {e}")
            raise
