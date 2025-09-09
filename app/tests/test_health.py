# app/tests/test_health.py

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"status": "OK"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
