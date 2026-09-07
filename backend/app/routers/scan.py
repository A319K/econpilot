from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.discovery.scan import ScanReport, run_scan
from app.schemas.scan import ScanRequest

router = APIRouter(tags=["scan"])


@router.post("/scan", response_model=ScanReport)
async def scan(payload: ScanRequest = ScanRequest(), db: Session = Depends(get_db)):
    return await run_scan(
        db,
        role_type=payload.role_type,
        targets_only=payload.targets_only,
        max_age_days=payload.max_age_days,
    )
