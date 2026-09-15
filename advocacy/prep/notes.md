# notes.md, the fact sheet

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> `advocacy/advocacy.md` is unwritten, no claim is frozen, and `advocacy-intake` has not run.
> Per HANDOFF section 8.5, intake waits until chapter 5 runs on real Home Assistant hardware.
> Nothing here is cleared to publish. This is staging material for a campaign that has not
> started.

Written 2026-09-15 in `advocacy/prep/`. Structured by theme, not by chronology, because the
cycle projects sections out of it and a section needs one theme's facts together.

## How to read a fact here

Every fact carries a status tag. The tags are the point of the file, and collapsing them is how
a post stops surviving a skeptical reader.

| Tag | Means |
| --- | --- |
| `LIVE` | A command was run on 2026-09-15 and its output is quoted or summarized here |
| `SOURCE` | Verified by reading source on disk, cited as `path:line-range` |
| `VENDOR` | Deepgram or Home Assistant says so and nobody here has tested it |
| `INFERRED` | Reasoning over other facts in this file. The reasoning is stated so it can be attacked |

Two paths appear over and over and are abbreviated:

- `FORK/` is `/Users/samgutentag/Developer/ha-deepgram-tts/custom_components/deepgram_tts/`,
  the audited fork of `alceasan/ha-deepgram-tts` at `ba59415`.
- `HAPKG/` is `.venv/lib/python3.14/site-packages/homeassistant/`, Home Assistant 2026.9.2
  installed in this repo's test venv on Python 3.14.7.

`alceasan/ha-deepgram-tts` is prior art and gets credited by name anywhere its defects are
discussed. Every finding below is a transferable lesson about writing a Home Assistant TTS
entity, which is the only reason to write any of them down.

---

## Theme 1: undeclared dependencies, and why the load-failure story is weaker than the audit said

This is the theme where the campaign is most likely to publish something false, so it goes
first.

**F1.1** `LIVE` The integration imports `async_timeout` in two modules and calls it three
times, while its manifest declares no requirements.

```
FORK/api_models.py:4       import async_timeout
FORK/api_models.py:12          async with async_timeout.timeout(10):
FORK/api.py:9              import async_timeout
FORK/api.py:84                 async with async_timeout.timeout(10):
FORK/api.py:118                async with async_timeout.timeout(30):
```

**F1.2** `SOURCE` `FORK/manifest.json` declares `"requirements": []` and
`"dependencies": []`, so Home Assistant installs nothing on its behalf. Same file:
`"iot_class": "cloud_push"`, `"version": "1.0.2"`, codeowner `@alceasan`.

**F1.3** `LIVE` `pydub` is imported behind an optional guard and the failure is deferred to
call time.

```
FORK/stream_processor.py:10        from pydub import AudioSegment
FORK/stream_processor.py:12        AudioSegment = None
FORK/stream_processor.py:149-150   if not AudioSegment:
                                       raise RuntimeError("pydub is not available to join mp3 fragments")
```

**F1.4** `LIVE` Nothing in a working Home Assistant 2026.9.2 environment requires `pydub`,
and it is not in HA's constraints file. Two checks over the installed environment:

```
$ .venv/bin/python -c "import pydub"
ModuleNotFoundError
pydub requirers across all installed distributions: NONE
$ grep -i pydub HAPKG/package_constraints.txt
(no match)
```

So the pydub failure is real and reproducible. `F1.3` plus `F1.4` is the whole story: the
streaming path raises on every call because the package it needs is never installed.

**F1.5** `LIVE` **`async_timeout` is a different story, and the audit got this one wrong.**
`async-timeout` is importable in a real HA 2026.9.2 environment, and the dependency chain that
puts it there runs through the TTS component itself:

```
HAPKG/components/tts/manifest.json      "dependencies": ["http", "ffmpeg"]
HAPKG/components/ffmpeg/manifest.json   "requirements": ["ha-ffmpeg==3.2.2"]
ha-ffmpeg 3.2.2 metadata                Requires-Dist: async-timeout      <- no environment marker
HAPKG/package_constraints.txt:213       async-timeout==4.0.3
$ .venv/bin/python -c "import async_timeout"   -> succeeds, version 5.0.1
```

Every other package in the environment that wants `async-timeout` marks it
`python_version < "3.11"` and therefore contributes nothing on Python 3.14 (verified for
`aiohttp`, `bleak`, `bluetooth-adapters`, `bleak-retry-connector`,
`bluetooth-auto-recovery`). `ha-ffmpeg` is the one with no marker, and it is pulled in by the
`tts` component, which any TTS integration loads by definition.

**F1.6** `INFERRED` from `F1.5`: the claim that the fork "almost certainly did not load at
all" is not supportable. A TTS integration runs inside a Home Assistant that has already
installed `ha-ffmpeg`, so `import async_timeout` most likely resolves. The honest version is
that the import is undeclared and its availability is an accident of somebody else's
dependency graph, which can change in any release without warning. **Do not publish the
two-line load failure as a fact.**

**F1.7** `LIVE` `aiohttp` in HA 2026.9.2 is `3.14.3`, and `homeassistant`'s own distribution
metadata requires `aiohttp==3.14.3`, `aiohttp_cors`, `aiohttp-fast-zlib`, and
`aiohttp-asyncmdnsresolver`. No direct `async-timeout` requirement.

**F1.8** `VENDOR` aiohttp dropped `async_timeout` as a hard dependency at 3.10.
`asyncio.timeout()` has been in the standard library since Python 3.11, so on HA's Python 3.14
the third-party package buys nothing. Carried from the audit, not retested here.

**F1.9** `SOURCE` This project's own manifest declares `"requirements": []` and that is true
of it: `custom_components/deepgram_tts/manifest.json:10`, with nothing outside the standard
library and what HA ships. `scripts/manifest_check.py` fails CI if that drifts, which is the
mechanical answer to `F1.1`.

---

## Theme 2: the streaming opt-in is the method signature, and there is no flag

**F2.1** `SOURCE` Home Assistant decides whether a TTS entity supports streaming input by
comparing the subclass method against the base class method.

```python
# HAPKG/components/tts/entity.py:93-98
def async_supports_streaming_input(self) -> bool:
    """Return if the TTS engine supports streaming input."""
    return (
        self.__class__.async_stream_tts_audio
        is not TextToSpeechEntity.async_stream_tts_audio
    )
```

**F2.2** `INFERRED` from `F2.1`: defining `async_stream_tts_audio` **is** the opt-in. There is
no config key, no manifest flag, and no feature bit. A half-finished streaming path goes live
for every Assist pipeline response the moment the method exists on the class.

**F2.3** `INFERRED` from `F2.1`, `F1.3`, `F1.4`: this is what produces the fork's signature
failure shape. Direct `tts.speak` calls take `async_get_tts_audio` and work. Assist pipeline
responses take `async_stream_tts_audio` and raise on the missing pydub. Same integration,
same voice, same key, two outcomes depending on which caller asks.

**F2.4** `SOURCE` The streaming contract is two dataclasses, and both are small:

```python
# HAPKG/components/tts/entity.py:37-42
@dataclass
class TTSAudioRequest:
    language: str
    options: dict[str, Any]
    message_gen: AsyncGenerator[str]

# HAPKG/components/tts/entity.py:45-50
@dataclass
class TTSAudioResponse:
    extension: str
    data_gen: AsyncGenerator[bytes]
```

**F2.5** `LIVE` The fork's streaming path collects the whole generator into one string before
yielding anything:

```python
# FORK/tts.py:165-171
async def message_gen() -> AsyncGenerator[str, None]:
    texto = ""
    if hasattr(request, "message_gen") and request.message_gen is not None:
        async for chunk in request.message_gen:
            texto += chunk
    _LOGGER.debug("Text reconstructed from request.message_gen: ...")
    yield texto
```

**F2.6** `INFERRED` from `F2.5`: an implementation that buffers `message_gen` to completion
has the streaming API's call signature and none of its behavior. Nothing starts synthesizing
until the language model has stopped talking.

---

## Theme 3: the server places the flush boundaries, so sentence splitting is the wrong idea

**F3.1** `VENDOR` The Flux TTS websocket at `wss://api.deepgram.com/v2/speak` takes `Speak`,
`Flush`, `Interrupt`, `Configure`, and `Close` from the client, and emits `Connected`,
`SpeechStarted`, `SpeechMetadata`, `SpeechInterrupted`, `Flushed`, `SessionMetadata`,
`ConfigureSuccess`, `ConfigureFailure`, `Warning`, and `Error`. Every audio frame for a turn
arrives between `SpeechStarted` and `SpeechMetadata`. Recorded in HANDOFF section 3.5.
**Untested. No socket has been opened, because there is no API key on this machine (`F11.1`).**

**F3.2** `VENDOR` The server decides where flush boundaries fall, so a client streams language
model tokens straight in and does no sentence segmentation. HANDOFF section 3.5 calls this the
single most important fact in that document. **Untested for the same reason.**

**F3.3** `LIVE` The fork does segment sentences, and the segmentation code is the largest
single file in it. `FORK/stream_processor.py` is 206 lines (`wc -l`), holding
`_find_sentence` at line 35 and a growth threshold at line 80:

```python
# FORK/stream_processor.py:80
min_len = 2 ** count * 10  # Exponential buffer growth for optimal streaming
```

**F3.4** `INFERRED` from `F3.3`: `count` increments once per input chunk, so the buffer
threshold doubles per chunk. At chunk 20 it is over 10 MB of text before a synthesis call
fires. It is inert in the fork only because `F2.5` yields exactly one chunk, which is the
second bug hiding the first.

**F3.5** `LIVE` Three more costs in that same file, each verified by line:
`SYNTHESIS_DELAY_S = 0.15` at line 18 and slept at line 186, before every synthesis call.
`TRIM_MS_FROM_END = 0` at line 17, which makes the trim helper at 114-122 unreachable by its
own constant. `_strip_id3` defined at line 134 and never called.

**F3.6** `INFERRED` from `F3.1` and `F3.2`, if they hold: a client that follows the protocol
has no sentence regex, no per-sentence round trips, and no fragment stitching, so the whole
206 lines of `F3.3` has no counterpart in this build. That is the design bet, and it is
currently a bet, not a result.

---

## Theme 4: 36 Flux voices, all English, which is the one real regression

**F4.1** `LIVE` `GET https://api.deepgram.com/v2/models` returns HTTP 200 with no
`Authorization` header, and its `tts` array holds exactly **36** entries. Every one has
`architecture: "flux-tts"`.

**F4.2** `LIVE` The language set across all 36 is English only: `en`, `en-AU`, `en-GB`,
`en-IE`, `en-IN`, `en-PH`, `en-SG`, `en-US`. Full id list, from the same response:

```
flux-alexis-en    flux-bree-en      flux-brittany-en  flux-brooke-en
flux-bruce-en     flux-cliff-en     flux-cole-en      flux-colin-en
flux-conor-en     flux-donovan-en   flux-drew-en      flux-elise-en
flux-gemma-en     flux-haley-en     flux-hannah-en    flux-heather-en
flux-jack-en      flux-kai-en       flux-kelsey-en    flux-kit-en
flux-maeve-en     flux-marcelo-en   flux-marcus-en    flux-meena-en
flux-meghan-en    flux-miles-en     flux-naveen-en    flux-paige-en
flux-priya-en     flux-rufus-en     flux-sean-en      flux-sharon-en
flux-sienna-en    flux-tanner-en    flux-wade-en      flux-wes-en
```

**F4.3** `LIVE` `GET https://api.deepgram.com/v1/models` returns HTTP 200 unauthenticated with
**102** TTS models: 90 `aura-2` and 12 legacy `aura`. Its languages are `de`, `de-DE`, `en`,
`en-AU`, `en-GB`, `en-IE`, `en-PH`, `en-US`, `es`, `es-419`, `es-AR`, `es-CO`, `es-ES`,
`es-MX`, `fr`, `fr-FR`, `it`, `it-IT`, `ja`, `ja-JP`, `nl`, `nl-NL`. **Zero** entries whose
`canonical_name` starts with `flux`.

**F4.4** `INFERRED` from `F4.2` and `F4.3`: seven base languages exist across both families
(`en`, `de`, `es`, `fr`, `it`, `ja`, `nl`) and exactly one of them can be served by Flux. A
Flux-only integration collapses `supported_languages` to `["en"]` and takes the voice away
from every non-English Assist pipeline. That is why both families ship and why routing is by
model prefix.

**F4.5** `INFERRED` from `F4.3`: the fork's dynamic voice discovery reads `/v1/models` only
(`FORK/api_models.py:9`, noted in the audit), so no Flux voice could ever appear in its
picker. Not a bug in its logic. It is looking in a catalog that does not contain them.

**F4.6** `LIVE` One catalog entry, verbatim from today's response, because the shape drives
the config flow:

```json
{"name": "haley", "canonical_name": "flux-haley-en", "architecture": "flux-tts",
 "languages": ["en", "en-US"], "version": "2026-08-12.0",
 "uuid": "98bee083-eeff-4d22-9f09-e5b522873d44",
 "metadata": {"accent": "American", "age": "Young Adult", "display_name": "Haley",
   "tags": ["feminine","clear","professional","caring","calm","empathetic"],
   "use_cases": ["Customer Service","Financial Services","IVR"],
   "sample": "https://cdn.sanity.io/files/0dsbfl6j/production/79d681...wav"}}
```

`metadata.display_name` is the presentable label. `name` is a bare lowercase given name, which
is what the fork shows users (`FORK/config_flow.py:132`). `metadata.sample` is a playable WAV,
which is raw material for a voice picker later.

**F4.7** `SOURCE` This build's default is `flux-haley-en`, set at
`custom_components/deepgram_tts/const.py:19`, chosen for the metadata in `F4.6` and because it
is the voice the Deepgram quickstart uses.

**F4.8** All 36 voices are cleared for public use, `flux-marcus-en` and `flux-brittany-en`
included. Settled, not a question, and not a topic for any piece of content.

**F4.9** `VENDOR` `flux-marcus-en` and `flux-brittany-en` drift in pitch and volume between
calls, sometimes emit an audible musical note before a greeting, and can click at clip starts
(HANDOFF section 5.1). A home assistant makes many short separate calls, which is where that
drift is most audible, so neither is a good *shipped default*. This is engineering advice about
picking a default and it gets **one** mention, in the voice-picker context, framed that way.

---

## Theme 5: two endpoint families that do not mix

**F5.1** `LIVE` Posting an Aura model to the v2 endpoint is rejected before auth is checked. A
dummy key still gets a real answer:

```
$ curl -X POST "https://api.deepgram.com/v2/speak?model=aura-2-thalia-en" \
    -H "Authorization: Token 0000...0000" -H "Content-Type: application/json" \
    -d '{"text":"hello"}'
HTTP 400
{"err_code":"V1_MODEL_ON_V2_SPEAK_ENDPOINT",
 "err_msg":"Only flux models are supported on the `/v2/speak` endpoint. Please use the
            `/v1/speak` endpoint for Aura text-to-speech requests."}
```

**F5.2** `SOURCE` The endpoints, as this build has them in
`custom_components/deepgram_tts/const.py:23-30`: `https://api.deepgram.com/v2/speak` for Flux
batch, `wss://api.deepgram.com/v2/speak` for Flux streaming,
`https://api.deepgram.com/v1/speak` for Aura batch, plus the two model catalogs.

**F5.3** `INFERRED` from `F5.1`: the model id is the only routing signal the API offers, so
the client picks the URL from the prefix. One synthesize signature, two URLs. Implemented as
`family_for_model` at `custom_components/deepgram_tts/models.py:61-63`.

**F5.4** Barge-in is out of scope and the reason is a Home Assistant limit rather than a
Deepgram one. `SpeechInterrupted` carries `text_spoken` and `text_remaining`, which is the
right primitive for it, and HA's TTS entity API has no barge-in hook today. HANDOFF section 5,
item 8. The `SpeechInterrupted` fields are `VENDOR` and untested along with the rest of
Theme 3; the absence of an HA hook is `SOURCE`, from the entity contract in `F2.4` having no
such method.

---

## Theme 6: the /v2/speak parameter surface, enumerated by being wrong on purpose

Query-parameter validation runs before auth on this endpoint, so an invalid value returns a
real schema error even with a dummy key. Every response below was collected on 2026-09-15.

**F6.1** `LIVE` Unknown parameters are rejected outright:

```
?model=flux-haley-en&nonsense=1
HTTP 400 INVALID_QUERY_PARAMETER
"Failed to deserialize query parameters: unknown field `nonsense`"
```

**F6.2** `LIVE` The encoding enum, quoted back by the server:

```
?encoding=flac16
HTTP 400 "unknown variant `flac16`, expected one of `linear16`, `mulaw`, `alaw`, `mp3`,
          `opus`, `flac`, `aac`"
```

**F6.3** `LIVE` The container enum, same method:

```
?container=mp4
HTTP 400 "unknown variant `mp4`, expected one of `wav`, `ogg`, `none`"
```

**F6.4** `LIVE` `sample_rate` and `mp3` are mutually exclusive:

```
?encoding=mp3&sample_rate=24000
HTTP 400 UNSUPPORTED_AUDIO_FORMAT "`sample_rate` is not applicable when `encoding=mp3`."
```

**F6.5** `LIVE` `bit_rate` is a fixed set when encoding is mp3, and the server names it:

```
?bit_rate=9
HTTP 400 UNSUPPORTED_AUDIO_FORMAT "`bit_rate` must be 8000, 16000, 24000, 32000, 40000,
          or 48000 when `encoding=mp3`."
```

**F6.6** `LIVE` `speed` is typed at parse time but **not range checked before auth**, which
means the published range is not something an unauthenticated probe can confirm:

```
?speed=abc   HTTP 400 "invalid type: string \"abc\", expected f32"
?speed=3.0   HTTP 401 INVALID_AUTH        <- out of range, not rejected here
?speed=1.07  HTTP 401 INVALID_AUTH        <- not a 0.05 step, not rejected here
```

**F6.7** `VENDOR` `speed` accepts 0.5 to 1.5 in 0.05 increments, per HANDOFF section 3.4 and
the Deepgram docs. **`F6.6` shows this specific bound was not verified by probing, contrary to
how HANDOFF presents it.** Treat the range as documentation until a real key tests the
boundaries. This build encodes it as constants at
`custom_components/deepgram_tts/const.py:38-41`, which is fine, and the comment on line 38
says "`/v2/speak` validates 0.5 to 1.5 in 0.05 increments", which overstates what anyone here
has seen the endpoint do. Worth correcting in the code comment at some point, and worth not
repeating in a blog post before then.

**F6.8** `VENDOR` Compressed and containerized encodings are batch only. The socket emits raw
`linear16`, `mulaw`, or `alaw`. HANDOFF section 3.4, untested.

**F6.9** `VENDOR` Flux TTS is $0.045 per 1,000 characters, per HANDOFF section 3.5 as of
2026-09-15. Cite the date with the number, every time.

---

## Theme 7: Home Assistant already does the audio work

**F7.1** `SOURCE` HA converts audio itself. `_async_convert_audio` at
`HAPKG/components/tts/__init__.py:315` shells out to ffmpeg whenever the requested format
differs from what the entity returned, or when a sample rate, channel count, byte width, or
bit rate was asked for.

**F7.2** `SOURCE` The option constants an entity advertises, from the same module:
`ATTR_PREFERRED_FORMAT = "preferred_format"` (line 99),
`ATTR_PREFERRED_SAMPLE_RATE = "preferred_sample_rate"` (line 100),
`ATTR_VOICE = "voice"` (line 105), `_DEFAULT_FORMAT = "mp3"` (line 107).

**F7.3** `INFERRED` from `F7.1`: returning whatever the API produced and letting HA transcode
is correct and costs nothing extra. Transcoding inside the integration is a second full
transcode.

**F7.4** `LIVE` The fork transcodes anyway. `FORK/stream_processor.py:164` decodes each MP3
fragment with pydub and re-exports it as MP3, once per sentence, which on a Raspberry Pi is
the expensive kind of nothing.

---

## Theme 8: the audit numbers

**F8.1** `LIVE` The fork's integration is **858** lines of Python, counted today:

```
$ wc -l FORK/*.py
  73 __init__.py    15 api_models.py   142 api.py       240 config_flow.py
   8 const.py      206 stream_processor.py            174 tts.py
 858 total
```

HANDOFF section 2 says "roughly 850 lines". 858 is the measured number and is the one to
quote.

**F8.2** `LIVE` `stream_processor.py` is **206** of those 858 lines, and it is the file the
websocket design deletes outright (`F3.6`).

**F8.3** `INFERRED` The "about 180 lines survive" figure in HANDOFF section 2 is an estimate
from the repair plan, not a diff. It is honest as an estimate and dishonest as a measurement.
If a post needs a number for how little carried over, use `F8.1` and `F8.2`, which are counted,
or say "about a fifth, by estimate" and attribute it to the plan.

**F8.4** `SOURCE` The three reasons the project restarted instead of forking, from HANDOFF
section 2, in the order HANDOFF weights them: almost nothing survives; the git history is
worth more than the code, because the lab convention wants a commit log that reads as build
order; and GitHub cannot make a fork private, so making a parent private detaches forks into a
new network rather than converting them.

**F8.5** `LIVE` Environment drift the fork carries, verified today:
`hacs.json` still asks for Home Assistant `2025.7.0` while current stable is 2026.9.x;
`requirements.txt` pins `pytest-homeassistant-custom-component==0.13.89` plus black and
flake8; `manifest.json` points its issue tracker at the upstream repo.

---

## Theme 9: what this project has actually built, as of 2026-09-15

**F9.1** `LIVE` Three commits exist. `git log --oneline`:

```
325d6d7 feat(scaffold): chapter 1, an integration that loads
21503ca docs: squash the session into a self-contained handoff and starter prompts
2aaf842 chore: seed the lab from the fork audit
```

**F9.2** `LIVE` Chapter 1 is **314** lines of component code across six modules
(`__init__.py` 80, `config_flow.py` 34, `const.py` 46, `errors.py` 31, `models.py` 63,
`tts.py` 60), plus 182 lines of tests.

**F9.3** `LIVE` The test suite passes: `.venv/bin/python -m pytest -q` reports
`6 passed in 0.17s` against Home Assistant 2026.9.2 on Python 3.14.7.

**F9.4** `SOURCE` The TTS entity is a placeholder and says so. `async_get_tts_audio` at
`custom_components/deepgram_tts/tts.py:54-60` raises `DeepgramRequestError` with the message
that chapter 5 wires it to `/v2/speak`. **There is no synthesis in this repo today.**

**F9.5** `SOURCE` `custom_components/deepgram_tts/models.py:41-47` splits language codes on
`"-"` and the docstring records why: Deepgram uses hyphens, so splitting on an underscore is a
no-op that leaves `en` and `en-US` both in the list.

**F9.6** `LIVE` The fork splits on underscore in five places, which is the defect `F9.5`
answers: `FORK/tts.py:74`, `FORK/tts.py:101`, `FORK/config_flow.py:178`,
`FORK/config_flow.py:189`, `FORK/config_flow.py:212`.

**F9.7** `LIVE` The fork claims single instance with a constant, at
`FORK/config_flow.py:87`: `await self.async_set_unique_id("deepgram_tts")`. This build sets no
constant unique id and leaves `single_config_entry` out of the manifest, so a Flux entity and
an Aura entity can coexist.

**F9.8** `SOURCE` The build order is seven chapters (HANDOFF section 6): scaffold, API client,
voice catalog, config flow, batch TTS entity, streaming TTS entity, harden. Chapter 5 must run
on real hardware before chapter 6 starts. Chapters 2 through 6 are in progress in parallel
worktrees as of today and **none of it has run on Home Assistant hardware**.

---

## Theme 10: dead weight worth naming once, because it is a category not a list

**F10.1** `LIVE` Four items in the fork that cost nothing at runtime and everything to a
reader: `async_step_connection_test` that nothing routes to
(`FORK/config_flow.py:32-55`), `_verify_response_or_raise` defined twice in the same module so
the second silently wins (`FORK/api.py:28` and `FORK/api.py:50`), three unused
`IntegrationBlueprintApiClient*` exception classes left from the scaffold
(`FORK/api.py:12-26`), and the trim and ID3 helpers from `F3.5`.

**F10.2** `LIVE` The broad handler that hides auth failures is at `FORK/api.py:138`
(`except Exception as exception:  # pylint: disable=broad-except`), two lines after
`_verify_response_or_raise` at `FORK/api.py:125` raises the typed auth error it then rewraps.

**F10.3** `LIVE` The request body is `Content-Type: text/plain` at `FORK/api.py:78` and
`FORK/api.py:111`, where the endpoint reference asks for `application/json` with
`{"text": "..."}`.

**F10.4** `VENDOR` Whether `/v1/speak` actually rejects a `text/plain` body is unknown. Auth
is validated before the body on that endpoint, so a dummy key returns 401 regardless of
content type. HANDOFF section 7, item 3, and it stays open.

---

## Theme 11: what nobody has verified, and what it would take

Every item here is a hole. Any piece of content that needs one of them has to wait or say so.

**F11.1** `LIVE` There is no `DEEPGRAM_API_KEY` on this machine. `echo "${DEEPGRAM_API_KEY:-UNSET}"`
prints `UNSET`. Nothing past the auth check has ever been exercised in this project: no
synthesis, no socket, no audio. **To fix: a key in the environment, then one authenticated
round trip against `/v1/speak` and `/v2/speak`.**

**F11.2** First-frame latency over the websocket is unmeasured, on any hardware.
Deepgram markets Flux as starting audio in as low as 80 ms; that is `VENDOR`, it is a
different measurement than the one a Home Assistant user experiences, and **no latency number
of any kind may appear in any draft**. To fix: chapter 6 running on the target hardware, timed
from the first token to the first audio frame, with the sample size stated.

**F11.3** Sam owns zero speaker devices today. Nothing has played out loud through a Home
Assistant voice pipeline. To fix: hardware Sam does not have yet, which is also what blocks
most of the video slate.

**F11.4** The entire websocket protocol in Theme 3 is `VENDOR`. The design of chapter 6 rests
on `F3.2` being true. To fix: open the socket with a real key and log the message sequence.

**F11.5** Whether the fork loads on a real Home Assistant is still untested, and `F1.5` makes
the answer likely yes rather than the audit's likely no. To fix: install it on the real
instance, restart, and read the log. Three commands, once hardware exists.

**F11.6** No installation of this project on real Home Assistant has happened. Chapter 1
passes its tests in a venv (`F9.3`); hassfest and HACS validation run in CI only, because
there is no Docker daemon on this machine (chapter 1 commit message, `325d6d7`).

---

## Sources

- `HANDOFF.md`, this repo, written 2026-09-15. The fact base for the project.
- `docs/state-of-the-fork-2026-09-15.html`, the full audit of `alceasan/ha-deepgram-tts`.
- `docs/flux-first-rewrite-plan.md`, the superseded 16-commit repair plan, whose code review
  section is the most detailed record of the fork's behavior.
- `docs/superpowers/interface-contract.md`, the fixed module boundaries for chapters 2 to 6.
- `alceasan/ha-deepgram-tts` at `ba59415`, read on disk at `~/Developer/ha-deepgram-tts`.
- Home Assistant 2026.9.2 as installed in `.venv`, read on disk.
- `api.deepgram.com`, probed unauthenticated on 2026-09-15.
