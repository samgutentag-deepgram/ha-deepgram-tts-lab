"""Does asyncio.timeout cover the body read, and what error type escapes a bad catalog body?

Written as pytest tests because they need the `hass` and `aioclient_mock` fixtures, but they
live under docs/review/ and are NOT collected by the suite (testpaths = ["tests"]). Run them
explicitly:

    .venv/bin/python -m pytest docs/review/repro/test_repro_timeouts_and_errors.py -v -p no:cacheprovider
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import json
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.api import DeepgramClient
from custom_components.deepgram_tts.catalog import async_fetch_catalog
from custom_components.deepgram_tts.const import (
    DEFAULT_VOICE,
    DOMAIN,
    URL_MODELS_AURA,
    URL_MODELS_FLUX,
    URL_SPEAK_FLUX,
)
from custom_components.deepgram_tts.errors import DeepgramConnectionError

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable."""


class SlowBody:
    """A response body that never finishes arriving."""

    async def read(self) -> bytes:
        await asyncio.sleep(3600)
        return b""


# --- 1. does the speak timeout cover the body read, not just the request? ----------------


async def test_timeout_covers_the_body_read(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Patch TIMEOUT_SPEAK down and hang inside read(). A working timeout still fires."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=b"x")
    client = DeepgramClient(async_get_clientsession(hass), "k")

    real_response_read = None

    async def hanging_read(self) -> bytes:  # noqa: ANN001
        await asyncio.sleep(3600)
        return b""

    with (
        patch("custom_components.deepgram_tts.api.TIMEOUT_SPEAK", 0.15),
        patch(
            "pytest_homeassistant_custom_component.test_util.aiohttp.AiohttpClientMockResponse.read",
            hanging_read,
        ),
    ):
        with pytest.raises(DeepgramConnectionError) as caught:
            await client.async_synthesize("hi", model=DEFAULT_VOICE)

    assert real_response_read is None
    print(f"\n  body read hung -> {type(caught.value).__name__}: {caught.value}")


async def test_catalog_timeout_covers_the_body_read(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, flux_models_payload: dict
) -> None:
    """Same question for the catalog, whose read is `await response.json()`."""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(URL_MODELS_AURA, json=flux_models_payload)

    async def hanging_json(self, **kwargs):  # noqa: ANN001, ANN003
        await asyncio.sleep(3600)

    with (
        patch("custom_components.deepgram_tts.catalog.TIMEOUT_CATALOG", 0.15),
        patch(
            "pytest_homeassistant_custom_component.test_util.aiohttp.AiohttpClientMockResponse.json",
            hanging_json,
        ),
    ):
        with pytest.raises(DeepgramConnectionError) as caught:
            await async_fetch_catalog(async_get_clientsession(hass))

    print(f"\n  catalog json() hung -> {type(caught.value).__name__}: {caught.value}")


# --- 2. what escapes when a catalog body is not valid JSON? ------------------------------


async def test_malformed_catalog_json_error_type(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, flux_models_payload: dict
) -> None:
    """A truncated JSON body with a JSON content type. What type reaches the caller?"""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(
        URL_MODELS_AURA,
        text='{"tts": [{"canonical_name": "aura-2-x-en"',
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(BaseException) as caught:  # noqa: PT011
        await async_fetch_catalog(async_get_clientsession(hass))

    print(f"\n  truncated catalog JSON -> {type(caught.value).__name__}: {caught.value}")
    print(f"  is DeepgramConnectionError? {isinstance(caught.value, DeepgramConnectionError)}")


async def test_malformed_catalog_json_sets_entry_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, flux_models_payload: dict
) -> None:
    """The consequence: SETUP_RETRY (transient, retried) or SETUP_ERROR (dead, no retry)?"""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(
        URL_MODELS_AURA,
        text='{"tts": [{"canonical_name": "aura-2-x-en"',
        headers={"Content-Type": "application/json"},
    )

    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "k"}, options={"voice": DEFAULT_VOICE})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    print(f"\n  entry state after a truncated catalog body: {entry.state}")
    assert entry.state in (ConfigEntryState.SETUP_ERROR, ConfigEntryState.SETUP_RETRY)


async def test_catalog_http_500_message_text(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, flux_models_payload: dict
) -> None:
    """A 5xx is a server rejection, not unreachability. What does the message say?"""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(URL_MODELS_AURA, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    with pytest.raises(DeepgramConnectionError) as caught:
        await async_fetch_catalog(async_get_clientsession(hass))

    print(f"\n  catalog HTTP 500 -> {caught.value}")


async def test_catalog_401_reads_as_a_connection_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, flux_models_payload: dict
) -> None:
    """If a corporate proxy or a Deepgram change ever puts auth on /models."""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(
        URL_MODELS_AURA, status=401, json={"err_code": "INVALID_AUTH", "err_msg": "no"}
    )

    with pytest.raises(DeepgramConnectionError) as caught:
        await async_fetch_catalog(async_get_clientsession(hass))

    print(f"\n  catalog HTTP 401 -> {type(caught.value).__name__}: {caught.value}")


# --- 3. the sample-rate self check arithmetic, independent of the client ------------------


def test_sample_rate_arithmetic_by_hand() -> None:
    """Verify bytes_per_ms independently: 24 kHz, mono, 16 bit is 48 bytes per millisecond."""
    from custom_components.deepgram_tts.const import (
        WS_BITS_PER_SAMPLE,
        WS_CHANNELS,
        WS_SAMPLE_RATE,
    )

    by_hand = WS_SAMPLE_RATE * WS_CHANNELS * (WS_BITS_PER_SAMPLE // 8) / 1000
    in_code = WS_SAMPLE_RATE * WS_CHANNELS * WS_BITS_PER_SAMPLE / 8 / 1000
    print(f"\n  by hand {by_hand} bytes/ms, in code {in_code} bytes/ms")
    assert by_hand == in_code == 48.0

    # What ratios does the 0.9 to 1.1 window actually admit or reject?
    rows = []
    for real_rate in (8000, 12000, 16000, 22050, 24000, 24100, 26000, 32000, 44100, 48000):
        ratio = real_rate / WS_SAMPLE_RATE
        caught = not (0.9 <= ratio <= 1.1)
        rows.append((real_rate, round(ratio, 3), "warns" if caught else "SILENT"))
    for rate, ratio, verdict in rows:
        print(f"  real stream {rate:>6} Hz  ratio {ratio:<6} {verdict}")

    # Rounding: how short must a clip be before integer-ms rounding alone trips the window?
    for duration_ms in (1, 2, 5, 10, 20, 100):
        exact_bytes = duration_ms * 48
        # Server rounds a true duration of duration_ms + 0.49 down to duration_ms.
        worst = (duration_ms + 0.4999) * 48
        ratio = worst / exact_bytes
        print(
            f"  clip {duration_ms:>4} ms  worst-case rounding ratio {ratio:.3f}  "
            f"{'trips the window' if not 0.9 <= ratio <= 1.1 else 'inside the window'}"
        )


def test_sample_rate_check_skips_zero_and_crashes_on_a_string() -> None:
    """Directly, without a socket."""
    from custom_components.deepgram_tts.stream import FluxSocket

    socket = FluxSocket.__new__(FluxSocket)
    socket._sample_rate = 24000  # noqa: SLF001
    from custom_components.deepgram_tts.stream import StreamMetrics

    socket.metrics = StreamMetrics(audio_bytes=96000, audio_duration_ms=0)
    socket._check_sample_rate()  # noqa: SLF001
    print(f"\n  duration 0 with 96000 bytes -> warnings={socket.metrics.warnings}")
    assert socket.metrics.warnings == []

    socket.metrics = StreamMetrics(audio_bytes=480, audio_duration_ms="10")
    with pytest.raises(TypeError) as caught:
        socket._check_sample_rate()  # noqa: SLF001
    print(f'  duration "10" (string) -> {type(caught.value).__name__}: {caught.value}')

    socket.metrics = StreamMetrics(audio_bytes=480, audio_duration_ms=-10)
    socket._check_sample_rate()  # noqa: SLF001
    print(f"  duration -10 -> warnings={socket.metrics.warnings}")


def test_wav_header_matches_a_stdlib_wave_reader() -> None:
    """An independent oracle: does Python's own wave module read our header the way we mean it?"""
    import io
    import wave

    from custom_components.deepgram_tts.stream import wav_header

    payload = wav_header(24000) + b"\x00\x01" * 480
    with wave.open(io.BytesIO(payload), "rb") as reader:
        print(
            f"\n  wave module reads: rate={reader.getframerate()} "
            f"channels={reader.getnchannels()} sampwidth={reader.getsampwidth()} "
            f"nframes={reader.getnframes()}"
        )
        assert reader.getframerate() == 24000
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2
        frames = reader.readframes(reader.getnframes())
    print(f"  frames actually readable: {len(frames)} bytes of the 960 written")
