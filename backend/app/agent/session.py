"""In-process singleton holding the shared, long-lived browser and the
currently-active run. The browser is a single shared resource that must stay
open across HTTP requests (autofill -> pause -> resume are separate requests)
and across runs, so it cannot live in a request scope. Only ONE run may be
active at a time globally; the durable guard is the AgentRun table (see
is_run_active), this object just holds the live browser handle + background
task so they aren't garbage-collected.
"""

import asyncio

from sqlalchemy.orm import Session

from app.agent.browser import AgentBrowser
from app.models.agent_run import ACTIVE_STATUSES, AgentRun


class AgentSession:
    def __init__(self) -> None:
        self.browser: AgentBrowser | None = None
        self.active_run_id: int | None = None
        self.task: asyncio.Task | None = None


_session = AgentSession()


def get_session() -> AgentSession:
    return _session


def is_run_active(db: Session) -> bool:
    """True if any run is currently holding the browser (running or paused).
    Durable across process state; used for the global 409 guard."""
    return (
        db.query(AgentRun).filter(AgentRun.status.in_(list(ACTIVE_STATUSES))).first() is not None
    )
