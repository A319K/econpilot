import pytest

from app.models.application import ApplicationStatus as S
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.tracking.state_machine import ALLOWED_TRANSITIONS, InvalidTransition, transition
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models.application import Application


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _application(session, status=S.discovered) -> Application:
    company = Company(name="Acme")
    session.add(company)
    session.commit()
    job = Job(
        company_id=company.id,
        title="SWE Intern",
        url=f"https://example.com/{id(company)}",
        source=JobSource.manual,
        role_type=RoleType.internship,
        job_family=JobFamily.swe,
        dedup_hash=f"h{id(company)}",
    )
    session.add(job)
    session.commit()
    application = Application(job_id=job.id, status=status)
    session.add(application)
    session.commit()
    return application


ALL_STATUSES = list(S)

VALID_PAIRS = {
    (S.discovered, S.queued),
    (S.discovered, S.withdrawn),
    (S.queued, S.in_progress),
    (S.queued, S.withdrawn),
    (S.in_progress, S.ready_to_submit),
    (S.in_progress, S.queued),
    (S.in_progress, S.withdrawn),
    (S.ready_to_submit, S.submitted),
    (S.ready_to_submit, S.in_progress),
    (S.ready_to_submit, S.withdrawn),
    (S.submitted, S.oa),
    (S.submitted, S.interview),
    (S.submitted, S.offer),
    (S.submitted, S.rejected),
    (S.submitted, S.withdrawn),
    (S.oa, S.interview),
    (S.oa, S.offer),
    (S.oa, S.rejected),
    (S.oa, S.withdrawn),
    (S.interview, S.offer),
    (S.interview, S.rejected),
    (S.interview, S.withdrawn),
}


@pytest.mark.parametrize("from_status,to_status", sorted(VALID_PAIRS, key=lambda p: (p[0].value, p[1].value)))
def test_valid_transition_succeeds(from_status, to_status):
    session = _session()
    application = _application(session, status=from_status)

    result = transition(application, to_status)

    assert result.status == to_status
    assert result.status_history[-1]["from"] == from_status.value
    assert result.status_history[-1]["to"] == to_status.value


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (a, b)
        for a in ALL_STATUSES
        for b in ALL_STATUSES
        if a != b and (a, b) not in VALID_PAIRS
    ],
)
def test_invalid_transition_raises(from_status, to_status):
    session = _session()
    application = _application(session, status=from_status)

    with pytest.raises(InvalidTransition):
        transition(application, to_status)

    # Status and history must be untouched on rejection.
    assert application.status == from_status
    assert not application.status_history


@pytest.mark.parametrize("terminal", [S.offer, S.rejected, S.withdrawn])
def test_terminal_statuses_have_no_allowed_transitions(terminal):
    assert ALLOWED_TRANSITIONS.get(terminal, set()) == set()


@pytest.mark.parametrize("terminal", [S.offer, S.rejected, S.withdrawn])
def test_terminal_status_transition_raises_without_force(terminal):
    session = _session()
    application = _application(session, status=terminal)

    with pytest.raises(InvalidTransition):
        transition(application, S.queued)


def test_force_bypasses_validation_and_marks_history():
    session = _session()
    application = _application(session, status=S.offer)  # terminal

    result = transition(application, S.interview, force=True)

    assert result.status == S.interview
    assert result.status_history[-1]["forced"] is True


def test_non_forced_history_entry_has_no_forced_key():
    session = _session()
    application = _application(session, status=S.discovered)

    result = transition(application, S.queued)

    assert "forced" not in result.status_history[-1]


def test_note_is_recorded_in_history():
    session = _session()
    application = _application(session, status=S.discovered)

    result = transition(application, S.queued, note="applying via referral")

    assert result.status_history[-1]["note"] == "applying via referral"


def test_note_defaults_to_none():
    session = _session()
    application = _application(session, status=S.discovered)

    result = transition(application, S.queued)

    assert result.status_history[-1]["note"] is None


def test_history_entry_has_timestamp():
    session = _session()
    application = _application(session, status=S.discovered)

    result = transition(application, S.queued)

    assert "timestamp" in result.status_history[-1]
    assert isinstance(result.status_history[-1]["timestamp"], str)


def test_history_accumulates_across_multiple_transitions():
    session = _session()
    application = _application(session, status=S.discovered)

    transition(application, S.queued)
    transition(application, S.in_progress)
    transition(application, S.ready_to_submit)

    assert len(application.status_history) == 3
    assert [h["to"] for h in application.status_history] == ["queued", "in_progress", "ready_to_submit"]


def test_submitted_at_set_on_first_entry_into_submitted():
    session = _session()
    application = _application(session, status=S.ready_to_submit)
    assert application.submitted_at is None

    transition(application, S.submitted)

    assert application.submitted_at is not None


def test_submitted_at_not_overwritten_on_second_entry_into_submitted():
    session = _session()
    application = _application(session, status=S.ready_to_submit)

    transition(application, S.submitted)
    first_submitted_at = application.submitted_at

    # Bounce out (e.g. rejected -> forced back to ready_to_submit -> submitted again)
    transition(application, S.rejected)
    transition(application, S.ready_to_submit, force=True)
    transition(application, S.submitted)

    assert application.submitted_at == first_submitted_at


def test_transition_to_same_status_is_invalid_without_force():
    session = _session()
    application = _application(session, status=S.queued)

    with pytest.raises(InvalidTransition):
        transition(application, S.queued)
