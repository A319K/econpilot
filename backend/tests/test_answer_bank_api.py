from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.answer_bank import AnswerBankEntry, AnswerSource

client = TestClient(app)

_n = {"i": 0}


def _q() -> str:
    _n["i"] += 1
    return f"Custom question number {_n['i']}?"


def test_create_user_answer_is_approved_by_default():
    q = _q()
    resp = client.post("/answer-bank", json={"question": q, "answer": "My answer."})
    assert resp.status_code == 201
    body = resp.json()
    assert body["approved"] is True
    assert body["source"] == "user"
    assert body["question_norm"] == q.lower().rstrip("?").strip()


def test_duplicate_question_conflicts():
    q = _q()
    assert client.post("/answer-bank", json={"question": q, "answer": "a"}).status_code == 201
    dup = client.post("/answer-bank", json={"question": q.upper(), "answer": "b"})
    assert dup.status_code == 409


def test_empty_answer_rejected():
    resp = client.post("/answer-bank", json={"question": _q(), "answer": "   "})
    assert resp.status_code == 422


def test_list_filters_by_approved_and_source():
    db = SessionLocal()
    try:
        db.add(
            AnswerBankEntry(
                question_norm=f"pending q {_n['i']}",
                question_raw="Pending?",
                answer="draft",
                source=AnswerSource.llm,
                approved=False,
            )
        )
        _n["i"] += 1
        db.commit()
    finally:
        db.close()

    pending = client.get("/answer-bank", params={"approved": "false", "source": "llm"})
    assert pending.status_code == 200
    assert all(e["approved"] is False and e["source"] == "llm" for e in pending.json())


def test_approve_pending_suggestion():
    db = SessionLocal()
    try:
        entry = AnswerBankEntry(
            question_norm=f"approve me {_n['i']}",
            question_raw="Approve me?",
            answer="suggested",
            source=AnswerSource.llm,
            approved=False,
        )
        _n["i"] += 1
        db.add(entry)
        db.commit()
        entry_id = entry.id
    finally:
        db.close()

    resp = client.patch(f"/answer-bank/{entry_id}", json={"approved": True, "answer": "edited"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["approved"] is True
    assert body["answer"] == "edited"


def test_update_missing_answer_rejected_empty():
    created = client.post("/answer-bank", json={"question": _q(), "answer": "x"}).json()
    resp = client.patch(f"/answer-bank/{created['id']}", json={"answer": "  "})
    assert resp.status_code == 422


def test_delete_answer():
    created = client.post("/answer-bank", json={"question": _q(), "answer": "x"}).json()
    assert client.delete(f"/answer-bank/{created['id']}").status_code == 204
    assert client.get("/answer-bank", params={}).status_code == 200


def test_patch_and_delete_404():
    assert client.patch("/answer-bank/999999", json={"approved": True}).status_code == 404
    assert client.delete("/answer-bank/999999").status_code == 404
