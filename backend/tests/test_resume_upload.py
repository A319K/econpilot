"""Coverage for POST /resumes/upload — the drag-and-drop resume path."""

import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _upload(content: bytes, filename: str = "resume.pdf", name: str = "Finance Base"):
    return client.post(
        "/resumes/upload",
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
        data={"name": name, "job_family": "data_analytics"},
    )


def test_upload_creates_a_usable_base_resume():
    response = _upload(MINIMAL_PDF)
    assert response.status_code == 201

    body = response.json()
    assert body["is_uploaded"] is True
    assert body["latex_source"] is None
    assert body["is_base_template"] is True
    assert body["original_filename"] == "resume.pdf"
    # A PDF path is what the rest of the pipeline attaches to an application.
    assert body["pdf_path"].endswith(".pdf")


def test_uploaded_resume_is_listed_alongside_compiled_ones():
    created = _upload(MINIMAL_PDF).json()
    listed = client.get("/resumes").json()
    assert created["id"] in [r["id"] for r in listed]


def test_non_pdf_is_rejected_with_a_plain_language_message():
    response = _upload(b"PK\x03\x04 this is really a docx", filename="resume.docx")
    assert response.status_code == 422
    assert "isn't a PDF" in response.json()["detail"]


def test_empty_file_is_rejected():
    assert _upload(b"").status_code == 422


def test_oversized_file_is_rejected():
    too_big = MINIMAL_PDF + b"0" * (10 * 1024 * 1024 + 1)
    response = _upload(too_big)
    assert response.status_code == 422
    assert "10 MB" in response.json()["detail"]


def test_blank_name_is_rejected():
    response = client.post(
        "/resumes/upload",
        files={"file": ("r.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        data={"name": "   ", "job_family": "data_analytics"},
    )
    assert response.status_code == 422


def test_malicious_filename_cannot_escape_the_output_directory():
    body = _upload(MINIMAL_PDF, filename="../../../../etc/passwd.pdf").json()
    # The stored path is generated from the display name, never the upload's
    # filename, and the remembered original is stripped to its basename.
    assert ".." not in body["pdf_path"]
    assert body["original_filename"] == "passwd.pdf"


def test_uploaded_resume_rejects_latex_edits():
    resume_id = _upload(MINIMAL_PDF).json()["id"]
    response = client.put(f"/resumes/{resume_id}", json={"latex_source": "\\documentclass{article}"})
    assert response.status_code == 422
    assert "uploaded PDF" in response.json()["detail"]


def test_uploaded_resume_can_still_be_renamed():
    resume_id = _upload(MINIMAL_PDF).json()["id"]
    response = client.put(f"/resumes/{resume_id}", json={"name": "Consulting Base"})
    assert response.status_code == 200
    assert response.json()["name"] == "Consulting Base"
