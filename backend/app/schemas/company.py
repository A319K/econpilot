from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.company import AtsType


class CompanyBase(BaseModel):
    name: str
    careers_url: str | None = None
    ats_type: AtsType = AtsType.unknown
    ats_board_id: str | None = None
    is_target: bool = False
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    careers_url: str | None = None
    ats_type: AtsType | None = None
    ats_board_id: str | None = None
    is_target: bool | None = None
    notes: str | None = None


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
