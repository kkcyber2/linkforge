"""HTTP-level tests."""
import pytest
from fastapi.testclient import TestClient

from linkforge import app as appmod


@pytest.fixture
def client():
    appmod.store = appmod.LinkStore()
    return TestClient(appmod.app, follow_redirects=False)


class TestCreate:
    def test_creates_link(self, client):
        r = client.post("/api/links", json={"target": "https://example.com"})
        assert r.status_code == 200
        assert r.json()["slug"]

    def test_rejects_javascript_scheme(self, client):
        r = client.post("/api/links", json={"target": "javascript:alert(1)"})
        assert r.status_code == 400

    def test_duplicate_slug_is_400(self, client):
        client.post("/api/links", json={"target": "https://a.com", "slug": "x"})
        r = client.post("/api/links", json={"target": "https://b.com", "slug": "x"})
        assert r.status_code == 400


class TestRedirect:
    def test_redirects_302_not_301(self, client):
        """301 would be browser-cached and we would lose all future click data."""
        slug = client.post("/api/links", json={"target": "https://example.com"}).json()["slug"]
        r = client.get(f"/{slug}")
        assert r.status_code == 302
        assert r.headers["location"] == "https://example.com"

    def test_records_click_with_headers(self, client):
        slug = client.post("/api/links", json={"target": "https://example.com"}).json()["slug"]
        client.get(f"/{slug}", headers={"referer": "https://linkedin.com/x",
                                        "user-agent": "iPhone"})
        st = client.get(f"/api/links/{slug}/stats").json()
        assert st["clicks"] == 1
        assert st["by_referrer"] == {"linkedin": 1}
        assert st["by_device"] == {"mobile": 1}

    def test_unknown_slug_404(self, client):
        assert client.get("/nope").status_code == 404

    def test_deactivated_no_longer_redirects(self, client):
        slug = client.post("/api/links", json={"target": "https://example.com"}).json()["slug"]
        client.delete(f"/api/links/{slug}")
        assert client.get(f"/{slug}").status_code == 404


class TestApi:
    def test_list(self, client):
        client.post("/api/links", json={"target": "https://a.com"})
        assert len(client.get("/api/links").json()["links"]) == 1

    def test_stats_unknown_404(self, client):
        assert client.get("/api/links/nope/stats").status_code == 404

    def test_deactivate_unknown_404(self, client):
        assert client.delete("/api/links/nope").status_code == 404

    def test_index_renders(self, client):
        assert client.get("/").status_code == 200
