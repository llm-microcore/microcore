import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..utils import ExtendedString


class SearchResult(ExtendedString):
    """
    String containing the search result with additional information in attributes

    Attributes:
        id (str): document (text) identifier in embedding database
        distance (float): The distance between the query and the search result
        metadata (dict): A dictionary containing document metadata
    """

    id: str
    distance: float
    metadata: dict


@dataclass
class AbstractEmbeddingDB(ABC):
    """
    Base class for embedding databases
    """

    @abstractmethod
    def search(
        self,
        collection: str,
        query: str | list,
        n_results: int = 5,
        where: dict = None,
        **kwargs,
    ) -> list[str | SearchResult]:
        """
        Similarity search

        Args:
            collection (str): collection name
            query (str | list): query string or list of query strings
            n_results (int): number of results to return
            where (dict): filter results by metadata
            **kwargs: additional arguments
        """

    def find(self, *args, **kwargs) -> list[str | SearchResult]:
        """
        Alias for `search`
        """
        return self.search(*args, **kwargs)

    def find_all(
        self,
        collection: str,
        query: str | list,
        where: dict = None,
        **kwargs,
    ) -> list[str | SearchResult]:
        return self.search(
            collection, query, n_results=sys.maxsize - 1, where=where, **kwargs
        )

    @abstractmethod
    def get_all(self, collection: str) -> list[str | SearchResult]:
        """Return all documents in the collection"""

    def save(self, collection: str, text: str, metadata: dict = None):
        """Save a single document in the collection"""
        self.save_many(collection, [(text, metadata)])

    @abstractmethod
    def save_many(self, collection: str, items: list[tuple[str, dict] | str]):
        """Save multiple documents in the collection"""

    @abstractmethod
    def clear(self, collection: str):
        """Clear the collection"""

    def find_one(self, collection: str, query: str | list) -> str | SearchResult | None:
        """
        Find most similar document in the collection

        Returns:
            Most similar document or None if collection is empty
        """
        return next(iter(self.search(collection, query, 1)), None)

    @abstractmethod
    def count(self, collection: str) -> int:
        """
        Count the number of documents in the collection

        Returns:
            Number of documents in the collection
        """

    @abstractmethod
    def delete(self, collection: str, what: str | list[str] | dict):
        """
        Delete documents from the collection

        Args:
            collection (str): collection name
            what (str | list[str] | dict): id, list ids or metadata query
        """
