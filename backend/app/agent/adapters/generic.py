from app.agent.adapters.base import Adapter


class GenericAdapter(Adapter):
    """Fallback adapter for unrecognized ATS/careers pages. Uses the base
    generic behavior verbatim."""

    name = "generic"
