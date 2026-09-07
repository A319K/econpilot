from pydantic import BaseModel

from app.profile import Education, Personal, Profile, Project, Skills, StandardAnswers, WorkExperience


class ProfileRead(BaseModel):
    personal: Personal
    education: list[Education]
    work_experience: list[WorkExperience]
    projects: list[Project]
    skills: Skills
    standard_answers: StandardAnswers

    @classmethod
    def from_profile(cls, profile: Profile) -> "ProfileRead":
        return cls(
            personal=profile.personal,
            education=profile.education,
            work_experience=profile.work_experience,
            projects=profile.projects,
            skills=profile.skills,
            standard_answers=profile.standard_answers,
        )
