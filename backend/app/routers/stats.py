from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.tracking.stats import StatsResponse, compute_stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    return compute_stats(db)
