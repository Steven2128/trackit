from app.parsers.cards.base import CardEmailParser, CardEvent, CardEventKind
from app.parsers.cards.rappicard import RappiCardParser

# Formats the user can pick when linking a debt to an email sender.
CARD_FORMATS: dict[str, CardEmailParser] = {
    p.key: p for p in (RappiCardParser(),)
}

__all__ = [
    "CARD_FORMATS",
    "CardEmailParser",
    "CardEvent",
    "CardEventKind",
    "RappiCardParser",
]
