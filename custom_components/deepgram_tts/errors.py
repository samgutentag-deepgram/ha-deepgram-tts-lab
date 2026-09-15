"""Typed errors for the Deepgram TTS integration.

Every caller needs to tell an expired key from a dead network, so each failure mode gets its
own class and the client reraises these before any broad handler runs.
"""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class DeepgramError(HomeAssistantError):
    """Base class for every error this integration raises."""


class DeepgramAuthError(DeepgramError):
    """The API key was rejected (HTTP 401 or 403)."""


class DeepgramConnectionError(DeepgramError):
    """The request never completed: DNS, TCP, TLS, timeout, or a dropped socket."""


class DeepgramRequestError(DeepgramError):
    """The API rejected the request itself (4xx other than auth, or a 5xx)."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None) -> None:
        """Keep the HTTP status and Deepgram err_code so logs name the real cause."""
        super().__init__(message)
        self.status = status
        self.code = code
