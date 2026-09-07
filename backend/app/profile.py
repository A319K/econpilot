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
