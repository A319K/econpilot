from app.models.application import Application, ApplicationStatus
from app.models.mixins import utcnow

# Terminal statuses (offer, rejected, withdrawn) map to an empty set and are
# omitted from ALLOWED_TRANSITIONS for readability - looked up via .get(...,
# set()) everywhere below.
ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.discovered: {ApplicationStatus.queued, ApplicationStatus.withdrawn},
    ApplicationStatus.queued: {ApplicationStatus.in_progress, ApplicationStatus.withdrawn},
    ApplicationStatus.in_progress: {
        ApplicationStatus.ready_to_submit,
        ApplicationStatus.queued,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.ready_to_submit: {
        ApplicationStatus.submitted,
        ApplicationStatus.in_progress,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.submitted: {
        ApplicationStatus.oa,
        ApplicationStatus.interview,
        ApplicationStatus.offer,
        ApplicationStatus.rejected,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.oa: {
        ApplicationStatus.interview,
        ApplicationStatus.offer,
        ApplicationStatus.rejected,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.interview: {
        ApplicationStatus.offer,
        ApplicationStatus.rejected,
        ApplicationStatus.withdrawn,
    },
}


class InvalidTransition(Exception):
    """Raised when a status transition isn't allowed by the state machine."""


def transition(
    application: Application,
    new_status: ApplicationStatus,
    note: str | None = None,
    force: bool = False,
) -> Application:
    """Move `application` to `new_status`, validating against
    ALLOWED_TRANSITIONS unless force=True. Always appends a history entry
    and sets submitted_at the first time the application enters submitted.
    """
    current = application.status

    if not force:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise InvalidTransition(
                f"Cannot transition from {current.value!r} to {new_status.value!r}"
            )

    entry: dict = {
        "from": current.value,
        "to": new_status.value,
        "timestamp": utcnow().isoformat(),
        "note": note,
    }
    if force:
        entry["forced"] = True

    application.status_history = [*(application.status_history or []), entry]
    application.status = new_status

    if new_status == ApplicationStatus.submitted and application.submitted_at is None:
        application.submitted_at = utcnow()

    return application
