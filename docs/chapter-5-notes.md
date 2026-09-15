# Chapter 5 notes: the TTS entity, batch path

Written 2026-09-15, while building `tts.py`. Notes an agent reads, so this stays markdown.

## What I chose

- **`async_stream_tts_audio` is absent, and there is no placeholder for chapter 6.** Not a stub,
  not a `NotImplementedError`, not a commented-out signature. `async_supports_streaming_input()`
  compares `self.__class__.async_stream_tts_audio` against the base method, so the method
  existing at all is the opt-in, and HA would route every Assist response down it while direct
  `tts.speak` calls kept working. `test_streaming_input_is_not_supported_yet` asserts both that
  the flag reads False and that `"async_stream_tts_audio" not in vars(DeepgramTTSEntity)`. It is
  **expected to fail when chapter 6 lands**, and the failure is the point: the flip from batch to
  socket should not be something a reviewer can miss. Chapter 6 deletes that test, in the same
  commit that adds the method and `stream.py`.
- **`_attr_name = entry.title`, not `_attr_has_entity_name = True` with a null name.** The
  chapter 1 placeholder used the modern shape, and it does produce the right entity id, but it
  leaves `entity.name` as `None` and the tts manager refuses to synthesize at all:
  `HomeAssistantError("TTS engine name is not set.")` out of `_async_generate_tts_audio`. Core's
  own `google_cloud` TTS entity sets `_attr_name = entry.title` for the same reason. `DeviceInfo`
  keeps `name=entry.title` too, so the device card is labeled.
- **The `_attr_` attributes rather than `@cached_property` overrides.** `supported_options`,
  `default_options`, `supported_languages`, and `default_language` are all in
  `CACHED_PROPERTIES_WITH_ATTR_` on the base class, so assigning `_attr_supported_options` in
  `__init__` is the sanctioned way to set them and does not reimplement the caching. Options
  changes reload the entry, so the cache cannot go stale.
- **`DEFAULT_LANGUAGE` is unioned into `supported_languages`.** `catalog.supported_languages`
  is the source, but `default_language` has to be a member of the list or HA's `process_options`
  rejects every call. With an empty catalog that would surface as `Language 'en' not supported`
  instead of a Deepgram error naming the real cause.
- **`PREFERRED_FORMAT_PARAMS` lives in `const.py`, and it is short.** HA's `preferred_format` is
  one string (a file extension); Deepgram splits the same idea across `encoding` and `container`.
  `wav` becomes `linear16` plus `container=wav`, `ogg` becomes `opus` plus `container=ogg`, and
  `mp3`, `flac`, `aac` are encodings on their own. Anything not in the map asks for nothing and
  lets HA convert, because `/v2/speak` rejects an unknown encoding outright with
  `INVALID_QUERY_PARAMETER`: a guess costs a failed synthesis, a fallback costs one ffmpeg pass.
- **`resolve_voice` is the only gate on settled decision 4.** The entity passes the per-call
  voice, then the entry's voice, then `DEFAULT_VOICE` as `preferred` and uses whatever comes
  back as the model. It never overrides the answer afterwards. A second language check in the
  entity would be a duplicate of the one in `catalog.py`, and duplicated invariants drift.
- **`speed` is gated on `voice.is_flux`, not on the configured voice.** A per-call `voice`
  option can switch family mid-call, so the gate has to read the resolved voice. `api.py` drops
  it again for Aura, which is belt and braces on purpose.
- **A language nobody can speak raises `DeepgramError`, the base class, not a fifth error type.**
  It is not an auth failure, not a connection failure, and not an API rejection, and the
  interface contract says not to add a fifth error without a reason. The message names the
  language.

## Divergence from the interface contract

The contract says `supported_options` is
`[ATTR_VOICE, ATTR_AUDIO_OUTPUT, ATTR_PREFERRED_FORMAT, CONF_SPEED]`. **`ATTR_AUDIO_OUTPUT` is
not advertised.** It is a per-integration free-form option, not part of HA's format machinery:
it is absent from `_PREFFERED_FORMAT_OPTIONS`, `_async_generate_tts_audio` never reads it, and
the only two core consumers give it incompatible meanings (`cloud` uses `mp3`/`raw` and puts it
in `default_options`, `wyoming` advertises it and ignores it). Advertising it without honoring it
lets a caller pass an option that silently does nothing. Honoring it as a second format knob puts
it in a fight with `preferred_format`: HA compares the returned extension against
`preferred_format` only, so `audio_output: wav` with no `preferred_format` would produce WAV and
then transcode it straight back to MP3. The three options the chapter 5 brief requires are
advertised: `voice`, `preferred_format`, and `speed`.

## HANDOFF section 4.3 versus the installed component

Section 4.3 is correct on everything it lists, and incomplete. Read out of
`.venv/lib/python3.14/site-packages/homeassistant/components/tts/__init__.py`, HA 2026.9.2:

| Constant | In 4.3 | Installed |
| --- | --- | --- |
| `ATTR_VOICE = "voice"` | yes | same |
| `ATTR_PREFERRED_FORMAT = "preferred_format"` | yes | same |
| `ATTR_PREFERRED_SAMPLE_RATE = "preferred_sample_rate"` | yes | same |
| `_DEFAULT_FORMAT = "mp3"` | yes | same |
| `ATTR_AUDIO_OUTPUT = "audio_output"` | no | present, exported in `__all__` |
| `ATTR_PREFERRED_SAMPLE_CHANNELS = "preferred_sample_channels"` | no | present |
| `ATTR_PREFERRED_SAMPLE_BYTES = "preferred_sample_bytes"` | no | present |
| `ATTR_PREFERRED_BITRATE = "preferred_bitrate"` | no | present |
| `ATTR_MEDIA_PLAYER_ENTITY_ID`, `ATTR_PLATFORM`, `CONF_LANG` | no | present |

Two behaviors worth writing down because they decide how the entity is built:

1. `_PREFFERED_FORMAT_OPTIONS` is the set of five `preferred_*` options that HA treats as hints.
   They bypass the `supported_options` validation entirely, so any caller can send them whether
   the entity advertises them or not. Advertising one only changes whether it is left in
   `options` for the entity to act on, or popped and applied by ffmpeg afterwards.
2. `async_get_tts_audio(self, message, language, options)` takes `options` as a required
   positional `dict[str, Any]`, not `dict | None = None`. The chapter 1 placeholder had the
   optional shape; chapter 5 matches the base class.

## What surprised me

1. **The modern entity-naming shape breaks TTS.** `_attr_has_entity_name = True` with
   `_attr_name = None` is what HA's own docs push, and it gave exactly the entity ids chapter 1
   asserted, and then every synthesis failed with "TTS engine name is not set." The entity id and
   `entity.name` come from different places, so the naming looked right in the registry while the
   service was dead. That failure mode is very close in shape to the one in section 2.1: a real
   defect that only the pipeline surfaces.
2. **Going through `async_get_media_source_audio` runs real ffmpeg.** Any test that asks for a
   `preferred_format` the entity cannot produce natively triggers `_async_convert_audio`, which
   shells out to the ffmpeg binary and fails on fake audio with "Failed to find two consecutive
   MPEG audio frames." So the unmapped-format test calls the entity directly and the WAV test
   asserts that no conversion was needed. It also proves the conversion path is live on this
   machine, which is worth knowing.
3. **The tts manager caches in memory on message, language, options, and engine.** Two calls with
   the same message in one test replay the first result and never reach the entity, so the API
   assertion passes against a stale call. Every test here passes `cache=False` and a distinct
   message.
4. **`tts.speak` never synthesizes anything.** It hands the media player a
   `media-source://tts/...` URL and returns. Audio is only produced when something fetches the
   stream. The round-trip test therefore calls the service, captures the
   `media_player.play_media` call, and then fetches the id it was given. On real hardware that
   means a silent speaker is not evidence that synthesis failed.

## The chapter 5 hardware gate

There is **no `DEEPGRAM_API_KEY` on this machine and no Home Assistant instance**, so everything
authenticated is mocked. Nothing below has been observed against the real API or on real
hardware. HANDOFF section 6 says chapter 5 has to run on the real instance before chapter 6
starts, and this is that checklist.

Paste each block into Developer Tools, Actions, in YAML mode. Swap
`media_player.office_speaker` for a real speaker, and the `tts.` entity ids for whatever the
config flow titled the entries.

### 1. `flux-haley-en` is the default on a fresh install

Unverified: that a default-voice synthesis authenticates, returns playable audio, and that the
audio is the Haley voice rather than whatever `/v2/speak` falls back to.

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_flux_haley
data:
  media_player_entity_id: media_player.office_speaker
  message: Chapter five is on the instance, and this is the default voice.
  cache: false
```

Pass: audio plays, and the Deepgram console request log shows `model=flux-haley-en`. Enable
`logger` at debug for `custom_components.deepgram_tts` to see the resolved model locally.

### 2. A non-English pipeline resolves an Aura voice

Unverified for every one of the six languages: that the Aura voice `resolve_voice` picks actually
synthesizes on `/v1/speak`, and that the audio is in the right language. Run all six; the entry
is configured with a Flux voice on purpose, so each one exercises the rejection.

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_flux_haley
data:
  media_player_entity_id: media_player.office_speaker
  message: Tu cita esta confirmada para las tres de la tarde.
  language: es
  cache: false
```

Then repeat with `language: de` / `fr` / `nl` / `it` / `ja` and a phrase in that language. Pass:
audio plays in the requested language, and no request in the Deepgram log for these six carries a
`flux-` model.

### 3. A per-call voice option overrides the entry

Unverified: that an arbitrary catalog voice id, not just the configured one, is accepted by the
API. The mocks accept any model string.

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_flux_haley
data:
  media_player_entity_id: media_player.office_speaker
  message: This should not be Haley.
  options:
    voice: flux-wes-en
  cache: false
```

Pass: audibly a different voice, and the log shows `model=flux-wes-en`.

### 4. Speed is applied for Flux and rejected for nothing

Unverified: that `/v2/speak` accepts the speed values the options flow can produce, and that the
0.05-increment rule in HANDOFF 3.4 is enforced the way the probe suggested.

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_flux_haley
data:
  media_player_entity_id: media_player.office_speaker
  message: This sentence should be noticeably faster than the last one.
  options:
    speed: 1.4
  cache: false
```

Pass: audibly faster, no error. Then try `speed: 1.37` and record whether the API rejects a value
off the increment grid or rounds it, because the options flow's slider step depends on the answer.

### 5. Speed is meaningless for Aura and must not break the call

Unverified: that dropping the parameter is sufficient, rather than `/v1/speak` needing something
else.

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_aura_celeste
  # or the Flux entry with language: es
data:
  media_player_entity_id: media_player.office_speaker
  message: Esto no deberia cambiar de velocidad.
  language: es
  options:
    speed: 1.4
  cache: false
```

Pass: audio plays at normal speed and no request carries `speed`.

### 6. WAV comes back as WAV, with no ffmpeg pass

Unverified: that `encoding=linear16` with `container=wav` really returns `audio/wav`, which is
what keeps HA's converter out of the loop on the Pi. Also unverified, from chapter 2 notes item
3: whether `audio/basic` and `audio/l16` responses are usable at all.

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_flux_haley
data:
  media_player_entity_id: media_player.office_speaker
  message: This one should arrive as a wav and never touch ffmpeg.
  options:
    preferred_format: wav
  cache: false
```

Pass: audio plays, and the HA log shows no `_async_convert_audio` / ffmpeg invocation for this
call. Repeat with `preferred_format: mp3` and `preferred_format: flac`.

### 7. An expired or wrong key reads as an auth failure

Unverified: what a real 401 body looks like, and therefore what the user sees. Chapter 2 notes
item 4 is the same gap.

Add a second config entry with a deliberately wrong key, then:

```yaml
action: tts.speak
target:
  entity_id: tts.deepgram_flux_haley_2
data:
  media_player_entity_id: media_player.office_speaker
  message: This should fail as an auth error.
  cache: false
```

Pass: the log names an API key rejection, not a timeout and not a generic failure.

### 8. The voice list renders with usable labels

Unverified: that the 61 Aura voices whose `metadata.display_name` is null read acceptably as
title-cased bare names in the real Assist voice dropdown, and that 138 entries in one select is
usable at all. Chapter 3 notes item 3.

No YAML. Settings, Voice assistants, pick the Deepgram engine, and open the voice dropdown for
`en` and for `es`. Pass: no blank labels, no raw model ids, Flux reads before Aura.

### 9. Two entries coexist with distinguishable entity ids

Unverified on a real instance: that the config flow's titles slugify to distinct entity ids. The
tests assert `tts.deepgram_flux_haley` and `tts.deepgram_aura_celeste` against hand-built titles.

No YAML. Add a Flux entry and an Aura entry and read Developer Tools, States, filtered to `tts.`.
Pass: two entities, both named after their voice, neither suffixed `_2`.

### 10. Latency and the legacy voices

Unverified and both worth a number rather than a pass: how long a short `tts.speak` takes end to
end on the Pi (HANDOFF section 7 item 2 is about the socket, but the batch number is the baseline
chapter 6 has to beat), and whether the 12 legacy `aura-*` models in the merged catalog still
synthesize at all (chapter 3 notes item 2). For the second, run check 3 with
`voice: aura-asteria-en`.

## Still unverified after this chapter

1. **Everything in the gate above.** No key, no instance.
2. **Whether `container=none` ever reaches the entity.** `PREFERRED_FORMAT_PARAMS` never sends
   it, so `api.py`'s `CONTAINER_NONE` branch is only reachable from chapter 6 or a direct client
   call.
3. **`sample_rate` is never sent from the entity.** `ATTR_PREFERRED_SAMPLE_RATE` is not
   advertised, so HA pops it and resamples with ffmpeg. That is one transcode a voice satellite
   asking for 16 kHz will pay. Passing it through to `/v2/speak` would avoid it, but only for
   encodings where the API accepts it, and chapter 2 notes item 2 says we do not yet know which.
   Worth revisiting once there is a key.
4. **Nothing here tests the Assist pipeline.** Chapter 5 is `tts.speak` and the media source.
   The pipeline path only becomes interesting in chapter 6, which is exactly why the streaming
   guard test exists.
