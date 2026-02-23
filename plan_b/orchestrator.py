import logging
from datetime import datetime

from plan_b.config import Config
from plan_b.models import Song
from plan_b.scrapers.onlineradiobox import OnlineRadioBoxScraper
from plan_b.scrapers.wdr import WDRScraper

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full scrape -> match -> update workflow."""

    def __init__(self, enable_tidal: bool = True, enable_spotify: bool = False):
        self.scrapers = [
            OnlineRadioBoxScraper(),  # Primary: time-filtered Plan B songs
            WDRScraper(),  # Secondary: WDR show pages
        ]
        self.tidal = None
        self.spotify = None

        if enable_tidal:
            from plan_b.services.tidal import TidalService

            self.tidal = TidalService()

        if enable_spotify:
            errors = Config.validate_spotify()
            if errors:
                for err in errors:
                    logger.error(f"Spotify config error: {err}")
                logger.error("Spotify disabled. Set credentials in .env file.")
            else:
                from plan_b.services.spotify import SpotifyService

                self.spotify = SpotifyService()

    def run(self) -> dict:
        """
        Execute the full pipeline:
        1. Scrape songs from all sources
        2. Deduplicate
        3. Match to Tidal and/or Spotify
        4. Update playlists

        Returns a summary dict.
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "songs_scraped": 0,
            "songs_unique": 0,
            "tidal_matched": 0,
            "tidal_unmatched": 0,
            "spotify_matched": 0,
            "spotify_unmatched": 0,
            "unmatched_songs": [],
        }

        # Step 1: Scrape
        logger.info("=" * 60)
        logger.info("Step 1: Scraping songs from all sources")
        logger.info("=" * 60)
        all_songs = self._scrape_all_sources()
        summary["songs_scraped"] = len(all_songs)

        # Step 2: Deduplicate
        logger.info("")
        logger.info("Step 2: Deduplicating")
        unique_songs = list(dict.fromkeys(all_songs))
        summary["songs_unique"] = len(unique_songs)
        logger.info(f"  {len(all_songs)} scraped -> {len(unique_songs)} unique songs")

        if not unique_songs:
            logger.warning("No songs found from any source!")
            return summary

        # Step 3 & 4: Match and update for each enabled service
        if self.tidal:
            self._process_service(
                service=self.tidal,
                service_name="Tidal",
                songs=unique_songs,
                summary=summary,
                matched_key="tidal_matched",
                unmatched_key="tidal_unmatched",
                id_field="track_id",
            )

        if self.spotify:
            self._process_service(
                service=self.spotify,
                service_name="Spotify",
                songs=unique_songs,
                summary=summary,
                matched_key="spotify_matched",
                unmatched_key="spotify_unmatched",
                id_field="track_uri",
            )

        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Run complete!")
        logger.info(f"  Songs scraped: {summary['songs_unique']} unique")
        if self.tidal:
            logger.info(
                f"  Tidal: {summary['tidal_matched']} matched, "
                f"{summary['tidal_unmatched']} unmatched"
            )
        if self.spotify:
            logger.info(
                f"  Spotify: {summary['spotify_matched']} matched, "
                f"{summary['spotify_unmatched']} unmatched"
            )
        if summary["unmatched_songs"]:
            logger.info(f"  Unmatched songs ({len(summary['unmatched_songs'])}):")
            for s in summary["unmatched_songs"]:
                logger.info(f"    - {s}")
        logger.info("=" * 60)

        return summary

    def _process_service(
        self,
        service,
        service_name: str,
        songs: list[Song],
        summary: dict,
        matched_key: str,
        unmatched_key: str,
        id_field: str,
    ):
        """Match songs and update playlist for a single music service."""
        logger.info("")
        logger.info(f"Step 3: Matching to {service_name}")
        logger.info("-" * 40)

        track_ids = []
        unmatched = []

        for song in songs:
            result = service.search_and_match(song)
            if result and getattr(result, id_field):
                track_ids.append(getattr(result, id_field))
                summary[matched_key] += 1
            else:
                unmatched.append(f"{song.artist} - {song.title}")
                summary[unmatched_key] += 1

        # Collect unmatched for summary (avoid duplicates across services)
        for s in unmatched:
            if s not in summary["unmatched_songs"]:
                summary["unmatched_songs"].append(s)

        logger.info(
            f"  {service_name}: {summary[matched_key]} matched, "
            f"{summary[unmatched_key]} unmatched"
        )

        # Update playlist (only if we have matches — never clear to empty)
        if track_ids:
            logger.info(f"\nStep 4: Updating {service_name} playlist")
            logger.info("-" * 40)
            playlist = service.find_or_create_playlist()
            service.update_playlist(playlist, track_ids)
            logger.info(f"  {service_name} playlist: {playlist.playlist_url}")
        else:
            logger.warning(
                f"  No {service_name} matches found. Playlist not updated "
                f"(keeping previous content)."
            )

    def _scrape_all_sources(self) -> list[Song]:
        """Run all scrapers and collect songs."""
        songs = []
        for scraper in self.scrapers:
            try:
                result = scraper.scrape()
                logger.info(f"  {scraper.name}: {len(result)} songs")
                songs.extend(result)
            except Exception as e:
                logger.error(f"  {scraper.name} scraper failed: {e}", exc_info=True)
        return songs
