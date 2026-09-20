"""Voice capability endpoint (Phase V).

Reports whether STT / TTS are usable so the frontend can enable the microphone
and read-aloud controls only when a provider is actually available. This is a
read-only status endpoint; no audio is ever uploaded to any service here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.core.config import Settings
from app.schemas.voice import VoiceStatusOut
from app.services.voice_service import VoiceService

router = APIRouter()


@router.get("/voice/status", response_model=VoiceStatusOut)
def voice_status(settings: Settings = Depends(get_settings)):
    return VoiceService(settings).status()