"""
Abstract interface for the external service that provides drop-down options.

To integrate a real service, create a new class that inherits from
``ExternalService`` and implement the two methods below.
Then swap the implementation in ``src/dependencies.py``.
"""

from abc import ABC, abstractmethod

from src.models.api_models import Item, SelectedObject


class ExternalService(ABC):
    """Contract that any external-service adapter must fulfil."""

    @abstractmethod
    def search(
        self,
        *,
        offset: int,
        limit: int,
        filter: str | None = None,
        body: dict | None = None,
        sparql_key: str | None = None,
        sparql_params: list[str] | None = None,
    ) -> list[Item]:
        """
        Return a page of items matching the optional *filter*.

        Parameters
        ----------
        offset : int
            Number of items to skip.
        limit : int
            Maximum number of items to return.
        filter : str | None
            Free-text typed by the user; ``None`` means "return everything".
        body : dict | None
            Free-form object sent in the request body (extra query parameters
            defined in the Witboost template).
        sparql_key : str | None
            Key of the named SPARQL query to execute.
        sparql_params : list[str] | None
            Positional parameters to inject into the SPARQL query.
        """

    @abstractmethod
    def validate(
        self,
        selected_objects: list[SelectedObject],
        query_parameters: dict | None = None,
        sparql_key: str | None = None,
        sparql_params: list[str] | None = None,
    ) -> list[str]:
        """
        Check that every *selected_object* still exists in the external
        glossary.

        Return a list of human-readable error strings.
        An empty list means validation passed.
        """
