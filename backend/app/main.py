from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import SessionLocal
from app.profile import get_profile, profile_is_placeholder, save_profile
from app.routers.agent_runs import router as agent_runs_router
from app.routers.answer_bank import router as answer_bank_router
from app.routers.applications import router as applications_router
from app.routers.companies import router as companies_router
from app.routers.cover_letters import router as cover_letters_router
from app.routers.frontend_support import router as frontend_support_router
from app.routers.jobs import router as jobs_router
from app.routers.notify import router as notify_router
from app.routers.resumes import router as resumes_router
from app.routers.scan import router as scan_router
from app.routers.stats import router as stats_router
from app.routers.watcher import router as watcher_router
from app.schemas.profile import ProfileRead, ProfileWrite
from app.watcher.scheduler import get_watcher_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_watcher_service().start()
    yield
    get_watcher_service().stop()


app = FastAPI(title="EconPilot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Vite picks the next free port (5174, 5175, …) when an earlier one is
    # taken, so allow a small range rather than pinning a single origin.
    allow_origins=[f"http://localhost:{port}" for port in range(5173, 5181)],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies_router)
app.include_router(jobs_router)
app.include_router(scan_router)
app.include_router(resumes_router)
app.include_router(cover_letters_router)
app.include_router(applications_router)
app.include_router(agent_runs_router)
app.include_router(answer_bank_router)
app.include_router(stats_router)
app.include_router(frontend_support_router)
app.include_router(notify_router)
app.include_router(watcher_router)


@app.get("/health")
def health():
    db_status = "ok"
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        db_status = "fail"

    return {"status": "ok", "db": db_status}


@app.get("/profile", response_model=ProfileRead)
def read_profile():
    return ProfileRead.from_profile(get_profile(), is_placeholder=profile_is_placeholder())


@app.put("/profile", response_model=ProfileRead)
def write_profile(payload: ProfileWrite):
    """Replace profile.yaml with `payload`.

    This is how the dashboard's Profile page saves, so that filling in your
    details never requires opening a text editor. Validation errors come back
    as a 422 the page renders inline.
    """
    saved = save_profile(payload.to_profile())
    return ProfileRead.from_profile(saved, is_placeholder=profile_is_placeholder())
