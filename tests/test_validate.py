"""Tests for POST /v1/resources/validate."""


class TestValidate:
    def test_valid_items_return_200(self, client):
        resp = client.post(
            "/v1/resources/validate",
            json={
                "selectedObjects": [{"id": "banana"}, {"id": "apple"}],
            },
        )
        assert resp.status_code == 200
        assert resp.json() == "Validation succeeded"

    def test_invalid_item_returns_400(self, client):
        resp = client.post(
            "/v1/resources/validate",
            json={
                "selectedObjects": [{"id": "banana"}, {"id": "doesnotexist"}],
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "errors" in body
        assert any("doesnotexist" in e["error"] for e in body["errors"])

    def test_empty_selection_returns_200(self, client):
        resp = client.post(
            "/v1/resources/validate",
            json={"selectedObjects": []},
        )
        assert resp.status_code == 200

    def test_query_parameters_accepted(self, client):
        resp = client.post(
            "/v1/resources/validate",
            json={
                "selectedObjects": [{"id": "banana"}],
                "queryParameters": {"kind": "fruit"},
            },
        )
        assert resp.status_code == 200
