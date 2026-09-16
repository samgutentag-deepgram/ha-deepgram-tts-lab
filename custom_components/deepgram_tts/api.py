"""Authenticated synthesis against both Deepgram speak endpoints.

Chapter 2 of the build. One public synthesis method, two URLs, chosen by model prefix, because
`/v2/speak` rejects an Aura model with V1_MODEL_ON_V2_SPEAK_ENDPOINT and `/v1/speak` has never
heard of Flux.

The client hands back whatever bytes the API produced. Decoding and re-encoding here would be a
full transcode per spoken sentence on a Raspberry Pi, and Home Assistant already converts in
`_async_convert_audio` when the requested format differs from what the entity returned.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
import json
import logging

from aiohttp import ClientError, ClientSession

from .const import (
    CONTAINER_NONE,
    CONTENT_TYPE_EXTENSIONS,
    DEFAULT_EXTENSION,
    DEFAULT_VOICE,
    ENCODING_MP3,
    ERROR_BODY_MAX_CHARS,
    FAMILY_FLUX,
    TIMEOUT_SPEAK,
    URL_SPEAK_AURA,
    URL_SPEAK_FLUX,
    VERIFY_KEY_TEXT,
)
from .errors import (
    DeepgramAuthError,
    DeepgramConnectionError,
    DeepgramError,
    DeepgramRequestError,
)
from .models import family_for_model
from .stream import FluxSocket

_LOGGER = logging.getLogger(__name__)

_AUTH_STATUSES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    """One completed batch synthesis."""

    audio: bytes
    """Exactly the bytes the API returned. Never decoded, trimmed, or re-encoded."""

    extension: str
    """File extension for the audio, for Home Assistant's format handling."""

    content_type: str
    """The response Content-Type verbatim, empty when the API sent none."""


def _extension_for(content_type: str, container: str | None, encoding: str | None) -> str:
    """Work out the file extension for a synthesis response."""
    base = content_type.split(";")[0].strip().lower()
    if extension := CONTENT_TYPE_EXTENSIONS.get(base):
        return extension
    if container is not None and container != CONTAINER_NONE:
        return container
    if encoding is not None:
        return encoding
    return DEFAULT_EXTENSION


def _error_for(status: int, body: bytes, url: str) -> DeepgramError:
    """Build the typed error for a rejected request.

    Deepgram sends `{"err_code": ..., "err_msg": ...}` on rejection, but a proxy or a 5xx can
    send anything at all, so parsing must never be the thing that raises.
    """
    code: str | None = None
    message: str | None = None

    try:
        payload = json.loads(body)
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        if (raw_code := payload.get("err_code")) is not None:
            code = str(raw_code)
        if (raw_message := payload.get("err_msg")) is not None:
            message = str(raw_message)

    if message is None:
        snippet = body.decode("utf-8", errors="replace").strip()[:ERROR_BODY_MAX_CHARS]
        message = snippet or "empty response body"

    if status in _AUTH_STATUSES:
        return DeepgramAuthError(f"Deepgram rejected the API key (HTTP {status}): {message}")

    return DeepgramRequestError(
        f"{url} returned HTTP {status}: {message}", status=status, code=code
    )


class DeepgramClient:
    """Batch text to speech against Deepgram's Flux and Aura endpoints."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Store the shared Home Assistant session and the key to authenticate with."""
        self._session = session
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    def stream(self, *, model: str, speed: float | None = None) -> FluxSocket:
        """Open one streaming turn against the Flux socket.

        Inert on main for the same reason `stream.py` is: Home Assistant only routes down the
        streaming path when the entity defines `async_stream_tts_audio`, and nothing here does.
        This exists so `scripts/live_stream_check.py` can exercise the real socket client
        against the real API without the entity opting in, which is what the review asked for.

        The client hands back a socket rather than exposing the API key, so the key stays in the
        one object that owns it.
        """
        return FluxSocket(self._session, self._api_key, model=model, speed=speed)

    async def async_verify_key(self) -> None:
        """Round trip a one-word synthesis and discard the audio.

        Raise DeepgramAuthError on a rejected key, DeepgramConnectionError when the request
        never completed, and DeepgramRequestError for anything else.
        """
        try:
            await self.async_synthesize(VERIFY_KEY_TEXT, model=DEFAULT_VOICE)
        except DeepgramError:
            # Above the broad handler on purpose. Rewrapping these is what made the codebase
            # this project replaces undebuggable: an expired key read as a dead network.
            raise
        except Exception as err:
            raise DeepgramRequestError(f"Key verification failed: {err}") from err

    async def async_synthesize(
        self,
        text: str,
        *,
        model: str,
        encoding: str | None = None,
        container: str | None = None,
        sample_rate: int | None = None,
        speed: float | None = None,
    ) -> SynthesisResult:
        """Synthesize `text` with `model` and return the audio the API produced."""
        family = family_for_model(model)
        url = URL_SPEAK_FLUX if family == FAMILY_FLUX else URL_SPEAK_AURA
        params = _build_params(
            model=model,
            family=family,
            encoding=encoding,
            container=container,
            sample_rate=sample_rate,
            speed=speed,
        )

        try:
            async with (
                asyncio.timeout(TIMEOUT_SPEAK),
                self._session.post(
                    url, params=params, json={"text": text}, headers=self._headers
                ) as response,
            ):
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                body = await response.read()
        except TimeoutError as err:
            raise DeepgramConnectionError(f"{url} did not respond within {TIMEOUT_SPEAK}s") from err
        except ClientError as err:
            raise DeepgramConnectionError(f"Could not reach {url}: {err}") from err

        if status != HTTPStatus.OK:
            raise _error_for(status, body, url)

        return SynthesisResult(
            audio=body,
            extension=_extension_for(content_type, container, encoding),
            content_type=content_type,
        )


def _build_params(
    *,
    model: str,
    family: str,
    encoding: str | None,
    container: str | None,
    sample_rate: int | None,
    speed: float | None,
) -> dict[str, str]:
    """Build the query string from the arguments that were actually given.

    Only known parameters, and only the ones with a value: the API rejects anything it does not
    recognize with INVALID_QUERY_PARAMETER rather than ignoring it.
    """
    params: dict[str, str] = {"model": model}

    if encoding is not None:
        params["encoding"] = encoding
    if container is not None:
        params["container"] = container

    if sample_rate is not None:
        # Dropped for an explicit mp3 AND for no encoding at all, because mp3 is the default.
        # Verified live 2026-09-16: sample_rate with no encoding returns
        # 400 UNSUPPORTED_AUDIO_FORMAT, "`sample_rate` is not applicable when `encoding=mp3`".
        # Chapter 2 followed the interface contract literally and only dropped it for the
        # explicit case, which left a request the API rejects reachable through the default.
        if encoding in (None, ENCODING_MP3):
            _LOGGER.debug(
                "Dropping sample_rate=%s: not applicable to mp3, which is the default when no "
                "encoding is given",
                sample_rate,
            )
        else:
            params["sample_rate"] = str(sample_rate)

    if speed is not None:
        if family == FAMILY_FLUX:
            params["speed"] = str(speed)
        else:
            _LOGGER.debug("Dropping speed=%s: %s is not a Flux model", speed, model)

    return params
