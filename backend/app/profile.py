import os
import tempfile
import warnings
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, EmailStr

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "profile.yaml"
PROFILE_EXAMPLE_PATH = Path(__file__).resolve().parent.parent.parent / "profile.example.yaml"


class Personal(BaseModel):
    name: str
    email: EmailStr
    phone: str
    city: str
    state: str
    address: str | None = None
    zip: str | None = None
    country: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class Education(BaseModel):
    school: str
    degree: str
    major: str
    gpa: float | None = None
    start: str
    end: str


class WorkExperience(BaseModel):
    company: str
    title: str
    start: str
    end: str
    bullets: list[str] = []


class Project(BaseModel):
    name: str
    description: str | None = None
    bullets: list[str] = []
    url: str | None = None


class Skills(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []


class EeoDefaults(BaseModel):
    gender: str | None = None
    ethnicity: str | None = None
    veteran: str | None = None
    disability: str | None = None


class StandardAnswers(BaseModel):
    work_authorization: str
    requires_sponsorship: bool
    willing_to_relocate: bool
    graduation_date: str


class Profile(BaseModel):
    personal: Personal
    education: list[Education]
    work_experience: list[WorkExperience]
    projects: list[Project]
    skills: Skills
    eeo_defaults: EeoDefaults = EeoDefaults()
    standard_answers: StandardAnswers


def profile_is_placeholder() -> bool:
    """True when no real profile.yaml exists and the example is standing in.

    The dashboard uses this to prompt the user to fill in their details rather
    than silently generating applications for "Jordan Example".
    """
    return not PROFILE_PATH.exists()


@lru_cache
def get_profile() -> Profile:
    path = PROFILE_PATH
    if not path.exists():
        warnings.warn(
            f"profile.yaml not found at {PROFILE_PATH}; falling back to profile.example.yaml",
            stacklevel=2,
        )
        path = PROFILE_EXAMPLE_PATH

    with path.open("r") as f:
        raw = yaml.safe_load(f)

    return Profile.model_validate(raw)


def save_profile(profile: Profile) -> Profile:
    """Write `profile` to profile.yaml and invalidate the read cache.

    Written atomically (temp file in the same directory + os.replace) so an
    interrupted save can never leave a half-written profile behind — the old
    file survives instead. Always targets PROFILE_PATH; the bundled example is
    never overwritten.
    """
    payload = profile.model_dump(mode="json", exclude_none=True)

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(PROFILE_PATH.parent), prefix=".profile.", suffix=".yaml.tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, PROFILE_PATH)
    except BaseException:
        # Leave no stray temp file behind if the write or replace failed.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    get_profile.cache_clear()
    return get_profile()
