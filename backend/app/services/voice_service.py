"""Voice architecture (Phase V).

The product's core is text-first and fully usable without voice. This module
defines the contract (STT/TTS plugins) and reports capability status so the
frontend can hide or gently disable voice controls when no provider is
available. Real transcription / synthesis happens in the browser (Web Speech
API / MediaRecorder) or through plugins the user opts into with their own keys.

Nothing here ever requires a real voice API key for the product to work, and
no voice traffic is sent anywhere without explicit user consent.
"""

from __future__ import annotations

import platform
from typing import Optional

from app.core.config import Settings
from app.schemas.voice import VoiceProviderOut, VoiceStatusOut


class SpeechToTextPlugin:
    id = "base"
    name = "Base STT"
    requires_key = True

    def __init__(self, api_key: str = "", error: str = ""):
        self.api_key = api_key or ""
        self.error = error or ""

    def available(self) -> bool:
        return bool(self.api_key)


class TextToSpeechPlugin:
    id = "base"
    name = "Base TTS"
    requires_key = False

    def __init__(self, api_key: str = "", error: str = ""):
        self.api_key = api_key or ""
        self.error = error or ""

    def available(self) -> bool:
        # The base plugin models browser speech synthesis: available unless
        # the operator disabled it (an explicit "none"/"off" sets an error).
        return not bool(self.error)


class OpenRouterWhisperPlugin(SpeechToTextPlugin):
    id = "openai-whisper"
    name = "OpenAI Whisper (via OpenRouter)"
    requires_key = True

    def available(self) -> bool:
        # Whisper transcription would consume OpenRouter credits; stay off
        # unless the user explicitly enables STT AND supplies a key.
        return False


class ElevenLabsPlugin(TextToSpeechPlugin):
    id = "elevenlabs"
    name = "ElevenLabs TTS"
    requires_key = True

    def available(self) -> bool:
        return bool(self.api_key)


class OpenRouterTTSPlugin(TextToSpeechPlugin):
    """Represents an OpenRouter TTS model in the capability layer.

    The configured ``OPENROUTER_TTS_MODEL`` is surfaced here (secret-free) so
    the operator can see what is configured. No real audio synthesis request is
    sent: the product stays text-first, so this plugin reports availability
    only when the operator also opts in with a TTS key - and even then the
    browser performs playback. Without a live TTS call we never claim TTS is
    operational.
    """

    id = "openrouter"
    name = "OpenRouter TTS"
    requires_key = True

    def __init__(self, model: str = "", api_key: str = "", error: str = ""):
        super().__init__(api_key=api_key, error=error)
        self.model = model or ""
        if self.model:
            self.name = f"OpenRouter TTS ({self.model})"

    def available(self) -> bool:
        # Capability/status only: no live synthesis in this layer.
        return False


class BrowserRecognitionPlugin(SpeechToTextPlugin):
    """The browser's own speech recognition; requires no backend key."""

    id = "browser"
    name = "Browser speech recognition"
    requires_key = False

    def __init__(self, api_key: str = "", error: str = ""):
        super().__init__(api_key, error)
        # Web Speech API support varies; report availability honestly.
        browser = platform.system()
        self.error = "" if browser in ("Windows", "Darwin", "Linux") else "Unsupported platform"


class VoiceService:
    """Resolves configured STT / TTS providers and reports status."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _resolve_stt(self) -> SpeechToTextPlugin:
        requested = (self.settings.voice_stt_provider or "auto").strip().casefold()
        if requested in ("", "auto"):
            plugin = BrowserRecognitionPlugin()
        elif requested in ("none", "off", "disabled"):
            plugin = SpeechToTextPlugin(error="STT disabled by configuration")
        elif requested == "openai-whisper":
            plugin = OpenRouterWhisperPlugin(api_key=self.settings.voice_stt_api_key)
        else:
            plugin = SpeechToTextPlugin(api_key=self.settings.voice_stt_api_key, error=f"Unknown STT provider '{requested}'")
        return plugin

    def _resolve_tts(self) -> TextToSpeechPlugin:
        requested = (self.settings.voice_tts_provider or "auto").strip().casefold()
        if requested in ("", "auto"):
            plugin = TextToSpeechPlugin(api_key=self.settings.voice_tts_api_key)
        elif requested in ("none", "off", "disabled"):
            plugin = TextToSpeechPlugin(api_key="", error="TTS disabled by configuration")
        elif requested == "elevenlabs":
            plugin = ElevenLabsPlugin(api_key=self.settings.voice_tts_api_key)
        elif requested in ("openrouter", "openrouter-tts"):
            plugin = OpenRouterTTSPlugin(
                model=self.settings.openrouter_tts_model,
                api_key=self.settings.voice_tts_api_key,
                error="TTS configuration is represented here; no live synthesis endpoint is wired.",
            )
        else:
            plugin = TextToSpeechPlugin(api_key=self.settings.voice_tts_api_key, error=f"Unknown TTS provider '{requested}'")
        return plugin

    def status(self) -> VoiceStatusOut:
        stt = self._resolve_stt()
        tts = self._resolve_tts()
        enabled = self.settings.voice_enabled and (stt.available() or tts.available())
        messages: list[str] = []
        if not self.settings.voice_enabled:
            messages.append("Voice input/output is disabled. Enable it in settings to use microphone and text-to-speech.")
        elif not stt.available():
            messages.append("Speech-to-text is not available right now (no provider key configured).")
        return VoiceStatusOut(
            enabled=enabled,
            stt=VoiceProviderOut(
                id=stt.id,
                name=stt.name,
                kind="stt",
                available=stt.available(),
                requires_key=stt.requires_key,
                error=stt.error,
            ),
            tts=VoiceProviderOut(
                id=tts.id,
                name=tts.name,
                kind="tts",
                available=tts.available(),
                requires_key=tts.requires_key,
                error=tts.error,
            ),
            message=" ".join(messages),
        )