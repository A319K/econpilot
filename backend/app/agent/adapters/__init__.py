"""ATS detection + per-provider adapters (§2)."""

from app.agent.adapters.base import Adapter
from app.agent.adapters.detect import ATS_TYPES, detect_ats, get_adapter

__all__ = ["Adapter", "ATS_TYPES", "detect_ats", "get_adapter"]
