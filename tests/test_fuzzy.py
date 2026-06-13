"""Tests for the fuzzy matcher scoring and thresholding."""

from plan_b.matchers.fuzzy import FuzzyMatcher
from plan_b.models import Song


def test_exact_match_scores_high():
    matcher = FuzzyMatcher()
    song = Song(artist="Billie Eilish", title="Birds of a Feather")
    score = matcher.score_match(song, "Billie Eilish", "Birds of a Feather")
    assert score > 0.95


def test_unrelated_scores_low():
    matcher = FuzzyMatcher()
    song = Song(artist="Billie Eilish", title="Birds of a Feather")
    score = matcher.score_match(song, "Rammstein", "Du Hast")
    assert score < 0.5


def test_best_match_picks_correct_candidate_above_threshold():
    matcher = FuzzyMatcher()
    song = Song(artist="Eminem", title="Lose Yourself")
    candidates = [
        {"artist": "Adele", "title": "Hello", "id": "1", "uri": "u1", "service": "tidal"},
        {"artist": "Eminem", "title": "Lose Yourself", "id": "2", "uri": "u2", "service": "tidal"},
    ]
    result = matcher.best_match(song, candidates)
    assert result is not None
    assert result.matched is True
    assert result.track_id == "2"


def test_best_match_returns_none_when_all_below_threshold():
    matcher = FuzzyMatcher()
    song = Song(artist="Eminem", title="Lose Yourself")
    candidates = [
        {"artist": "Adele", "title": "Hello", "id": "1", "uri": "u1", "service": "tidal"},
    ]
    result = matcher.best_match(song, candidates)
    assert result is None
