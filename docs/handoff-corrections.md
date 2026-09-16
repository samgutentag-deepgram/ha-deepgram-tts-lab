# Corrections to HANDOFF.md

`HANDOFF.md` is the historical record of what was known on 2026-09-15, before anything was
built. **It is not edited in place**, because rewriting it would destroy the record of what the
project believed when it started, and half the value of a build log is being able to see where
the starting assumptions were wrong.

This file is the correction. Every entry names the section it corrects, what the handoff claims,
what is actually true, how that was established, and what the code would do wrong if the
handoff's version were believed.

Corrections are appended, never edited. Each carries the date it was established.

---

## C1. `async_timeout` IS available on a real instance. Section 2.1 overstates the failure.

**Established 2026-09-15.** Corrects section 2.1 and, by extension, the framing of section 2.

**What the handoff says:**

> `async_timeout` is not in HA core requirements, and aiohttp dropped it as a dependency at 3.10
> (HA ships 3.14.3). Nothing installs it, so the integration almost certainly did not load at all.

**What is actually true.** `async_timeout` is importable on any Home Assistant instance that has
the `tts` component loaded, which is every instance a TTS integration runs on. The dependency
chain is three hops and none of them are obvious:

```
homeassistant/components/tts/manifest.json   dependencies: ["http", "ffmpeg"]
homeassistant/components/ffmpeg/manifest.json requirements: ["ha-ffmpeg==3.2.2"]
ha-ffmpeg==3.2.2                              requires: "async-timeout"
```

The last line is the load-bearing one, and what makes it easy to miss is that every **other**
package in the graph guards it behind a Python version marker:

```
bleak==3.0.2      ->  "async-timeout>=3.0.0 ; python_full_version < '3.11'"
aiohttp==3.14.3   ->  "async-timeout<6.0,>=4.0; python_version < \"3.11\""
ha-ffmpeg==3.2.2  ->  "async-timeout"
```

`ha-ffmpeg` has no marker at all, so pip installs `async-timeout` on Python 3.14 too. Confirmed
present in the test environment at version 5.0.1.

**How this was established.** Enumerated with `importlib.metadata.requires` over every installed
distribution in the project's own test venv, which runs the real Home Assistant 2026.9.2, then
cross-checked against the installed `tts` and `ffmpeg` manifests. Reproducible in one command:

```bash
.venv/bin/python -c "
from importlib.metadata import distributions, requires
for d in distributions():
    for r in requires(d.metadata['Name']) or []:
        if 'async' in r and 'timeout' in r:
            print(d.metadata['Name'], '->', r)"
```

**What this changes.**

- **The pydub half of section 2.1 still stands, and it is the real cause.** `pydub` is absent
  from the environment, nothing in a working Home Assistant requires it, and the prior
  integration's optional-import guard left `AudioSegment = None` so its streaming path raised
  `RuntimeError("pydub is not available")` on every request. That is a real, total failure of
  the streaming path.
- **"It almost certainly did not load at all" is not supportable and must not be published.**
  The integration most likely loaded fine and then failed on every Assist pipeline response,
  which is a different and more interesting bug: direct `tts.speak` calls kept working, so it
  looked healthy to anyone testing it by hand.
- Nothing in this repo's code depended on the wrong version of the claim. We use
  `asyncio.timeout` because it is stdlib and correct, not because `async_timeout` is missing.
  That reasoning is unaffected.
- `scripts/manifest_check.py` is unaffected and arguably more valuable: an undeclared import that
  happens to resolve through somebody else's transitive dependency is worse than one that fails
  outright, because it works until that dependency drops it.

**Where this matters most.** `advocacy/prep/notes.md` records it as F1.5 and F1.6, and the
technical blog draft was written against the corrected version. A post claiming the integration
never loaded would have been wrong in a way a reader could check in five minutes.

---

## C2. `/v2/speak` does not range check `speed` before auth. Section 3.4's speed row is from the docs.

**Established 2026-09-15.** Corrects section 3.4.

**What the handoff says.** Section 3.4 presents its query parameter table as "enumerated by
sending deliberately invalid values and reading the rejections," and lists:

> | `speed` | 0.5 to 1.5, 0.05 increments |

**What is actually true.** That range was never enumerable by probing. Deliberately invalid
speeds all return 401 rather than 400:

```
speed=3.0   -> HTTP 401  {"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}
speed=1.07  -> HTTP 401  {"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}
speed=0.1   -> HTTP 401  {"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}
```

So the `speed` range comes from Deepgram's documentation, not from observed behavior, and it is
unverified. Whether an off-grid value like 1.07 is rejected or quietly rounded is unknown.

**What still holds, and this is the useful part.** Not every check runs after auth. Two do run
before it, which is what made the rest of section 3 possible:

```
bogus_param=1              -> HTTP 400  INVALID_QUERY_PARAMETER: unknown field `bogus_param`
model=aura-2-thalia-en     -> HTTP 400  V1_MODEL_ON_V2_SPEAK_ENDPOINT
```

Unknown-field rejection and the family routing check are pre-auth. Value range checks are not.
So section 3's enum lists (`encoding`, `container`) and the two-families finding are sound, and
only the numeric ranges are docs-sourced.

**How this was established.** Six requests to the live `/v2/speak` with a dummy 40-character
token, run twice by two different sessions, with the two pre-auth controls above as a baseline
so "everything returns 401" could be ruled out.

**What this changes.**

- The comment in `const.py` next to `SPEED_MIN` and `SPEED_MAX` claimed the endpoint validates
  that range. Corrected to say where the range comes from.
- We still constrain speed to 0.5 to 1.5 in 0.05 steps in the options flow, which is right: a
  documented range is a better guess than no constraint.
- Add to the first-API-key list: send `speed=1.37`, off the 0.05 grid, and record whether it is
  rejected or rounded. The options flow's slider step depends on the answer.

---

## C3. Section 4.3's constant list is correct and incomplete.

**Established 2026-09-15.** Corrects section 4.3 by addition.

Everything section 4.3 names is exactly right in the installed Home Assistant 2026.9.2:
`ATTR_VOICE = "voice"`, `ATTR_PREFERRED_FORMAT = "preferred_format"`,
`ATTR_PREFERRED_SAMPLE_RATE = "preferred_sample_rate"`, `_DEFAULT_FORMAT = "mp3"`.

Also present and exported, and not mentioned: `ATTR_AUDIO_OUTPUT = "audio_output"`,
`ATTR_PREFERRED_SAMPLE_CHANNELS`, `ATTR_PREFERRED_SAMPLE_BYTES`, `ATTR_PREFERRED_BITRATE`,
`ATTR_MEDIA_PLAYER_ENTITY_ID`, `ATTR_PLATFORM`, `CONF_LANG`.

Two behaviors worth knowing that section 4.3 does not cover:

1. The five `preferred_*` options bypass `supported_options` validation entirely. Advertising one
   only decides whether it stays in `options` for the entity to act on, or gets popped and
   applied by ffmpeg afterwards.
2. `async_get_tts_audio(self, message, language, options)` takes `options` as a **required
   positional** `dict[str, Any]`, not `dict | None = None`. Chapter 1's placeholder had the
   optional shape and was wrong.

`ATTR_AUDIO_OUTPUT` is deliberately not advertised by this integration. See
`docs/chapter-5-notes.md` for why: the only two core consumers give it incompatible meanings,
and honoring it as a second format knob fights `preferred_format`.

---

## C4. `mutagen` is pinned to a version the handoff never named, and the first guess was wrong.

**Established 2026-09-15.** Not a correction to the handoff, which does not mention `mutagen`.
Recorded here because the wrong number was briefly in this repo.

The installed `homeassistant/components/tts/manifest.json` requires `mutagen==1.48.1`.
`requirements-test.txt` initially pinned `1.47.0`, which was a guess. Corrected to match the
manifest, so the test environment matches a real instance rather than approximating one.
`ha-ffmpeg==3.2.2` added alongside it for the same reason.

Neither belongs in our `manifest.json`. They are the `tts` component's requirements, and
declaring somebody else's dependency is how a manifest starts lying, which is the failure mode
section 2.1 is about.

---

## C5. Returning WAV is correct but not free. Section 4.3 is right about the first half.

**Established 2026-09-15.** Corrects section 4.3.

**What the handoff says:**

> So returning WAV and letting HA transcode is correct and free. Doing our own transcode is waste.

**What is actually true.** Correct, yes. Free, no. `final_extension` falls back to
`_DEFAULT_FORMAT`, which is `"mp3"`, when no format was requested, and `needs_conversion` then
compares that against the entity's `"wav"`. So **ffmpeg runs on essentially every call.** Assist
makes it unconditional regardless: the pipeline sets a preferred sample rate alongside the
format, and a non-null rate forces conversion on its own.

Read from the installed `homeassistant/components/tts/__init__.py` at lines 1068-1070 and
1151-1157, and `assist_pipeline/pipeline.py` at 1425-1431.

**What this changes.** Not the design decision. Transcoding ourselves is still worse, and two of
the three core integrations that stream also return WAV, so this is the core-normal choice.
What changes is the arithmetic: **any latency budget written from the handoff is short by one
ffmpeg subprocess spawn per turn.** On a Raspberry Pi that is not nothing, and it has to be in
the first-frame measurement rather than discovered after it.

Also confirmed in the same pass, and this is good news for `stream.py`: `_async_convert_audio`
passes the entity's extension as ffmpeg's `-f`, and it carries a special case whose only purpose
is our exact situation:

```python
if is_input_gen and from_extension == "wav":
    # The container is known, so minimize probing latency for live TTS audio.
    command.extend(["-probesize", "32"])
```

All five variants of the RIFF size fields, including our all-ones sentinel and wyoming's zeros,
produce byte-identical ffmpeg output over a non-seekable pipe. Nothing truncates, conversion is
progressive rather than buffered to end of stream, and a header split across two writes still
works. One hard limit: raw PCM declared as `extension="wav"` with no header at all fails with
`invalid start code in RIFF header`.

---

## C6. A mid-turn fallback is not safe, and the handoff's degradation advice needs a qualifier.

**Established 2026-09-15.** Qualifies settled decision 5 and section 6.1.

**What the handoff says.** Settled decision 5: "Fall back to `/v2/speak` batch when the socket
fails or when the selected voice is Aura, so a dropped connection degrades instead of erroring."
Section 6.1 makes it chapter 6's second verification: "killing the socket mid-turn degrades to
batch instead of raising."

**What is actually true.** It depends entirely on whether anything has been yielded yet, and the
handoff does not distinguish the two cases.

`TTSCache.async_load_data` drains the entity's generator once, in a background task, and
multicasts the result. `async_stream_data` yields every **already-buffered** chunk before it
re-raises a failure. So a generator that emits audio, fails, and then yields a batch result
hands the consumer a truncated WAV stream immediately followed by a second complete audio file.
That decodes as the first half followed by garbage.

Read from the installed `tts/__init__.py` at lines 160-183 and 207-211.

**What this changes.** Nothing in the code, because chapter 6 was built with two failure windows
from the start and already sits on the safe side of this. Before any audio has reached the
caller, the whole turn is served from batch. After, the turn ends early and the log says why.
The entity also holds the socket's WAV header until the first real audio frame, specifically to
keep the safe window as wide as possible.

Recorded because the handoff's wording would lead a reader straight into the unsafe version, and
because two independent investigations arrived at the same hazard from opposite directions: one
by reasoning about RIFF headers while writing the fallback, one by reading HA's cache
implementation.

**Two more facts from the same reading, both worth knowing before anyone quotes a cost.**

The drain starts the moment Home Assistant creates the result stream, not when a player fetches
it. So the socket opens and characters are billed even if nobody ever listens. And streamed
audio is never cached or deduplicated: `store_to_disk=False`, keyed on a ULID. Batch audio is
cached; streamed audio is not. At $0.045 per 1,000 characters that is a real difference in a
house that asks the same question every morning.

---

## C7. The open questions in section 7 are closed. Three answers, one of them a bug.

**Established 2026-09-16, with a real API key.** Closes section 7 items 1 and 3, and settles the
`speed` half of C2.

### Section 7 item 1: the first authenticated round trip. PASSES.

```
flux  /v2/speak flux-haley-en:    HTTP 200, audio/mpeg, 19584 bytes, 2.10s, first4=ff f3 64 c4
aura  /v1/speak aura-2-thalia-en: HTTP 200, audio/mpeg, 17136 bytes, 1.40s, first4=ff f3 64 c4
```

`ffprobe` on both: `mp3`, 24000 Hz, mono, 48 kbps. So the undocumented default output of both
endpoints is 24 kHz mono mp3 at 48 kbps, and `0xFFF3` is a real MPEG frame sync rather than a
container we guessed at.

### Section 3.4's `speed` range is real after all, and C2 needs this qualifier.

C2 said the 0.5 to 1.5 range in 0.05 increments was docs-sourced because probing returned 401.
With a real key it validates, and the error messages are explicit:

```
speed=1.37 -> 400  "'speed' must be provided in increments of 0.05."
speed=3.0  -> 400  "'speed' must be between 0.5 and 1.5."
speed=0.1  -> 400  "'speed' must be between 0.5 and 1.5."
speed=1.15 -> 200
```

So the **values** in section 3.4 are correct. What was wrong is only the claim that they were
established by pre-auth probing. Range checks run after auth; schema checks run before it. The
options flow's 0.05 slider step is right, and off-grid values are rejected rather than rounded.

### A real bug: `sample_rate` is rejected with no encoding at all.

```
sample_rate=24000, no encoding -> 400 UNSUPPORTED_AUDIO_FORMAT
  "Unsupported audio format: `sample_rate` is not applicable when `encoding=mp3`."
```

mp3 is the default, so omitting `encoding` is the same as asking for mp3. Chapter 2 followed the
interface contract literally and dropped `sample_rate` only for an **explicit** `encoding=mp3`,
which left a request the API rejects reachable through the default. This was recorded in the
ledger as a deliberate decision to follow the contract rather than guess, and the guess would
have been right. Fixed in `_build_params`, with two tests.

### Section 7 item 3: `/v1/speak` does accept a `text/plain` body. Answered.

`Content-Type: text/plain` with a raw body returns HTTP 200 and audio. This only ever affected
the Aura path and this integration always sends JSON, so nothing changes. The question is closed.

### And the formats the streaming path depends on, confirmed over batch

```
encoding=linear16&container=wav&sample_rate=24000  -> 200  audio/wav          RIFF
encoding=linear16&sample_rate=24000                -> 200  audio/wav          RIFF
encoding=linear16&container=none&sample_rate=16000 -> 200  audio/l16;rate=16000  raw
encoding=linear16&container=wav&sample_rate=48000  -> 200  audio/wav          RIFF
```

`container` defaults to `wav` for `linear16`. Both 16000 and 48000 are accepted, which matters
because the two playback paths the hardware research found want exactly those: 16 kHz for an
ESPHome satellite with the speaker flag, 48 kHz for a Voice Preview Edition fetching the proxy
URL itself. And `audio/l16;rate=16000` carries a parameter on the content type, which
`_extension_for` already handles by splitting on `;`.

---

## C8. The Flux socket really does emit 24 kHz, and the WAV header is correct.

**Established 2026-09-16.** Closes the largest open risk in chapter 6.

`stream.py` asks the socket for `encoding=linear16&sample_rate=24000` and prepends a WAV header
declaring 24 kHz. Nothing in the protocol confirms the rate, so that header was an assertion.

Six live turns through the real `FluxSocket`, with the rate computed from bytes received against
the `audio_duration_ms` the server reported:

```
implied sample rate across runs: [24000]
MATCHES the 24000 Hz in the WAV header. Playback pitch is correct.
ffprobe on the result: pcm_s16le, 24000 Hz, 1 channel, 6.24 s
```

So the header is right, ffmpeg decodes what we produce, and the self-check in
`_check_sample_rate` stayed quiet for the right reason rather than because it is broken. The
tightened 0.95 tolerance from the skeptic pass did not produce a false positive on real audio.

## C9. First-frame latency, measured. The 80 ms figure is not reproducible from a house.

**Established 2026-09-16.** Closes section 7 item 2, which said the figure was unmeasured and
that Deepgram's "as low as 80 ms" was a claim to test rather than a fact to repeat.

Measured on a MacBook, arm64, over wifi, twice with two independent harnesses that agree:

```
                            median      min      max      p95
socket connect to Connected    96 ms    86 ms   146 ms   146 ms
first Speak to first audio    314 ms   285 ms   332 ms   332 ms
first Speak to SpeechMetadata 3927 ms
```

The network floor on this path is not small and has to be subtracted before the number means
anything:

```
ping api.deepgram.com   min/avg/max 71.99 / 72.93 / 76.25 ms
TCP connect             ~75 ms
TLS established         ~160 ms
```

**So 73 ms of the 314 ms is one round trip that no implementation can avoid.** An 80 ms
time-to-first-audio is barely above that floor, which means it must be measured from inside
Deepgram's network or with the transit excluded. It is not reachable from a house on this coast,
and it should not be repeated as though it were.

**The defensible claim is the comparison, not the absolute.** Same machine, same network, same
text, same voice:

```
streaming, first audio frame   median  314 ms
batch, whole clip returned            3394 ms
                                      10.8x faster to first sound
```

And the property that actually decides whether streaming is worth building:

```
realtime factor   median 1.56x
```

Audio arrives 1.56 times faster than it plays, so a player that starts on the first frame never
starves. Below 1.0 the whole design would be pointless. This is the number to lead with.

All figures are in `scripts/out/live-stream-*.json` and `scripts/out/first-frame-*.json` with the
hardware recorded in each file. **None of this is the Pi.** A Raspberry Pi on wifi will be
slower, and the ffmpeg conversion C5 describes is a subprocess spawn that is not in these numbers
because they do not go through Home Assistant.
