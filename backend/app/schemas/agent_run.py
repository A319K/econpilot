from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.agent_run import AgentRunStatus, PauseReason


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    status: AgentRunStatus
    pause_reason: PauseReason | None
    started_at: datetime
    ended_at: datetime | None
    action_log: list | None
    llm_calls: int
    screenshots_dir: str | None
