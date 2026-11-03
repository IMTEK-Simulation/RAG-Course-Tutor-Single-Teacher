from fastapi.testclient import TestClient

from backend.auth import SingleAccountAuth
from backend.courses import CourseStore
from backend import main


def configured_client(tmp_path, monkeypatch):
    store = CourseStore(tmp_path / "courses")
    auth = SingleAccountAuth(tmp_path / "account.json", tmp_path / "secret")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "auth", auth)
    main.retrievers.clear()
    client = TestClient(main.app)
    response = client.post("/auth/setup", json={"username": "dozent", "password": "sicheres-passwort-123"})
    assert response.status_code == 201
    return client, store


def test_only_first_account_can_be_created(tmp_path, monkeypatch):
    client, _store = configured_client(tmp_path, monkeypatch)
    second = client.post("/auth/setup", json={"username": "zweiter", "password": "noch-ein-passwort-123"})
    assert second.status_code == 409


def test_students_can_read_courses_and_use_tutor_but_not_manage(tmp_path, monkeypatch):
    client, store = configured_client(tmp_path, monkeypatch)
    course = store.create("Öffentlicher Testkurs", "Für Studierende sichtbar", "Lernbegleiter", "de")
    client.post("/auth/logout")
    assert client.get("/courses").status_code == 200
    assert client.get(f"/course-info?course_id={course['id']}").status_code == 200
    tutor = client.post("/tutor", json={
        "course_id": course["id"], "message": "Was ist das Thema?", "mode": "direct",
        "language": "de", "base_url": "https://openwebui.uni-freiburg.de/api",
        "model": "UFR: Standard Coding", "api_key": "student-key", "messages": [], "top_k": 2,
    })
    assert tutor.status_code == 200
    assert tutor.json()["sources"] == []
    assert client.get(f"/courses/{course['id']}/chunks").status_code == 401
    assert client.post("/courses", json={"name": "Verboten"}).status_code == 401


def test_create_upload_edit_reindex_and_delete(tmp_path, monkeypatch):
    client, _store = configured_client(tmp_path, monkeypatch)
    created = client.post("/courses", json={
        "name": "Einführung KI", "description": "Testkurs",
        "tutor_role": "Tutor für KI", "language": "de",
    })
    assert created.status_code == 201
    course_id = created.json()["id"]
    upload = client.post(
        f"/courses/{course_id}/documents",
        files={"file": ("lektion.md", b"# Grundlagen\n\nMaschinelles Lernen nutzt Daten, um Muster zu erkennen. Dieser Absatz ist lang genug fuer einen brauchbaren Wissensabschnitt und einen Retrieval-Test.", "text/markdown")},
    )
    assert upload.status_code == 201
    chunks = client.get(f"/courses/{course_id}/chunks").json()["chunks"]
    chunk_id = chunks[0]["id"]
    edited = client.patch(f"/courses/{course_id}/chunks/{chunk_id}", json={
        "title": "Lektion", "section": "Lernen aus Daten", "text": chunks[0]["text"],
        "module": "Modul 1", "topic": "Grundlagen",
    })
    assert edited.status_code == 200
    assert client.post(f"/courses/{course_id}/reindex").status_code == 200
    assert client.delete(f"/courses/{course_id}").status_code == 200
    assert client.get(f"/courses/{course_id}/chunks").status_code == 404


def test_rejects_unsupported_upload(tmp_path, monkeypatch):
    client, store = configured_client(tmp_path, monkeypatch)
    course = store.create("Testkurs", "", "Tutor", "de")
    response = client.post(f"/courses/{course['id']}/documents", files={"file": ("malware.exe", b"nope")})
    assert response.status_code == 400
