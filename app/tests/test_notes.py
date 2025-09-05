from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200


def test_create_and_list_notes():
    r = client.post("/notes", json={"title": "t1", "body": "b1"})
    assert r.status_code == 201
    r = client.get("/notes")
    assert any(n["title"] == "t1" for n in r.json())
