from abc import ABC, abstractmethod

from plan_b.models import Song


class BaseScraper(ABC):
    """Interface that all scrapers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this scraper source."""
        ...

    @abstractmethod
    def scrape(self) -> list[Song]:
        """
        Fetch and return a list of Song objects.
        Should handle its own errors and return an empty list on failure.
        """
        ...
