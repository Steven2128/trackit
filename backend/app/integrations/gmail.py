from dataclasses import dataclass


@dataclass
class GmailCredentials:
    access_token: str
    refresh_token: str | None = None


class GmailClient:
    """Stub Gmail client. Real implementation will use google-api-python-client."""

    def __init__(self, credentials: GmailCredentials) -> None:
        self.credentials = credentials

    def list_messages(self, query: str = "", max_results: int = 50) -> list[dict]:
        raise NotImplementedError("Gmail listing is not implemented yet")

    def get_message(self, message_id: str) -> dict:
        raise NotImplementedError("Gmail message fetch is not implemented yet")
