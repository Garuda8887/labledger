def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    assert body["db"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "labledger"
