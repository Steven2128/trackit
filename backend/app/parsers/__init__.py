from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction
from app.parsers.itau_co import ItauCoParser
from app.parsers.nequi import NequiParser

REGISTERED_PARSERS: list[EmailParser] = [
    ItauCoParser(),
    NequiParser(),
    # DaviplataParser(),     # TODO: user has no Daviplata email notifications yet
    # FalabellaCoParser(),   # TODO: only marketing emails observed; need transactional samples
]

__all__ = [
    "EmailEnvelope",
    "EmailParser",
    "ParsedTransaction",
    "ItauCoParser",
    "NequiParser",
    "REGISTERED_PARSERS",
]
