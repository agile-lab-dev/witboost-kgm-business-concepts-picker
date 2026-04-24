"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from src.dependencies import get_external_service, get_settings
from src.main import app
from src.models.api_models import Item, SelectedObject
from src.services.external_service import ExternalService
from src.settings import AppSettings, CorsConfig, CustomUrlPickerConfig, KgmConfig

# ---------------------------------------------------------------------------
# In-memory mock used by route-level tests
# ---------------------------------------------------------------------------

_MOCK_ITEMS: list[Item] = [
    Item(id="banana", value="Banana", description="A yellow fruit", referenceGlossary="Fruits"),
    Item(id="apple", value="Apple", description="A red or green fruit", referenceGlossary="Fruits"),
    Item(id="orange", value="Orange", description="A citrus fruit", referenceGlossary="Fruits"),
    Item(id="grape", value="Grape", description="A small round fruit", referenceGlossary="Fruits"),
    Item(id="mango", value="Mango", description="A tropical fruit", referenceGlossary="Fruits"),
    Item(id="pineapple", value="Pineapple", description="A tropical spiky fruit", referenceGlossary="Fruits"),
    Item(id="strawberry", value="Strawberry", description="A red berry", referenceGlossary="Berries"),
    Item(id="blueberry", value="Blueberry", description="A small blue berry", referenceGlossary="Berries"),
    Item(id="watermelon", value="Watermelon", description="A large green fruit", referenceGlossary="Fruits"),
    Item(id="peach", value="Peach", description="A fuzzy stone fruit", referenceGlossary="Fruits"),
    Item(id="cherry", value="Cherry", description="A small red stone fruit", referenceGlossary="Fruits"),
    Item(id="lemon", value="Lemon", description="A sour citrus fruit", referenceGlossary="Fruits"),
    Item(id="kiwi", value="Kiwi", description="A fuzzy brown fruit", referenceGlossary="Fruits"),
    Item(id="avocado", value="Avocado", description="A creamy green fruit", referenceGlossary="Fruits"),
    Item(id="coconut", value="Coconut", description="A tropical hard-shelled fruit", referenceGlossary="Fruits"),
]


class _InMemoryService(ExternalService):
    def search(self, *, offset, limit, filter=None, body=None, sparql_key=None, sparql_params=None):
        results = _MOCK_ITEMS
        if filter:
            lo = filter.lower()
            results = [i for i in results if lo in (i.value or "").lower() or lo in (i.description or "").lower() or lo in (i.referenceGlossary or "").lower()]
        return results[offset : offset + limit]

    def validate(self, selected_objects, query_parameters=None, sparql_key=None, sparql_params=None):
        known = {i.id for i in _MOCK_ITEMS}
        return [f'Item "{o.id}" does not exist' for o in selected_objects if o.id not in known]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def settings() -> AppSettings:
    return AppSettings(
        kgm=KgmConfig(base_url="https://mock.example.com"),
        custom_url_picker=CustomUrlPickerConfig(cors=CorsConfig(origin="*")),
    )


@pytest.fixture()
def client(settings: AppSettings) -> TestClient:
    """FastAPI test client with dependency overrides."""
    svc = _InMemoryService()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_external_service] = lambda: svc
    yield TestClient(app)
    app.dependency_overrides.clear()
