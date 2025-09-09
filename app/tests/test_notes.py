# app/tests/test_notes.py

def test_create_and_list_notes(client):
    # create
    r = client.post("/notes", json={"title": "t1", "body": "b1"})
    assert r.status_code == 201
    note = r.json()
    assert note["title"] == "t1"
    assert note["body"] == "b1"
    assert "id" in note

    # list
    r = client.get("/notes")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    # keep both styles of assertion but consistent with a single list
    assert any(n["title"] == "t1" for n in items)
    assert items[0]["title"] == "t1"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    # Prometheus exposition format
    assert "http_requests_total" in r.text or "http_requests" in r.text
