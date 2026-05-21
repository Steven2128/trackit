from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction
from app.parsers.itau_co import ItauCoParser

REGISTERED_PARSERS: list[EmailParser] = [
    ItauCoParser(),
    # NequiParser(),         # TODO: when we have Nequi email fixtures
    # DaviplataParser(),     # TODO: when we have Daviplata email fixtures
    # FalabellaCoParser(),   # TODO: when we have Falabella email fixtures
]

__all__ = [
    "EmailEnvelope",
    "EmailParser",
    "ParsedTransaction",
    "ItauCoParser",
    "REGISTERED_PARSERS",
]
