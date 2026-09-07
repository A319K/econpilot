from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent import runs as agent_runs
from app.db import get_db
from app.models.agent_run import AgentRun
from app.schemas.agent_run import AgentRunRead

router = APIRouter(tags=["agent-runs"])


def _get_run(db: Session, run_id: int) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.get("/agent-runs/{run_id}", response_model=AgentRunRead)
def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    """Live status + action log + pause reason for a run (2s-polled by the UI)."""
    return AgentRunRead.model_validate(_get_run(db, run_id))


@router.post("/agent-runs/{run_id}/resume", response_model=AgentRunRead)
async def resume_agent_run(run_id: int, db: Session = Depends(get_db)):
    """Resume a paused run: the agent re-snapshots the still-open browser (where
    the human fixed the blocker) and continues."""
    try:
        run = agent_runs.resume_run(db, run_id)
    except agent_runs.AgentRunError as exc:
        status = 404 if "not found" in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return AgentRunRead.model_validate(run)


@router.post("/agent-runs/{run_id}/abandon", response_model=AgentRunRead)
def abandon_agent_run(run_id: int, db: Session = Depends(get_db)):
    """Give up on a run. The browser is left open for the human to close."""
    try:
        run = agent_runs.abandon_run(db, run_id)
    except agent_runs.AgentRunError as exc:
        status = 404 if "not found" in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return AgentRunRead.model_validate(run)
