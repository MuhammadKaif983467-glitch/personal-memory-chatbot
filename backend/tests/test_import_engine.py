"""Tests for the universal conversation import engine.

Covers: WhatsApp parser, Telegram parser, Instagram parser, Facebook parser,
generic parser, normalizer, participant detector, orchestrator, and universal
inspector.
"""

from __future__ import annotations

from datetime import datetime

import pytest


# ---------------------------------------------------------------------------
# WhatsApp parser
# ---------------------------------------------------------------------------

class TestWhatsAppParser:
    def setup_method(self):
        from app.services.import_engine.parsers.whatsapp import WhatsAppParser
        self.parser = WhatsAppParser()

    def test_basic_messages(self):
        text = (
            "12/09/2025, 10:42 pm - Ali: bro kya scene\n"
            "12/09/2025, 10:43 pm - Kaif: hi\n"
        )
        msgs = self.parser.parse(text)
        assert len(msgs) == 2
        assert msgs[0].sender == "Ali"
        assert msgs[0].content == "bro kya scene"
        assert msgs[1].sender == "Kaif"

    def test_multiline_message(self):
        text = (
            "12/09/2025, 10:42 pm - Ali: bro listen\n"
            "\n"
            "kal jo hua na\n"
            "\n"
            "actually scene ye tha\n"
            "12/09/2025, 10:43 pm - Kaif: ok\n"
        )
        msgs = self.parser.parse(text)
        assert len(msgs) == 2
        assert "bro listen" in msgs[0].content
        assert "kal jo hua na" in msgs[0].content
        assert "actually scene ye tha" in msgs[0].content

    def test_media_omitted(self):
        text = "12/09/2025, 10:42 pm - Ali: <Media omitted>\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 1
        assert msgs[0].message_type == "media"

    def test_image_omitted(self):
        text = "12/09/2025, 10:42 pm - Ali: image omitted\n"
        msgs = self.parser.parse(text)
        assert msgs[0].message_type == "image"

    def test_system_message(self):
        text = (
            "12/09/2025, 10:42 pm - Ali: hello\n"
            "12/09/2025, 10:43 pm - system: Ali added Kaif\n"
        )
        msgs = self.parser.parse(text)
        assert len(msgs) == 2
        assert msgs[1].is_system is True
        assert msgs[1].message_type == "system"

    def test_bracket_timestamp_format(self):
        text = "[12/09/2025, 22:42] Ali: hello\n[12/09/2025, 22:43] Kaif: hi\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 2
        assert msgs[0].sender == "Ali"

    def test_yyyy_mm_dd_format(self):
        text = "2025-09-12 22:42:11 | Ali | hello\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 1

    def test_no_sender_returns_empty(self):
        text = "just some random text without a sender pattern\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 0

    def test_url_detection(self):
        text = "12/09/2025, 10:42 pm - Ali: https://example.com\n"
        msgs = self.parser.parse(text)
        assert msgs[0].message_type == "link"

    def test_system_end_to_end_encrypted(self):
        text = (
            "12/09/2025, 10:42 pm - system: Messages and calls are end-to-end encrypted\n"
            "12/09/2025, 10:43 pm - Ali: hello\n"
        )
        msgs = self.parser.parse(text)
        assert msgs[0].is_system is True


# ---------------------------------------------------------------------------
# Telegram parser
# ---------------------------------------------------------------------------

class TestTelegramParser:
    def setup_method(self):
        from app.services.import_engine.parsers.telegram import TelegramParser
        self.parser = TelegramParser()

    def test_basic_json(self):
        import json
        data = {
            "messages": [
                {"from": "Ali", "text": "hello", "date": "2025-09-12T22:42:00"},
                {"from": "Kaif", "text": "hi", "date": "2025-09-12T22:43:00"},
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 2
        assert msgs[0].sender == "Ali"
        assert msgs[0].content == "hello"

    def test_text_array_normalization(self):
        import json
        data = {
            "messages": [
                {
                    "from": "Ali",
                    "text": ["hello ", {"type": "bold", "text": "bro"}],
                    "date": "2025-09-12T22:42:00",
                }
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert msgs[0].content == "hello bro"

    def test_unix_timestamp(self):
        import json
        data = {
            "messages": [
                {"from": "Ali", "text": "hello", "date_unixtime": "1726184520"}
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert msgs[0].timestamp is not None

    def test_service_message(self):
        import json
        data = {
            "messages": [
                {"from": "Ali", "text": "", "type": "service", "action": "invite_members"}
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert msgs[0].is_system is True

    def test_empty_text_with_photo(self):
        import json
        data = {
            "messages": [
                {"from": "Ali", "text": "", "photo": "photo.jpg", "date": "2025-09-12T22:42:00"}
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert msgs[0].message_type == "image"

    def test_reactions(self):
        import json
        data = {
            "messages": [
                {
                    "from": "Ali",
                    "text": "hello",
                    "date": "2025-09-12T22:42:00",
                    "reactions": [{"type": "❤️", "count": 2}],
                }
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert len(msgs[0].reactions) == 1


# ---------------------------------------------------------------------------
# Instagram parser
# ---------------------------------------------------------------------------

class TestInstagramParser:
    def setup_method(self):
        from app.services.import_engine.parsers.instagram import InstagramParser
        self.parser = InstagramParser()

    def test_basic_json(self):
        import json
        data = {
            "participants": [{"name": "Ali"}, {"name": "Kaif"}],
            "messages": [
                {"sender_name": "Ali", "content": "hello", "timestamp_ms": 1726184520000},
                {"sender_name": "Kaif", "content": "hi", "timestamp_ms": 1726184580000},
            ],
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 2
        assert msgs[0].sender == "Ali"

    def test_photo_messages(self):
        import json
        data = {
            "participants": [{"name": "Ali"}],
            "messages": [
                {"sender_name": "Ali", "content": "", "timestamp_ms": 1726184520000, "photos": [{"uri": "img.jpg"}]},
            ],
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert msgs[0].message_type == "image"
        assert msgs[0].content == "[Photo]"

    def test_reactions(self):
        import json
        data = {
            "participants": [{"name": "Ali"}],
            "messages": [
                {
                    "sender_name": "Ali",
                    "content": "hello",
                    "timestamp_ms": 1726184520000,
                    "reactions": [{"reaction": "❤️", "actor": "Kaif"}],
                }
            ],
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert len(msgs[0].reactions) == 1
        assert msgs[0].reactions[0].emoji == "❤️"


# ---------------------------------------------------------------------------
# Facebook parser
# ---------------------------------------------------------------------------

class TestFacebookParser:
    def setup_method(self):
        from app.services.import_engine.parsers.facebook import FacebookParser
        self.parser = FacebookParser()

    def test_basic_json(self):
        import json
        data = {
            "participants": [{"name": "Ali"}, {"name": "Kaif"}],
            "messages": [
                {"sender_name": "Ali", "content": "hello", "timestamp_ms": 1726184520},
                {"sender_name": "Kaif", "content": "hi", "timestamp_ms": 1726184580},
            ],
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 2
        assert msgs[0].sender == "Ali"
        assert msgs[0].metadata["platform"] == "facebook"

    def test_unsent_message(self):
        import json
        data = {
            "participants": [{"name": "Ali"}],
            "messages": [
                {"sender_name": "Ali", "content": "oops", "timestamp_ms": 1726184520, "is_unsent": True},
            ],
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 1
        assert msgs[0].is_deleted is True


# ---------------------------------------------------------------------------
# Generic parser
# ---------------------------------------------------------------------------

class TestGenericParser:
    def setup_method(self):
        from app.services.import_engine.parsers.generic import GenericParser
        self.parser = GenericParser()

    def test_json_import(self):
        import json
        data = {
            "messages": [
                {"sender": "Ali", "content": "hello", "timestamp": "2025-09-12T22:42:00"},
                {"sender": "Kaif", "content": "hi", "timestamp": "2025-09-12T22:43:00"},
            ]
        }
        msgs = self.parser.parse(json.dumps(data))
        assert len(msgs) == 2

    def test_txt_sender_colon(self):
        text = "Ali: hello\nKaif: hi\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 2
        assert msgs[0].sender == "Ali"

    def test_txt_multiline(self):
        text = "Ali: hello\nthis is continuation\nKaif: hi\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 2
        assert "this is continuation" in msgs[0].content

    def test_csv_import(self):
        text = "sender,timestamp,content\nAli,2025-09-12,hello\nKaif,2025-09-12,hi\n"
        msgs = self.parser.parse(text)
        assert len(msgs) == 2

    def test_empty_text(self):
        msgs = self.parser.parse("")
        assert len(msgs) == 0


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

class TestNormalizer:
    def test_normalized_message_to_imported(self):
        from app.services.import_engine.normalizer import NormalizedMessage, normalize_messages
        from datetime import datetime

        msgs = [
            NormalizedMessage(sender="Ali", content="hello", timestamp=datetime(2025, 9, 12, 22, 42)),
            NormalizedMessage(sender="Kaif", content="hi", is_system=True),
            NormalizedMessage(sender="Ali", content="deleted", is_deleted=True),
        ]
        result = normalize_messages(msgs)
        assert len(result) == 2
        assert result[0].sender == "Ali"
        assert result[0].timestamp == "2025-09-12T22:42:00"


# ---------------------------------------------------------------------------
# Participant detector
# ---------------------------------------------------------------------------

class TestParticipantDetector:
    def test_detect_participants(self):
        from app.services.import_engine.normalizer import NormalizedMessage
        from app.services.import_engine.participant_detector import detect_participants

        msgs = [
            NormalizedMessage(sender="Ali", content="a"),
            NormalizedMessage(sender="Ali", content="b"),
            NormalizedMessage(sender="Kaif", content="c"),
            NormalizedMessage(sender="Ali", content="d"),
            NormalizedMessage(sender="Zoe", content="e"),
        ]
        participants = detect_participants(msgs)
        assert participants == ["Ali", "Kaif", "Zoe"]


# ---------------------------------------------------------------------------
# Universal inspector
# ---------------------------------------------------------------------------

class TestUniversalInspector:
    def setup_method(self):
        from app.services.import_engine.universal_inspector import UniversalInspector
        self.inspector = UniversalInspector()

    def test_detect_whatsapp_txt(self):
        text = (
            "12/09/2025, 10:42 pm - Ali: hello\n"
            "12/09/2025, 10:43 pm - Kaif: hi\n"
        ).encode("utf-8")
        result = self.inspector.inspect("chat.txt", text)
        assert result.platform == "whatsapp"
        assert result.file_type == "txt"

    def test_detect_json_generic(self):
        import json
        data = {"messages": [{"sender": "Ali", "content": "hello"}]}
        raw = json.dumps(data).encode("utf-8")
        result = self.inspector.inspect("import.json", raw)
        assert result.file_type == "json"

    def test_detect_csv(self):
        raw = b"sender,timestamp,content\nAli,2025-09-12,hello\n"
        result = self.inspector.inspect("chat.csv", raw)
        assert result.file_type == "csv"

    def test_telegram_json(self):
        import json
        data = {"messages": [{"from": "Ali", "text": "hello", "date": "2025-09-12T22:42:00"}]}
        raw = json.dumps(data).encode("utf-8")
        result = self.inspector.inspect("result.json", raw)
        assert result.platform == "telegram"


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------

class TestOrchestrator:
    def setup_method(self):
        from app.services.import_engine.orchestrator import ImportOrchestrator
        self.orch = ImportOrchestrator()

    def test_whatsapp_txt_import(self):
        text = (
            "12/09/2025, 10:42 pm - Ali: hello\n"
            "12/09/2025, 10:43 pm - Kaif: hi\n"
        ).encode("utf-8")
        payload = self.orch.import_file("chat.txt", text, consent_confirmed=True)
        assert payload.consent_confirmed is True
        assert len(payload.messages) >= 2
        assert payload.conversation.source == "whatsapp"

    def test_telegram_json_import(self):
        import json
        data = {
            "messages": [
                {"from": "Ali", "text": "hello", "date": "2025-09-12T22:42:00"},
                {"from": "Kaif", "text": "hi", "date": "2025-09-12T22:43:00"},
            ]
        }
        raw = json.dumps(data).encode("utf-8")
        payload = self.orch.import_file("result.json", raw, consent_confirmed=True)
        assert payload.conversation.source == "telegram"
        assert len(payload.messages) == 2

    def test_preview_file(self):
        text = (
            "12/09/2025, 10:42 pm - Ali: hello\n"
            "12/09/2025, 10:43 pm - Kaif: hi\n"
        ).encode("utf-8")
        preview = self.orch.preview_file("chat.txt", text)
        assert preview["platform"] == "whatsapp"
        assert preview["valid_messages"] == 2
        assert "Ali" in preview["participants"]
        assert "Kaif" in preview["participants"]

    def test_inspect_file(self):
        text = b"12/09/2025, 10:42 pm - Ali: hello\n"
        result = self.orch.inspect("chat.txt", text)
        assert result["platform"] == "whatsapp"
        assert result["file_type"] == "txt"

    def test_empty_file_raises(self):
        from app.core.exceptions import ImportValidationError
        with pytest.raises(ImportValidationError):
            self.orch.import_file("empty.txt", b"", consent_confirmed=True)
