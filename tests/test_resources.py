"""Tests for POST /v1/resources."""


class TestRetrieveValues:
    def test_returns_paginated_results(self, client):
        resp = client.post("/v1/resources?offset=0&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert data[0]["id"] == "banana"

    def test_applies_filter(self, client):
        resp = client.post("/v1/resources?offset=0&limit=10&filter=berry")
        assert resp.status_code == 200
        data = resp.json()
        assert all("berry" in item["id"] for item in data)

    def test_applies_offset(self, client):
        resp = client.post("/v1/resources?offset=2&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        # Third item in the mock list is "orange"
        assert data[0]["id"] == "orange"

    def test_returns_empty_when_no_match(self, client):
        resp = client.post("/v1/resources?offset=0&limit=5&filter=zzznotexist")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_items_have_expected_fields(self, client):
        resp = client.post("/v1/resources?offset=0&limit=5")
        item = resp.json()[0]
        assert "id" in item
        assert "value" in item
        assert "description" in item

    def test_sparql_and_sparql_params_accepted(self, client):
        """Mock service ignores sparql params but the router should accept them."""
        resp = client.post(
            "/v1/resources?offset=0&limit=5",
            json={"sparql": "default", "sparql-params": "abc,def"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
