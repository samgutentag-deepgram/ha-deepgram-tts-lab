"""Chapter 2's stop condition: the right endpoint, typed failures, and untouched bytes."""

from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.api import DeepgramClient
from custom_components.deepgram_tts.const import (
    DEFAULT_VOICE,
    URL_SPEAK_AURA,
    URL_SPEAK_FLUX,
)
from custom_components.deepgram_tts.errors import (
    DeepgramAuthError,
    DeepgramConnectionError,
    DeepgramRequestError,
)

AURA_VOICE = "aura-2-thalia-en"

# Deliberately not valid audio, and deliberately starting with an ID3 tag: the point of the
# round-trip test is that nothing in the client inspects or rewrites these bytes.
FAKE_AUDIO = b"ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90d\x00deadbeef\x00\x01\x02"


@pytest.fixture
async def client(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> DeepgramClient:
    # Async so the session is created on the running loop, and dependent on aioclient_mock so
    # the mock patch is installed before hass caches a session.
    return DeepgramClient(async_get_clientsession(hass), "test-key")


def last_call(aioclient_mock: AiohttpClientMocker):
    """Return (method, url, data, headers) for the most recent request."""
    return aioclient_mock.mock_calls[-1]


async def test_flux_model_posts_to_v2(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})

    result = await client.async_synthesize("Hello there.", model=DEFAULT_VOICE)

    method, url, data, headers = last_call(aioclient_mock)
    assert method.upper() == "POST"
    assert str(url).startswith(URL_SPEAK_FLUX)
    assert url.query["model"] == DEFAULT_VOICE
    assert data == {"text": "Hello there."}
    assert headers["Authorization"] == "Token test-key"
    assert headers["Content-Type"] == "application/json"
    assert result.extension == "mp3"
    assert result.content_type == "audio/mpeg"


async def test_aura_model_posts_to_v1(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_AURA, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})

    await client.async_synthesize("Hola.", model=AURA_VOICE)

    _, url, _, _ = last_call(aioclient_mock)
    assert str(url).startswith(URL_SPEAK_AURA)
    assert url.path == "/v1/speak"


async def test_audio_is_returned_byte_identical(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The regression test for re-encoding. What the API sent is what the caller gets."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})

    result = await client.async_synthesize("Hello there.", model=DEFAULT_VOICE)

    assert result.audio == FAKE_AUDIO
    assert len(result.audio) == len(FAKE_AUDIO)


async def test_speed_is_sent_for_flux(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO)

    await client.async_synthesize("Hello.", model=DEFAULT_VOICE, speed=1.15)

    _, url, _, _ = last_call(aioclient_mock)
    assert url.query["speed"] == "1.15"


async def test_speed_is_dropped_for_aura(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """v1/speak has no speed parameter and rejects unknown ones outright."""
    aioclient_mock.post(URL_SPEAK_AURA, content=FAKE_AUDIO)

    await client.async_synthesize("Hola.", model=AURA_VOICE, speed=1.15)

    _, url, _, _ = last_call(aioclient_mock)
    assert "speed" not in url.query


async def test_sample_rate_is_dropped_for_mp3(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The API rejects sample_rate with encoding=mp3 as not applicable."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO)

    await client.async_synthesize("Hello.", model=DEFAULT_VOICE, encoding="mp3", sample_rate=24000)

    _, url, _, _ = last_call(aioclient_mock)
    assert url.query["encoding"] == "mp3"
    assert "sample_rate" not in url.query


async def test_sample_rate_is_sent_for_linear16(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/wav"})

    result = await client.async_synthesize(
        "Hello.", model=DEFAULT_VOICE, encoding="linear16", container="wav", sample_rate=24000
    )

    _, url, _, _ = last_call(aioclient_mock)
    assert url.query["sample_rate"] == "24000"
    assert result.extension == "wav"


async def test_unset_options_are_absent_from_the_query(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only model is ever unconditional. Everything else is opt-in."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO)

    await client.async_synthesize("Hello.", model=DEFAULT_VOICE)

    _, url, _, _ = last_call(aioclient_mock)
    assert dict(url.query) == {"model": DEFAULT_VOICE}


async def test_extension_falls_back_to_requested_container(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unmapped Content-Type falls through to what was asked for, never to a guess."""
    aioclient_mock.post(
        URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "application/octet-stream"}
    )

    result = await client.async_synthesize(
        "Hello.", model=DEFAULT_VOICE, encoding="opus", container="ogg"
    )

    assert result.extension == "ogg"
    assert result.content_type == "application/octet-stream"


async def test_extension_defaults_to_mp3(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """No Content-Type and no requested format means the documented API default."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO)

    result = await client.async_synthesize("Hello.", model=DEFAULT_VOICE)

    assert result.extension == "mp3"


async def test_401_raises_auth_error(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Specifically DeepgramAuthError, so a caller can tell an expired key from a dead network."""
    aioclient_mock.post(
        URL_SPEAK_FLUX,
        status=401,
        json={"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials."},
    )

    with pytest.raises(DeepgramAuthError):
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)


async def test_403_raises_auth_error(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, status=403, text="Forbidden")

    with pytest.raises(DeepgramAuthError):
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)


async def test_400_carries_the_err_code(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The real rejection for posting an Aura model to the v2 endpoint."""
    aioclient_mock.post(
        URL_SPEAK_FLUX,
        status=400,
        json={
            "err_code": "V1_MODEL_ON_V2_SPEAK_ENDPOINT",
            "err_msg": "Only flux models are supported on the `/v2/speak` endpoint.",
        },
    )

    with pytest.raises(DeepgramRequestError) as caught:
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)

    assert caught.value.code == "V1_MODEL_ON_V2_SPEAK_ENDPOINT"
    assert caught.value.status == 400
    assert "Only flux models" in str(caught.value)


async def test_non_json_500_raises_request_error(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A proxy's HTML 502 page must not raise a second exception inside the error handler."""
    aioclient_mock.post(URL_SPEAK_FLUX, status=500, text="<html><body>oh dear</body></html>")

    with pytest.raises(DeepgramRequestError) as caught:
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)

    assert caught.value.status == 500
    assert caught.value.code is None
    assert "oh dear" in str(caught.value)


async def test_empty_error_body_is_survivable(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, status=503)

    with pytest.raises(DeepgramRequestError) as caught:
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)

    assert caught.value.status == 503


async def test_network_failure_raises_connection_error(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, exc=ClientConnectionError("no route to host"))

    with pytest.raises(DeepgramConnectionError):
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)


async def test_timeout_raises_connection_error(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, exc=TimeoutError())

    with pytest.raises(DeepgramConnectionError):
        await client.async_synthesize("Hello.", model=DEFAULT_VOICE)


async def test_verify_key_accepts_a_working_key(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})

    await client.async_verify_key()

    assert aioclient_mock.call_count == 1


async def test_verify_key_raises_auth_error_not_request_error(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The broad handler in async_verify_key must not swallow the typed auth failure."""
    aioclient_mock.post(URL_SPEAK_FLUX, status=401, text="Unauthorized")

    with pytest.raises(DeepgramAuthError):
        await client.async_verify_key()


async def test_verify_key_raises_connection_error_on_network_failure(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, exc=ClientConnectionError("dns is down"))

    with pytest.raises(DeepgramConnectionError):
        await client.async_verify_key()


async def test_verify_key_raises_request_error_otherwise(
    client: DeepgramClient, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, status=500, text="nope")

    with pytest.raises(DeepgramRequestError):
        await client.async_verify_key()
