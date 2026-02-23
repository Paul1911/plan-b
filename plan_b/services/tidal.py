import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

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
        """Load saved session or initiate new OAuth login."""
        session_file = Path(Config.TIDAL_SESSION_FILE)

        if session_file.exists():
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                self.session.load_oauth_session(
                    data["token_type"],
                    data["access_token"],
                    data.get("refresh_token"),
                    data.get("expiry_time"),
                )
                if self.session.check_login():
                    logger.info("Tidal session restored from file")
                    return
            except Exception as e:
                logger.warning(f"Saved Tidal session invalid: {e}")

        # Interactive OAuth login
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
        """Find existing 'Plan B' playlist or create a new one.

        Stores the UserPlaylist object internally for later modification.
        """
        # Search user's playlists for an existing one to delete+recreate
        try:
            playlists = self.session.user.playlists()
            for pl in playlists:
                if pl.name == Config.PLAYLIST_NAME:
                    logger.info(f"Found existing Tidal playlist: {pl.id}, will recreate")
                    # Delete the old playlist so we can create a fresh UserPlaylist
                    try:
                        pl.delete()
                        logger.info("Deleted old Tidal playlist")
                    except Exception as e:
                        logger.warning(f"Failed to delete old playlist: {e}")
                    break
        except Exception as e:
            logger.error(f"Failed to list Tidal playlists: {e}")

        # Create new playlist (returns a UserPlaylist with write methods)
        logger.info(f"Creating Tidal playlist: {Config.PLAYLIST_NAME}")
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        description = f"{Config.PLAYLIST_DESCRIPTION} Letztes Update: {timestamp}"
        self._user_playlist = self.session.user.create_playlist(
            Config.PLAYLIST_NAME, description
        )
        return PlaylistInfo(
            service_name="tidal",
            playlist_id=str(self._user_playlist.id),
            playlist_url=f"https://tidal.com/browse/playlist/{self._user_playlist.id}",
            name=self._user_playlist.name,
            track_count=0,
        )

    def update_playlist(self, playlist: PlaylistInfo, track_ids: list[str]) -> None:
        """Add tracks to the playlist using the stored UserPlaylist object."""
        if not track_ids:
            logger.warning("No tracks to add to Tidal playlist")
            return

        if not hasattr(self, "_user_playlist") or self._user_playlist is None:
            logger.error("No UserPlaylist available. Call find_or_create_playlist first.")
            return

        track_ids = track_ids[: Config.MAX_PLAYLIST_TRACKS]

        try:
            # Add in batches to avoid potential API limits
            batch_size = 50
            for i in range(0, len(track_ids), batch_size):
                batch = [int(tid) for tid in track_ids[i : i + batch_size]]
                self._user_playlist.add(batch)
                logger.info(f"Added batch of {len(batch)} tracks to Tidal")

            logger.info(f"Tidal playlist updated with {len(track_ids)} tracks")

        except Exception as e:
            logger.error(f"Failed to update Tidal playlist: {e}")
            raise
