"""Tests for KgmService."""

import httpx
import pytest
import respx

from src.models.api_models import SelectedObject
from src.services.kgm_service import DEFAULT_SPARQL_QUERY, KgmService
from src.settings import AppSettings, KgmConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KGM_BASE = "https://kgm.example.com"
SPARQL_URL = f"{KGM_BASE}/v1/graph/sparql"

SPARQL_RESPONSE = {
    "head": {
        "vars": ["concept", "label", "definition", "scheme", "schemeLabel"]
    },
    "results": {
        "bindings": [
            {
                "concept": {"type": "uri", "value": "http://example.org/type#Concept1"},
                "label": {"type": "literal", "value": "Concept One"},
                "definition": {"type": "literal", "value": "The first concept"},
                "scheme": {"type": "uri", "value": "http://example.org/type#GlossaryA"},
                "schemeLabel": {"type": "literal", "value": "Glossary Alpha"},
            },
            {
                "concept": {"type": "uri", "value": "http://example.org/type#Concept2"},
                "label": {"type": "literal", "value": "Concept Two"},
                "definition": {"type": "literal", "value": "The second concept"},
                "scheme": {"type": "uri", "value": "http://example.org/type#GlossaryA"},
                "schemeLabel": {"type": "literal", "value": "Glossary Alpha"},
            },
            {
                "concept": {"type": "uri", "value": "http://example.org/type#Concept3"},
                "label": {"type": "literal", "value": "Concept Three"},
                "definition": {"type": "literal", "value": "The third concept"},
                "scheme": {"type": "uri", "value": "http://example.org/type#GlossaryB"},
                "schemeLabel": {"type": "literal", "value": "Glossary Beta"},
            },
        ],
    },
}


@pytest.fixture()
def settings() -> AppSettings:
    return AppSettings(kgm=KgmConfig(base_url=KGM_BASE))


@pytest.fixture()
def service(settings: AppSettings) -> KgmService:
    return KgmService(settings)


def _mock_sparql(respx_mock: respx.MockRouter, data: dict | None = None) -> respx.Route:
    return respx_mock.post(SPARQL_URL).mock(
        return_value=httpx.Response(200, json=data if data is not None else SPARQL_RESPONSE)
    )


# ---------------------------------------------------------------------------
# Tests — mapping
# ---------------------------------------------------------------------------


class TestMapping:
    def test_maps_bindings_to_items(self, service):
        items = KgmService._map_to_items(SPARQL_RESPONSE["results"]["bindings"])
        assert len(items) == 3

    def test_item_id_is_label_value(self, service):
        items = KgmService._map_to_items(SPARQL_RESPONSE["results"]["bindings"])
        assert items[0].id == "Concept One"

    def test_item_value_is_label_value(self, service):
        items = KgmService._map_to_items(SPARQL_RESPONSE["results"]["bindings"])
        assert items[0].value == "Concept One"

    def test_item_description_is_definition_value(self, service):
        items = KgmService._map_to_items(SPARQL_RESPONSE["results"]["bindings"])
        assert items[0].description == "The first concept"

    def test_item_reference_glossary_is_scheme_label_value(self, service):
        items = KgmService._map_to_items(SPARQL_RESPONSE["results"]["bindings"])
        assert items[0].referenceGlossary == "Glossary Alpha"
        assert items[2].referenceGlossary == "Glossary Beta"

    def test_skips_bindings_without_label(self, service):
        bindings = [
            {
                "concept": {"type": "uri", "value": "http://example.org/type#NoLabel"},
                "definition": {"type": "literal", "value": "No label here"},
                "scheme": {"type": "uri", "value": "http://example.org/type#G"},
                "schemeLabel": {"type": "literal", "value": "G"},
            },
        ]
        items = KgmService._map_to_items(bindings)
        assert len(items) == 0


# ---------------------------------------------------------------------------
# Tests — search
# ---------------------------------------------------------------------------


class TestSearch:
    @respx.mock
    def test_returns_all_items(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=0, limit=100)
        assert len(items) == 3

    @respx.mock
    def test_pagination_offset_limit(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=1, limit=1)
        assert len(items) == 1
        assert items[0].value == "Concept Two"

    @respx.mock
    def test_filter_by_value(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=0, limit=100, filter="One")
        assert len(items) == 1
        assert items[0].value == "Concept One"

    @respx.mock
    def test_filter_by_description(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=0, limit=100, filter="third")
        assert len(items) == 1
        assert items[0].value == "Concept Three"

    @respx.mock
    def test_filter_by_reference_glossary(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=0, limit=100, filter="Beta")
        assert len(items) == 1
        assert items[0].referenceGlossary == "Glossary Beta"

    @respx.mock
    def test_filter_case_insensitive(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=0, limit=100, filter="concept one")
        assert len(items) == 1

    @respx.mock
    def test_empty_filter_returns_all(self, service):
        _mock_sparql(respx.mock)
        items = service.search(offset=0, limit=100, filter=None)
        assert len(items) == 3


# ---------------------------------------------------------------------------
# Tests — validate
# ---------------------------------------------------------------------------


class TestValidate:
    @respx.mock
    def test_valid_ids_return_no_errors(self, service):
        _mock_sparql(respx.mock)
        errors = service.validate([SelectedObject(id="Concept One")])
        assert errors == []

    @respx.mock
    def test_missing_id_returns_error(self, service):
        _mock_sparql(respx.mock)
        errors = service.validate([SelectedObject(id="DoesNotExist")])
        assert len(errors) == 1
        assert "DoesNotExist" in errors[0]


# ---------------------------------------------------------------------------
# Tests — error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @respx.mock
    def test_sparql_failure_raises(self, service):
        respx.mock.post(SPARQL_URL).mock(
            return_value=httpx.Response(500, json={"error": "Internal"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            service.search(offset=0, limit=5)


# ---------------------------------------------------------------------------
# Tests — named SPARQL queries
# ---------------------------------------------------------------------------


class TestNamedSparqlQueries:
    def test_uses_default_query_when_no_queries_configured(self):
        """No queries in config + no sparql_key → built-in default."""
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE))
        svc = KgmService(settings)
        assert svc._resolve_query() == DEFAULT_SPARQL_QUERY

    def test_uses_configured_default_key(self):
        """'default' key in config is used when no sparql_key is given."""
        custom = "SELECT ?label WHERE { ?s ?p ?o }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"default": custom}))
        svc = KgmService(settings)
        assert svc._resolve_query() == custom

    def test_resolves_named_query(self):
        """Explicit sparql_key selects the right query."""
        queries = {
            "business-concept": "SELECT ?label WHERE { ?c a skos:Concept }",
            "business-term": "SELECT ?label WHERE { ?t skos:broader <$1> }",
        }
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries=queries))
        svc = KgmService(settings)
        assert svc._resolve_query("business-concept") == queries["business-concept"]
        assert svc._resolve_query("business-term") == queries["business-term"]

    def test_unknown_key_raises_key_error(self):
        """Requesting a non-existent key raises KeyError."""
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"alpha": "Q1"}))
        svc = KgmService(settings)
        with pytest.raises(KeyError, match="not-configured"):
            svc._resolve_query("not-configured")

    def test_placeholder_replacement(self):
        """$1, $2 placeholders are replaced with sparql_params."""
        query = "SELECT ?label WHERE { ?t skos:broader <$1> ; skos:inScheme <$2> }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)
        resolved = svc._resolve_query("q", ["http://example.org/C1", "http://example.org/S1"])
        assert "http://example.org/C1" in resolved
        assert "http://example.org/S1" in resolved
        assert "$1" not in resolved
        assert "$2" not in resolved

    def test_no_params_leaves_placeholders_intact(self):
        """Without sparql_params, $1 stays as-is."""
        query = "SELECT ?label WHERE { ?t skos:broader <$1> }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)
        assert "$1" in svc._resolve_query("q")

    @respx.mock
    def test_search_sends_named_query_to_kgm(self):
        """search() with sparql_key sends the resolved query to KGM."""
        custom = "SELECT ?label WHERE { ?s ?p ?o }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"my-query": custom}))
        svc = KgmService(settings)

        route = respx.mock.post(SPARQL_URL).mock(
            return_value=httpx.Response(200, json=SPARQL_RESPONSE)
        )
        svc.search(offset=0, limit=100, sparql_key="my-query")
        assert route.called
        assert route.calls[0].request.content.decode() == custom

    @respx.mock
    def test_search_sends_query_with_replaced_params(self):
        """search() replaces placeholders before sending to KGM."""
        query = "SELECT ?label WHERE { ?t skos:broader <$1> }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)

        route = respx.mock.post(SPARQL_URL).mock(
            return_value=httpx.Response(200, json=SPARQL_RESPONSE)
        )
        svc.search(offset=0, limit=100, sparql_key="q", sparql_params=["http://example.org/X"])
        sent = route.calls[0].request.content.decode()
        assert "http://example.org/X" in sent
        assert "$1" not in sent

    @respx.mock
    def test_validate_uses_named_query(self):
        """validate() also respects sparql_key."""
        custom = "SELECT ?label WHERE { ?s ?p ?o }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"vq": custom}))
        svc = KgmService(settings)

        route = respx.mock.post(SPARQL_URL).mock(
            return_value=httpx.Response(200, json=SPARQL_RESPONSE)
        )
        svc.validate([SelectedObject(id="Concept One")], sparql_key="vq")
        assert route.called
        assert route.calls[0].request.content.decode() == custom

    def test_list_placeholder_single_value(self):
        """${1*} with a single value expands to one quoted string."""
        query = "VALUES ?x { ${1*} }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)
        resolved = svc._resolve_query("q", ["Customer Metric"])
        assert resolved == 'VALUES ?x { "Customer Metric" }'

    def test_list_placeholder_multiple_values(self):
        """${1*} with pipe-separated values expands to multiple quoted strings."""
        query = "VALUES ?x { ${1*} }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)
        resolved = svc._resolve_query("q", ["Customer Metric|Investment|Revenue"])
        assert resolved == 'VALUES ?x { "Customer Metric" "Investment" "Revenue" }'

    def test_list_placeholder_with_scalar(self):
        """${1*} list and $2 scalar can coexist."""
        query = "VALUES ?x { ${1*} } FILTER(?y = $2)"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)
        resolved = svc._resolve_query("q", ["A|B", "hello"])
        assert '"A" "B"' in resolved
        assert "hello" in resolved
        assert "${1*}" not in resolved
        assert "$2" not in resolved

    def test_no_params_leaves_list_placeholder_intact(self):
        """Without sparql_params, ${1*} stays as-is."""
        query = "VALUES ?x { ${1*} }"
        settings = AppSettings(kgm=KgmConfig(base_url=KGM_BASE, sparql_queries={"q": query}))
        svc = KgmService(settings)
        assert "${1*}" in svc._resolve_query("q")
