from pydantic import BaseModel

from app.profile import (
    Education,
    EeoDefaults,
    Personal,
    Profile,
    Project,
    Skills,
    StandardAnswers,
    WorkExperience,
)


class ProfileRead(BaseModel):
    personal: Personal
    education: list[Education]
    work_experience: list[WorkExperience]
    projects: list[Project]
    skills: Skills
    eeo_defaults: EeoDefaults = EeoDefaults()
    standard_answers: StandardAnswers
    # True when profile.yaml doesn't exist yet and the bundled example is
    # standing in. Read-only; the dashboard shows a "this isn't you yet" banner.
    is_placeholder: bool = False

    @classmethod
    def from_profile(cls, profile: Profile, *, is_placeholder: bool = False) -> "ProfileRead":
        return cls(
            personal=profile.personal,
            education=profile.education,
            work_experience=profile.work_experience,
            projects=profile.projects,
            skills=profile.skills,
            eeo_defaults=profile.eeo_defaults,
            standard_answers=profile.standard_answers,
            is_placeholder=is_placeholder,
        )


class ProfileWrite(BaseModel):
    """Full replacement of profile.yaml, sent by the dashboard's Profile page.

    Mirrors `Profile` exactly — a save always writes the whole document, so
    there is no partial-update merge to get wrong.
    """

    personal: Personal
    education: list[Education]
    work_experience: list[WorkExperience]
    projects: list[Project]
    skills: Skills
    eeo_defaults: EeoDefaults = EeoDefaults()
    standard_answers: StandardAnswers

    def to_profile(self) -> Profile:
        return Profile.model_validate(self.model_dump())
