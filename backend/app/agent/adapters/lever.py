from app.agent.adapters.base import Adapter


class LeverAdapter(Adapter):
    name = "lever"

    def step_hints(self) -> str:
        return (
            "Lever: uploading the resume first may auto-parse and pre-fill some "
            "fields - re-read the snapshot after uploading before filling the "
            "rest, and do not overwrite fields that already hold a correct "
            "value. Single page; the review state is the fully-filled form with "
            "a Submit button present."
        )
