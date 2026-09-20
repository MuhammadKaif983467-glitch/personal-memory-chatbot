"""Auto-detect participants from normalized messages."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from app.services.import_engine.normalizer import NormalizedMessage


def detect_participants(messages: Sequence[NormalizedMessage]) -> list:
    """Return participant names sorted by message count descending."""
    counter: Counter = Counter()
    for msg in messages:
        if not msg.is_system and msg.sender:
            counter[msg.sender] += 1
    return [name for name, _ in counter.most_common()]


def detect_conversations(messages: Sequence[NormalizedMessage]) -> list:
    """Group messages by conversation_id, returning list of (title, messages)."""
    from app.services.import_engine.normalizer import NormalizedConversation

    groups: dict = {}
    for msg in messages:
        cid = msg.conversation_id or "__default__"
        if cid not in groups:
            groups[cid] = []
        groups[cid].append(msg)

    conversations = []
    for cid, msgs in groups.items():
        participants = detect_participants(msgs)
        title = cid if cid != "__default__" else (
            f"Chat with {participants[0]}" if len(participants) == 1
            else f"Group chat ({', '.join(participants[:3])})"
        )
        conversations.append(NormalizedConversation(
            title=title,
            messages=msgs,
            participants=participants,
            source_platform=msgs[0].metadata.get("platform", "unknown") if msgs else "unknown",
        ))
    return conversations
