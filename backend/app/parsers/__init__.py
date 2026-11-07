from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction
from app.parsers.davivienda import DaviviendaParser
from app.parsers.itau_co import ItauCoParser
from app.parsers.nequi import NequiParser
from app.parsers.pse import PseParser
from app.parsers.uber import UberParser

REGISTERED_PARSERS: list[EmailParser] = [
    ItauCoParser(),
    NequiParser(),
    DaviviendaParser(),
    PseParser(),
    UberParser(),
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
    "PseParser",
    "UberParser",
    "REGISTERED_PARSERS",
]
