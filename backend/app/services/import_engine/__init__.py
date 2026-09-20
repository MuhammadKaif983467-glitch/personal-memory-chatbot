"""Universal conversation import engine.

Detects file format and platform, parses conversations from WhatsApp,
Telegram, Instagram, Facebook/Messenger, and generic formats, normalizes
messages, detects participants, and produces clean ImportPayload objects.
"""

from app.services.import_engine.universal_inspector import UniversalInspector, DetectedFormat
from app.services.import_engine.normalizer import NormalizedMessage, normalize_messages
from app.services.import_engine.participant_detector import detect_participants

__all__ = [
    "UniversalInspector",
    "DetectedFormat",
    "NormalizedMessage",
    "normalize_messages",
    "detect_participants",
]
