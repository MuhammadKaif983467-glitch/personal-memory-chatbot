"""Platform-specific parsers for the universal import engine."""

from app.services.import_engine.parsers.whatsapp import WhatsAppParser
from app.services.import_engine.parsers.telegram import TelegramParser
from app.services.import_engine.parsers.instagram import InstagramParser
from app.services.import_engine.parsers.facebook import FacebookParser
from app.services.import_engine.parsers.generic import GenericParser

PARSERS = {
    "whatsapp": WhatsAppParser,
    "telegram": TelegramParser,
    "instagram": InstagramParser,
    "facebook": FacebookParser,
    "generic": GenericParser,
}


def get_parser(platform: str):
    """Return parser class for the given platform."""
    return PARSERS.get(platform, GenericParser)
