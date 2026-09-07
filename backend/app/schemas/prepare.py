from pydantic import BaseModel

from app.materials.prepare import PrepareReport


class PrepareRequest(BaseModel):
    # None -> use settings.prepare_tailor_default (select-only by default).
    # Pass true/false to override per request.
    tailor: bool | None = None
    cover_letter: bool = True


__all__ = ["PrepareRequest", "PrepareReport"]
