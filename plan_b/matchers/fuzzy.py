import logging

from thefuzz import fuzz

from plan_b.config import Config
from plan_b.models import MatchResult, Song

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """
    Scores how well a music service search result matches the original scraped song.

    Uses multiple fuzzy matching strategies:
    - ratio: Standard Levenshtein similarity. Good for nearly identical strings.
    - token_sort_ratio: Sorts tokens alphabetically first. Handles "The Killers" vs "Killers, The".
    - partial_ratio: Best partial substring match. Handles "Eminem feat. Rihanna" vs "Eminem".

    Title is weighted higher (0.6) than artist (0.4) because artists can have
    variant spellings, "feat." credits, label differences, etc.
    """

    def score_match(self, song: Song, candidate_artist: str, candidate_title: str) -> float:
        """Return a confidence score (0.0 to 1.0) for how well the candidate matches."""
        artist_score = max(
            fuzz.ratio(song.artist.lower(), candidate_artist.lower()),
            fuzz.token_sort_ratio(song.artist.lower(), candidate_artist.lower()),
            fuzz.partial_ratio(song.artist.lower(), candidate_artist.lower()),
        )

        title_score = max(
            fuzz.ratio(song.title.lower(), candidate_title.lower()),
            fuzz.token_sort_ratio(song.title.lower(), candidate_title.lower()),
            fuzz.partial_ratio(song.title.lower(), candidate_title.lower()),
        )

        combined = (artist_score * 0.4 + title_score * 0.6) / 100.0
        return round(combined, 3)

    def is_acceptable(self, score: float) -> bool:
        """Check if score meets the configured threshold."""
        return score >= (Config.FUZZY_MATCH_THRESHOLD / 100.0)

    def best_match(self, song: Song, candidates: list[dict]) -> MatchResult | None:
        """
        From a list of candidate dicts, find the best match for the given song.

        Each candidate dict should have keys: artist, title, id, uri, service.
        Returns None if no candidate meets the threshold.
        """
        best_result = None
        best_score = 0.0

        for candidate in candidates:
            score = self.score_match(song, candidate["artist"], candidate["title"])
            if score > best_score:
                best_score = score
                best_result = MatchResult(
                    song=song,
                    service_name=candidate.get("service", "unknown"),
                    track_id=candidate.get("id"),
                    track_uri=candidate.get("uri"),
                    confidence=score,
                    matched_artist=candidate["artist"],
                    matched_title=candidate["title"],
                    matched=self.is_acceptable(score),
                )

        if best_result and best_result.matched:
            logger.info(
                f"  Matched: '{song.artist} - {song.title}' -> "
                f"'{best_result.matched_artist} - {best_result.matched_title}' "
                f"({best_result.confidence:.0%})"
            )
        else:
            logger.warning(
                f"  No match: '{song.artist} - {song.title}' "
                f"(best score: {best_score:.0%}, threshold: {Config.FUZZY_MATCH_THRESHOLD}%)"
            )

        return best_result if best_result and best_result.matched else None
