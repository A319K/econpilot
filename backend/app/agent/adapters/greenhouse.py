from app.agent.adapters.base import Adapter


class GreenhouseAdapter(Adapter):
    name = "greenhouse"

    def step_hints(self) -> str:
        return (
            "Greenhouse: a single long form on one page (no multi-step wizard). "
            "Fill every field then treat the page as review once all required "
            "fields are filled and the Submit Application button is present - do "
            "NOT click it. EEO questions appear as dropdowns near the bottom."
        )
