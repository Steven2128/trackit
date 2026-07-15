"""Thin client for Expo's push service (https://exp.host/--/api/v2/push/send).

No SDK — one POST per chunk of 100 messages via httpx, same as the docs'
curl example. Returns the tokens Expo marked `DeviceNotRegistered` so the
caller can purge them; every other per-message error is logged and dropped
(a push is best-effort by nature).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
CHUNK_SIZE = 100  # Expo's documented max per request


@dataclass
class PushMessage:
    token: str
    title: str
    body: str


async def send_push_messages(messages: list[PushMessage]) -> list[str]:
    """Send all messages; return the list of dead tokens to delete."""
    dead_tokens: list[str] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for start in range(0, len(messages), CHUNK_SIZE):
            chunk = messages[start : start + CHUNK_SIZE]
            payload = [
                {
                    "to": m.token,
                    "title": m.title,
                    "body": m.body,
                    "sound": "default",
                }
                for m in chunk
            ]
            try:
                response = await client.post(EXPO_PUSH_URL, json=payload)
                response.raise_for_status()
            except httpx.HTTPError:
                log.exception("expo_push_request_failed", extra={"count": len(chunk)})
                continue

            tickets = response.json().get("data", [])
            for message, ticket in zip(chunk, tickets):
                if ticket.get("status") == "ok":
                    continue
                error = (ticket.get("details") or {}).get("error")
                if error == "DeviceNotRegistered":
                    dead_tokens.append(message.token)
                log.warning(
                    "expo_push_ticket_error",
                    extra={"error": error, "message": ticket.get("message")},
                )
    return dead_tokens
