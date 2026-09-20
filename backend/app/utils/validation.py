"""Validation helpers shared by import paths and API schemas."""

from __future__ import annotations

from typing import Any


def collect_import_errors(payload: Any) -> list[str]:
    """Return human-readable validation errors raised by bad import payloads.

    Never silently drops a message: any error surfaces in the report so the
    user can fix the file and re-import.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Import payload must be a JSON object."]

    conversation = payload.get("conversation")
    if not isinstance(conversation, dict) or not conversation.get("person"):
        errors.append("conversation.person is required (the person you chatted with).")

    if not isinstance(payload.get("consent_confirmed"), bool):
        errors.append("consent_confirmed must be true or false.")
    if not isinstance(payload.get("messages"), list) or not payload["messages"]:
        errors.append("messages must be a non-empty array.")

    for idx, message in enumerate(payload.get("messages", [])):
        if not isinstance(message, dict):
            errors.append(f"messages[{idx}] must be an object.")
            continue
        if "content" not in message and "message_type" not in message:
            errors.append(f"messages[{idx}] needs 'content' (or a media message_type).")
        if message.get("content") is not None and not isinstance(message["content"], str):
            errors.append(f"messages[{idx}].content must be a string.")
        if "sender" not in message or not str(message.get("sender", "")).strip():
            errors.append(f"messages[{idx}].sender is required.")
    return errors