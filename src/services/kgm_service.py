"""
KGM (Knowledge Graph Manager) implementation of ``ExternalService``.

Queries the KGM SPARQL endpoint for SKOS concepts and maps the results
to the Custom URL Picker ``Item`` model.

Multiple named SPARQL queries can be configured. The caller selects which
query to execute via the ``sparql_key`` parameter. Positional placeholders
``$1``, ``$2``, … inside a query are replaced with the values supplied in
``sparql_params``.

List placeholders ``${N*}`` expand a pipe-separated parameter into SPARQL
``VALUES``-compatible quoted strings, e.g. ``"val1" "val2"``.
"""

import re

import httpx
from loguru import logger

from src.models.api_models import Item, SelectedObject
from src.services.external_service import ExternalService
from src.settings import AppSettings

DEFAULT_SPARQL_QUERY = """\
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?concept ?label ?definition ?scheme ?schemeLabel
WHERE {
  ?concept a skos:Concept ;
           skos:inScheme ?scheme .

  {
    ?child skos:broader ?concept .
  }
  UNION
  {
    ?concept skos:narrower ?child .
  }

  OPTIONAL {
    ?concept skos:prefLabel ?label .
    FILTER(LANG(?label) = "en" || LANG(?label) = "")
  }

  OPTIONAL {
    ?concept skos:definition ?definition .
    FILTER(LANG(?definition) = "en" || LANG(?definition) = "")
  }

  OPTIONAL {
    ?scheme skos:prefLabel ?schemeLabel .
    FILTER(LANG(?schemeLabel) = "en" || LANG(?schemeLabel) = "")
  }
}
ORDER BY ?schemeLabel ?label ?concept"""


class KgmService(ExternalService):
    """
    Queries the KGM SPARQL endpoint and exposes SKOS concepts as
    Custom URL Picker drop-down options.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._base_url: str = settings.kgm.base_url.rstrip("/")
        self._sparql_queries: dict[str, str] = {
            k: v.strip() for k, v in settings.kgm.sparql_queries.items() if v.strip()
        }
        logger.info(
            "KgmService initialised (base_url={}, queries={})",
            self._base_url,
            list(self._sparql_queries.keys()) or ["<built-in default>"],
        )

    # ---- Query resolution -------------------------------------------------

    def _resolve_query(
        self,
        sparql_key: str | None = None,
        sparql_params: list[str] | None = None,
    ) -> str:
        """
        Look up a named SPARQL query and replace positional placeholders.

        - If *sparql_key* is ``None``, the ``"default"`` key is used.
        - If the key is ``"default"`` and not present in the configured
          queries, the built-in ``DEFAULT_SPARQL_QUERY`` is returned.
        - Placeholders ``$1``, ``$2``, … are replaced with the
          corresponding values from *sparql_params*.
        - List placeholders ``${1*}``, ``${2*}``, … expand a
          pipe-separated param into SPARQL VALUES-compatible quoted
          strings: ``"val1" "val2" "val3"``.
        """
        key = sparql_key or "default"

        if key in self._sparql_queries:
            query = self._sparql_queries[key]
        elif key == "default":
            query = DEFAULT_SPARQL_QUERY
        else:
            available = list(self._sparql_queries.keys())
            raise KeyError(
                f"SPARQL query '{key}' is not configured. "
                f"Available queries: {available}"
            )

        if sparql_params:
            for i, param in enumerate(sparql_params, start=1):
                # List placeholder ${N*}: expand "a|b|c" → '"a" "b" "c"'
                list_ph = f"${{{i}*}}"
                if list_ph in query:
                    values_str = " ".join(f'"{v.strip()}"' for v in param.split("|"))
                    query = query.replace(list_ph, values_str)
                # Scalar placeholder $N
                query = query.replace(f"${i}", param)

        return query

    # ---- KGM SPARQL call --------------------------------------------------

    def _fetch_concepts(self, query: str) -> list[dict]:
        """Execute the SPARQL query and return the bindings list."""
        url = f"{self._base_url}/v1/graph/sparql"
        logger.debug("Querying KGM SPARQL endpoint at {}", url)
        logger.debug("SPARQL query:\n{}", query)

        response = httpx.post(
            url,
            content=query,
            headers={"Content-Type": "application/sparql-query"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", {}).get("bindings", [])

    # ---- Response mapping -------------------------------------------------

    @staticmethod
    def _map_to_items(bindings: list[dict]) -> list[Item]:
        """
        Map SPARQL result bindings to Items.

        Mapping:
          id                → label.value
          value             → label.value
          description       → definition.value
          referenceGlossary → schemeLabel.value
        """
        items: list[Item] = []
        for binding in bindings:
            label = binding.get("label", {}).get("value", "")
            definition = binding.get("definition", {}).get("value", "")
            scheme_label = binding.get("schemeLabel", {}).get("value", "")
            if label:
                items.append(
                    Item(
                        id=label,
                        value=label,
                        description=definition or None,
                        referenceGlossary=scheme_label or None,
                    )
                )
        return items

    # ---- ExternalService interface ----------------------------------------

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
        query = self._resolve_query(sparql_key, sparql_params)
        bindings = self._fetch_concepts(query)
        items = self._map_to_items(bindings)

        if filter:
            lower = filter.lower()
            items = [
                item
                for item in items
                if lower in (item.value or "").lower()
                or lower in (item.description or "").lower()
                or lower in (item.referenceGlossary or "").lower()
            ]

        return items[offset : offset + limit]

    def validate(
        self,
        selected_objects: list[SelectedObject],
        query_parameters: dict | None = None,
        sparql_key: str | None = None,
        sparql_params: list[str] | None = None,
    ) -> list[str]:
        query = self._resolve_query(sparql_key, sparql_params)
        bindings = self._fetch_concepts(query)
        items = self._map_to_items(bindings)
        known_ids = {item.id for item in items}
        errors: list[str] = []
        for obj in selected_objects:
            if obj.id not in known_ids:
                errors.append(f'Item "{obj.id}" does not exist in the glossary')
        return errors
