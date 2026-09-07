from app.agent.adapters.base import Adapter

# Workday almost always gates the application behind an account
# login/creation wall on first use per company. The agent never creates
# accounts or handles credentials (§0), so the expected outcome of the first
# Workday run for a given company is a PAUSE at that wall. The human logs in
# once in the shared persistent browser, then resumes; the session cookie is
# reused on subsequent runs. This is documented in the README.
EXPECTED_LOGIN_PAUSE = True


class WorkdayAdapter(Adapter):
    name = "workday"

    def step_hints(self) -> str:
        return (
            "Workday: a multi-page wizard. First-time applications require a "
            "candidate account (Sign In / Create Account) - if you hit that "
            "wall, PAUSE with login_required; never create an account or enter "
            "credentials. Typical page order: My Information, My Experience, "
            "Application Questions, Voluntary Disclosures (EEO), Review. Advance "
            "each page with its 'Save and Continue' / 'Next' button via "
            "step_done. The Review page is the final stop - do not submit."
        )

    def entry_keywords(self) -> list[str]:
        # Workday shows "Apply", then often "Apply Manually" vs "Autofill with
        # Resume"; prefer the manual path so we control the fields.
        return ["apply manually", "apply"]
