from app.agent.adapters.base import Adapter


class AshbyAdapter(Adapter):
    name = "ashby"

    def step_hints(self) -> str:
        return (
            "Ashby: a single-page application rendered as a dynamic form. "
            "Custom questions may use styled radio/select controls - match the "
            "profile value to one of the given options rather than typing. The "
            "review state is the fully-filled form with a Submit button present."
        )
