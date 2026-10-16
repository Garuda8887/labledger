def test_profiles_crud(client):
    r = client.post(
        "/api/v1/profiles",
        json={"display_name": "Ada", "sex": "female", "dob": "1990-01-15"},
    )
    assert r.status_code == 201
    profile = r.json()
    assert profile["display_name"] == "Ada"
    assert profile["preferred_unit_system"] == "conventional"
    pid = profile["id"]

    r = client.get("/api/v1/profiles")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    r = client.get(f"/api/v1/profiles/{pid}")
    assert r.status_code == 200

    r = client.patch(f"/api/v1/profiles/{pid}", json={"display_name": "Ada Lovelace"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Ada Lovelace"

    r = client.put(f"/api/v1/profiles/{pid}/unit-preference", json={"preferred_unit_system": "si"})
    assert r.status_code == 200
    assert r.json()["preferred_unit_system"] == "si"

    r = client.delete(f"/api/v1/profiles/{pid}")
    assert r.status_code == 400  # needs confirm

    r = client.delete(f"/api/v1/profiles/{pid}?confirm=true")
    assert r.status_code == 204

    r = client.get(f"/api/v1/profiles/{pid}")
    assert r.status_code == 404


def test_profile_isolation(two_profiles, client, sample_png_bytes):
    a, b = two_profiles
    files = {"files": ("lab.png", sample_png_bytes, "image/png")}
    r = client.post(f"/api/v1/profiles/{a['id']}/documents", files=files)
    assert r.status_code == 202
    docs_a = client.get(f"/api/v1/profiles/{a['id']}/documents").json()
    docs_b = client.get(f"/api/v1/profiles/{b['id']}/documents").json()
    assert docs_a["total"] == 1
    assert docs_b["total"] == 0
