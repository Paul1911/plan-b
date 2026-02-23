import logging
from datetime import datetime
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from plan_b.config import Config
from plan_b.matchers.fuzzy import FuzzyMatcher
from plan_b.models import MatchResult, PlaylistInfo, Song

logger = logging.getLogger(__name__)


class SpotifyService:
    """Handles all Spotify API interactions: auth, search, and playlist management."""

    def __init__(self):
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=Config.SPOTIFY_CLIENT_ID,
                client_secret=Config.SPOTIFY_CLIENT_SECRET,
                redirect_uri=Config.SPOTIFY_REDIRECT_URI,
                scope=Config.SPOTIFY_SCOPE,
                cache_path=".spotify_cache",
            )
        )
        self.matcher = FuzzyMatcher()
        self._user_id: Optional[str] = None

    @property
    def user_id(self) -> str:
        if self._user_id is None:
            self._user_id = self.sp.current_user()["id"]
        return self._user_id

    def search_and_match(self, song: Song) -> Optional[MatchResult]:
        """Search Spotify for a song and return the best fuzzy match."""
        # Try structured query first
        query = f"artist:{song.artist} track:{song.title}"
        try:
            results = self.sp.search(q=query, type="track", limit=Config.SEARCH_RESULT_LIMIT)
        except Exception as e:
            logger.error(f"Spotify search failed for '{query}': {e}")
            results = None

        # Fallback to simple query if no results
        tracks = results.get("tracks", {}).get("items", []) if results else []
        if not tracks:
            try:
                fallback_query = song.search_query
                results = self.sp.search(
                    q=fallback_query, type="track", limit=Config.SEARCH_RESULT_LIMIT
                )
                tracks = results.get("tracks", {}).get("items", [])
            except Exception as e:
                logger.error(f"Spotify fallback search failed: {e}")
                return None

        if not tracks:
            logger.warning(f"  No Spotify results for '{song.artist} - {song.title}'")
            return None

        candidates = []
        for track in tracks:
            artists = ", ".join(a["name"] for a in track["artists"])
            candidates.append(
                {
                    "artist": artists,
                    "title": track["name"],
                    "id": track["id"],
                    "uri": track["uri"],
                    "service": "spotify",
                }
            )

        return self.matcher.best_match(song, candidates)

    def find_or_create_playlist(self) -> PlaylistInfo:
        """Find existing playlist or create a new one."""
        # Search user's playlists
        playlists = self.sp.current_user_playlists(limit=50)
        while playlists:
            for pl in playlists["items"]:
                if pl["name"] == Config.PLAYLIST_NAME and pl["owner"]["id"] == self.user_id:
                    logger.info(f"Found existing Spotify playlist: {pl['id']}")
                    return PlaylistInfo(
                        service_name="spotify",
                        playlist_id=pl["id"],
                        playlist_url=pl["external_urls"]["spotify"],
                        name=pl["name"],
                        track_count=pl["tracks"]["total"],
                    )
            if playlists["next"]:
                playlists = self.sp.next(playlists)
            else:
                break

        # Create new playlist
        logger.info(f"Creating new Spotify playlist: {Config.PLAYLIST_NAME}")
        new_pl = self.sp.user_playlist_create(
            user=self.user_id,
            name=Config.PLAYLIST_NAME,
            public=True,
            description=Config.PLAYLIST_DESCRIPTION,
        )
        return PlaylistInfo(
            service_name="spotify",
            playlist_id=new_pl["id"],
            playlist_url=new_pl["external_urls"]["spotify"],
            name=new_pl["name"],
            track_count=0,
        )

    def update_playlist(self, playlist: PlaylistInfo, track_uris: list[str]) -> None:
        """Replace all tracks in the playlist with the given URIs."""
        if not track_uris:
            logger.warning("No tracks to add to Spotify playlist")
            return

        track_uris = track_uris[: Config.MAX_PLAYLIST_TRACKS]

        # Replace first batch (max 100 per API call)
        first_batch = track_uris[:100]
        self.sp.playlist_replace_items(playlist.playlist_id, first_batch)
        logger.info(f"Replaced Spotify playlist with first {len(first_batch)} tracks")

        # Add remaining in batches of 100
        for i in range(100, len(track_uris), 100):
            batch = track_uris[i : i + 100]
            self.sp.playlist_add_items(playlist.playlist_id, batch)
            logger.info(f"Added batch of {len(batch)} tracks to Spotify")

        # Update description with timestamp
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        description = f"{Config.PLAYLIST_DESCRIPTION} Letztes Update: {timestamp}"
        self.sp.playlist_change_details(playlist.playlist_id, description=description)
