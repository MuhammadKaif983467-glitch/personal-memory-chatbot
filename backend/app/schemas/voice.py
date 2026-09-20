"""Schemas for the voice layer (Phase V architecture).

The backend exposes capability/status only. Audio capture and playback happen
in the frontend (Web Speech API / MediaRecorder); the real provider plugins
(OpenAI Whisper, elevenlabs TTS, local pipeline) are stubs until the user opts
in with their own API keys. Nothing in the two-person memory product depends on
voice being enabled.
"""

from __future__ import annotations

from pydantic import BaseModel


class VoiceProviderOut(BaseModel):
    id: str
    name: str
    kind: str = "stt"
    available: bool
    requires_key: bool = True
    error: str = ""


class VoiceStatusOut(BaseModel):
    enabled: bool
    stt: VoiceProviderOut
    tts: VoiceProviderOut
    message: str = ""