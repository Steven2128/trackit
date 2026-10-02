from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction
from app.parsers.davivienda import DaviviendaParser
from app.parsers.itau_co import ItauCoParser
from app.parsers.nequi import NequiParser

REGISTERED_PARSERS: list[EmailParser] = [
    ItauCoParser(),
    NequiParser(),
    DaviviendaParser(),
    # DaviplataParser(),     # TODO: user has no Daviplata email notifications yet
    # FalabellaCoParser(),   # TODO: only marketing emails observed; need transactional samples
]

__all__ = [
    "EmailEnvelope",
    "DaviviendaParser",
    "EmailParser",
    "ParsedTransaction",
    "ItauCoParser",
    "NequiParser",
    "REGISTERED_PARSERS",
]
