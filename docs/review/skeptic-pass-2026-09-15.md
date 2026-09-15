# Skeptic pass: chapters 1 through 3 and the socket client

Written 2026-09-15 on branch `worktree-agent-a72565c57ade8ce4a`. An adversarial review of code
that has already landed. Out of scope on purpose: `config_flow.py` and `tts.py`, both being
rewritten while this was written.

Baseline before starting and after finishing: `.venv/bin/python -m pytest -q` reports
`62 passed`. `uvx ruff@0.16.7 check .` and `format --check .` clean. `scripts/manifest_check.py`
exits 0. Nothing under `custom_components/` or `tests/` was modified. The one repo file this pass
edited is `pyproject.toml`, adding `docs/review` to `extend-exclude` so the reproduction scripts
kept as evidence do not break the CI lint job.

Every finding is marked **CONFIRMED** when it was reproduced and the real output is quoted, or
**PLAUSIBLE** when it was only reasoned about. Reproduction scripts are in `docs/review/repro/`.

---

## Verdict per target

| Target | Verdict | Why |
| --- | --- | --- |
| `stream.py` | **Change** | The shape is right and the cleanup genuinely works. Two defects: a rejected key reads as a dead network, and a turn is truncated at the first `SpeechMetadata` |
| `catalog.py` | **Change** | Settled decision 4 is breakable through the `preferred` branch, and a malformed body escapes as `JSONDecodeError` into `SETUP_ERROR` |
| `api.py` | **Keep** | The error discipline is real, mutation tested, and the timeout covers the body read. The best file here |
| `errors.py` | **Keep** | Four classes, no ceremony, and `status`/`code` on the one that needs them |
| `models.py` | **Keep** (one Flag) | Earns its place. `base_languages` does not lowercase the catalog side |
| `const.py` | **Keep** | Named values with the reason attached. No bare literals doing real work |
| `__init__.py` | **Keep** (one Flag) | Correct `ConfigEntryNotReady` handling. Refetches 205 KB on every options change |
| `scripts/manifest_check.py` | **Change** | Catches the two vectors that actually killed the prior integration. False-positives on any legal optional manifest key |
| `scripts/live_check.py` | **Keep** (one Flag) | Honest about what it cannot do. Hardcoded counts turn benign catalog growth into a FAIL |
| `scripts/measure_first_frame.py` | **Change** | Measures the protocol, not the integration. It is the merge gate for code it never imports |
| `tests/` | **Keep** (two Adds) | 13 of 15 mutations caught. Two uncovered: the family guard, and the sender cleanup |

Tally: 5 Keep, 4 Change, 2 Keep-with-Flag. Adds and Removes are listed per finding.

---

## What earns its place, stated plainly

A review that only finds fault is not a review. Four things here are better than they had to be.

**1. `stream.py`'s concurrency and cleanup are correct.** This was the headline suspicion and it
does not land. An async generator that spawns a task and awaits in a `finally` is a classic way
to leak, and this one does not. Three abandonment modes were run
(`docs/review/repro/repro_stream_errors.py`, `repro_stream_cancel.py`):

```
OBSERVED  consumer breaks then calls aclose()
          frames consumed=2 socket.closed=True aexit_calls=1
          chunks_sent=1 leaked tasks=0

OBSERVED  consumer breaks and drops the generator (no aclose)
          socket.closed=True aexit_calls=1 live tasks=0

scenario 1: cancel the task consuming stream()
  OK: consumer task ended cancelled
  inner: CancelledError propagated out of stream()
  socket closed by the async with: True
  tasks still alive after cancel: 0 []
```

CONFIRMED. The `await self._finish_sender(sender)` in the `finally` runs to completion under
`GeneratorExit`, the `async with` closes the socket on the way out, the sender task does not
leak, and a cancelled consumer stays cancelled. Awaiting in an async generator's `finally` is
legal as long as the generator does not yield again, and this one does not. The shape is right.

**2. `asyncio.timeout` covers the body read in both modules.** The suspicion was a timeout around
the request but not the read. It is not. Both put the read inside the timeout scope, confirmed by
hanging the read with the timeout patched to 150 ms
(`docs/review/repro/test_repro_timeouts_and_errors.py`):

```
  body read hung -> DeepgramConnectionError: https://api.deepgram.com/v2/speak did not respond within 0.15s
  catalog json() hung -> DeepgramConnectionError: Could not read the Deepgram voice catalogs at ...
```

CONFIRMED. `async with (asyncio.timeout(...), self._session.post(...) as response)` nests left to
right, so the `await response.read()` in the body is inside the timeout. The catalog's
`asyncio.gather` inside one `asyncio.timeout` covers both `response.json()` calls.

**3. The test suite is much better than a 62-test suite usually is.** 15 deliberate breakages were
planted and the suite caught 13 (`docs/review/repro/repro_mutation_tests.py`). The three claims
this review was asked to doubt all discriminate for the right reason:

- Serializing the sender ahead of the receive loop fails
  `test_audio_arrives_before_the_text_runs_out`. Buffering the message into one `Speak` fails four
  tests. Splitting a chunk on commas fails the never-splits test. The state-machine fake is doing
  the work the ledger says it is.
- Stripping an ID3 tag from the returned bytes fails `test_audio_is_returned_byte_identical`.
- Splitting language codes on `_` instead of `-` fails three tests from `models.py` and two more
  from `catalog.py`, which are two separate split sites and both are covered.
- Also caught: rewrapping typed errors in `async_verify_key`'s broad handler, routing every model
  to `/v2/speak`, sending `sample_rate` with `encoding=mp3`, putting a real length in the WAV
  header, removing the sample-rate self check, and laundering a catalog failure through the wrong
  error class.

**4. The WAV header is right against an independent oracle.** Python's own `wave` module reads it
as 24000 Hz, 1 channel, 2 bytes per sample, and `readframes` returns all 960 bytes written past
the header despite the all-ones length sentinel. The self check's arithmetic is also right:
48 bytes per millisecond, derived by hand and matching the code exactly.

---

## High severity

### H1. A rejected API key on the websocket reads as a dead network

**CONFIRMED.** `stream.py:167-170`. Verdict: **Change**. This is the defect HANDOFF section 2.2
names as the one that made the prior codebase undebuggable, on the path this integration exists
for.

A bad key on `wss://api.deepgram.com/v2/speak` is rejected during the HTTP upgrade, before any
websocket frame exists. aiohttp raises `WSServerHandshakeError`, which subclasses `ClientError`,
so it lands in the second handler:

```
OBSERVED  handshake 401 -> exception type
          DeepgramConnectionError: Flux socket failed: 401, message='Invalid credentials', url='wss://api.deepgram.com/v2/speak'
          is DeepgramAuthError?       False
          is DeepgramConnectionError? True
```

`_error_from`'s `"AUTH" in code.upper()` matching only ever sees an in-band `Error` text frame,
which a handshake rejection never produces. `test_auth_shaped_server_error_raises_auth_error`
passes, but it exercises a path a real expired key probably never takes, while the path it does
take is untested. That is a test passing for the wrong reason.

It gets worse in combination with settled decision 5. The caller falls back to batch on
`DeepgramConnectionError`, so an expired key silently degrades to `/v2/speak` batch, which fails
with its own 401, and the user gets a connection-shaped failure twice with no mention of the key.

Recommendation: catch `WSServerHandshakeError` ahead of `ClientError` and map 401 and 403 to
`DeepgramAuthError`, reusing the `_AUTH_STATUSES` set already in `api.py`. Add a test that raises
`WSServerHandshakeError(status=401)` from `ws_connect`.

### H2. `resolve_voice` will hand a Flux voice to a Spanish pipeline

**CONFIRMED.** `catalog.py:100-107`. Verdict: **Change**. Settled decision 4 says a non-English
language must never resolve to Flux.

The ladder's third step is guarded on `voice.is_flux` and the last-resort step is guarded on the
base language code, both deliberately. The **first** step, the stored preference, is guarded on
neither. It asks only whether the voice claims the language, and trusts the catalog's answer:

```
1. a catalog that mislabels a Flux voice with Spanish
  resolve_voice(lang="es", preferred=None)                   -> aura-2-celeste-es (family=aura)
  resolve_voice(lang="es", preferred="flux-rogue-es")        -> flux-rogue-es (family=flux)

2. the same mislabel with no Aura voice for that language at all
  resolve_voice(lang="es", preferred="flux-rogue-es")        -> flux-rogue-es (family=flux)
```

This is the exact scenario the ledger says the design survives. See the ledger section below;
that claim is overstated.

The everything-else cases hold up. Empty catalog, `language=""`, `language="EN-us"`,
`language="en-US-x-custom"` and the last-resort branch all behave as documented, and
`resolve_voice(mislabeled, "es", "flux-haley-en")` correctly refuses a preference that cannot
speak the language. It is only the mislabeled-catalog case that gets through, and only through
the preference.

Recommendation: add `and not voice.is_flux` to the preferred branch when the base code is not
English, or more simply hoist one guard to the top of the function: if the base code is not
English, filter Flux out of every candidate set before the ladder runs. One guard in one place is
easier to defend than three guards with different reasoning.

### H3. Nothing tests the family guard that settled decision 4 rests on

**CONFIRMED.** Verdict: **Add**. Deleting the guard entirely leaves the suite green:

```
MISSED  D. drop the family guard from resolve_voice's ladder
        claim: a non-English language must never resolve to Flux
        62 passed in 0.47s
```

The mutation replaced `for voice in candidates: if not voice.is_flux: return voice` with
`for voice in candidates: return voice`. Every test still passed, including the six-language
parametrize written specifically for this rule.

The reason is fixture shape. `multilingual_aura_payload` gives each non-English language exactly
one voice, and that voice is Aura, so `candidates[0]` and "the first non-Flux candidate" are the
same object. The test asserts the right outcome against a catalog that cannot distinguish the two
implementations. `test_preferred_flux_voice_is_refused_for_spanish` has the same problem: it
passes because the fixture's Flux voice does not claim `es`, not because anything guards on
family.

Recommendation: add a fixture with a Flux voice that claims a non-English language, and assert
`resolve_voice` refuses it for that language both with and without it as the stored preference.
That single fixture covers H2 and H3 together.

### H4. Nothing tests the sender cleanup, which has a whole ledger entry behind it

**CONFIRMED.** Verdict: **Add**. Deleting the cleanup call outright leaves the suite green:

```
MISSED  E. never cancel the sender and never surface its failure
        claim: cleanup happens in the finally
        62 passed in 0.47s
```

The mutation replaced `finally: await self._finish_sender(sender)` with `finally: pass`. The
ledger records that the naive fix, suppressing `CancelledError` outright, "passes every test in
this file and quietly breaks shutdown." The measurement is worse than that: removing the entire
cleanup also passes every test in the file. `_finish_sender` is 16 lines of carefully reasoned
code with zero coverage.

`FakeSocket` even tracks `self.closed`, but `FakeSession.Ctx.__aexit__` never calls `close()` and
no test asserts on it, so that field can never be True in the suite. It is dead fixture state.

Recommendation: three tests. One where the sender raises a `ClientError` and the test asserts
`DeepgramConnectionError` mentioning "send failed" rather than a receive-side message. One where
the consumer abandons the generator and the test asserts the socket was closed and no task
remains. One that asserts a cancelled consumer stays cancelled. The reproduction scripts in
`docs/review/repro/` already contain working versions of all three.

### H5. A turn is truncated at the first `SpeechMetadata`

**CONFIRMED against a fake; the real server's behavior is unverified.** `stream.py:223-227`.
Verdict: **Flag**, escalating to Change if a live run confirms it.

`_receive` returns on the first `SpeechMetadata`. HANDOFF section 3.5 supports that: "Every audio
frame for a turn arrives between `SpeechStarted` and `SpeechMetadata`" and "`SpeechMetadata` means
all of that turn's audio has been sent." But the same section says the server places flush
boundaries internally, `SpeechMetadata` carries a `speech_id`, and `SessionMetadata` carries a
separate `total_audio_duration_ms`. A per-speech id and a separate session total both read like a
protocol that can emit more than one speech per connection.

If it does, the client stops at the first one:

```
OBSERVED  server emits SpeechMetadata for segment 1, then segment 2
          audio frames yielded=1 bytes=480 (3 frames of audio were available)
          chunks_sent=1 of 3  warnings=[]
```

One frame of three yielded, one chunk of three sent, and no warning. The failure is silent: the
house answers with the first few words and stops. The sample-rate self check does not catch it
either, because segment 1's bytes and segment 1's duration agree.

No test can catch this, because `FakeSocket` is built on the same assumption: it sends exactly one
`SpeechStarted` and emits `SpeechMetadata` only in response to `Flush`. The test double and the
implementation share a premise, which is the structural reason to be suspicious of it.

Recommendation: this belongs on the first-live-socket checklist ahead of the latency number. Send
three sentences with pauses and count `SpeechStarted` messages. If more than one arrives, the
loop must continue until `Flushed` or `SessionMetadata` rather than the first `SpeechMetadata`,
and `audio_duration_ms` must accumulate.

### H6. `stream.py` uses Python 3.14-only syntax that the CI lint job cannot parse

**Mechanism CONFIRMED; the CI consequence PLAUSIBLE.** `stream.py:167`. Verdict: **Change**.

`except DeepgramAuthError, DeepgramConnectionError:` is unparenthesized multi-exception syntax,
legal only since PEP 758 in Python 3.14:

```
--- 3.14 parse ---  3.14.7  stream.py parses OK
--- 3.9 parse ---   3.9.6   SyntaxError: line 167 'invalid syntax'
                            text: except DeepgramAuthError, DeepgramConnectionError:
```

Every pre-3.14 interpreter rejects it. That matters because `scripts/manifest_check.py` runs
`ast.parse` over every file in the component, and the CI `lint` job invokes it as plain
`python3 scripts/manifest_check.py` with no `setup-python` step, so it uses the runner's system
interpreter. The `test` job pins 3.14; the `lint` job does not. If `ubuntu-latest` ships anything
below 3.14, which it did at the time of writing, the manifest guard crashes with an unhandled
`SyntaxError` and the job fails for a reason that has nothing to do with the manifest.

That is the guard against the bug that killed the prior integration, broken by an incidental
syntax choice.

Recommendation: parenthesize the tuple. It costs two characters and the syntax is not buying
anything. Separately, pin `python-version: "3.14"` in the lint job, because a stdlib-only script
that reads `sys.stdlib_module_names` should be checking the interpreter the integration actually
runs on. Note the dead-code finding L3 below: the clause itself does nothing, so the cheapest fix
is to delete it.

---

## Medium severity

### M1. Three raw exception types escape `stream()` and defeat the batch fallback

**CONFIRMED.** Verdict: **Change**. The docstring promises "Raise `DeepgramConnectionError` on any
socket failure, so the caller can fall back to the batch endpoint." Three inputs break that
promise:

```
OBSERVED  server sends a non-JSON text frame
          JSONDecodeError: Expecting value: line 1 column 1 (char 0)
          typed as a Deepgram error? False

OBSERVED  server sends valid JSON that is not an object
          AttributeError: 'list' object has no attribute 'get'
          typed as a Deepgram error? False

OBSERVED  audio_duration_ms = "10" (a string)
          TypeError: can't multiply sequence by non-int of type 'float'
          typed as a Deepgram error? False
```

The first two come from the bare `json.loads(message.data)` in `_await_connected` and `_receive`,
and the `event.get(...)` that follows it. The third comes from `_check_sample_rate`, which sits
after the whole `try` block at `stream.py:172`, so nothing it raises can be typed. Worse, it
raises after every frame has already been yielded, so a caller that falls back to batch on a
failure would synthesize the whole utterance twice.

Recommendation: a small `_event_from(message)` helper that returns `dict[str, Any] | None`,
catching `ValueError` and rejecting non-dicts, and treating a bad frame as a protocol error
raising `DeepgramConnectionError`. Move `_check_sample_rate()` inside the `try`, or wrap its body,
so a metrics bug cannot become a synthesis failure.

### M2. A malformed catalog body lands in SETUP_ERROR with no retry

**CONFIRMED.** `catalog.py:138-142`. Verdict: **Change**. HANDOFF section 2.2 lists "let a catalog
fetch failure escape `async_setup_entry` as a raw aiohttp error, which marks the entry failed with
no retry" as a defect to avoid. A truncated JSON body with a correct content type does exactly
that, by a different route:

```
  truncated catalog JSON -> JSONDecodeError: unexpected end of data: line 1 column 42 (char 41)
  is DeepgramConnectionError? False
  entry state after a truncated catalog body: ConfigEntryState.SETUP_ERROR
```

`response.json()` raises `ContentTypeError` for a wrong header, which is a `ClientError` and
therefore handled. It raises `JSONDecodeError`, a `ValueError`, for a body that is truncated or
garbled, which is not. The chapter 3 notes record this as deliberate: "anything else escapes as
itself rather than being laundered through the wrong error class." The principle is right and the
boundary is drawn one class too narrow. A truncated body from a flaky connection or a captive
portal is a transient condition, and transient conditions belong in `SETUP_RETRY`.

Recommendation: add `ValueError` to the caught tuple, or catch it inside `_async_get_catalog` and
reraise as `DeepgramConnectionError` with the URL in the message. Add a test asserting
`SETUP_RETRY` for a truncated body.

### M3. The sample-rate self check is blind to the most likely wrong answer

**CONFIRMED.** `stream.py:279`. Verdict: **Change**. The 0.9 to 1.1 window catches a factor of
two, which is the case the ledger entry names. It does not catch 22050 Hz, which is the single
most plausible alternative rate for a speech API:

```
  real stream   8000 Hz  ratio 0.333  warns
  real stream  12000 Hz  ratio 0.5    warns
  real stream  16000 Hz  ratio 0.667  warns
  real stream  22050 Hz  ratio 0.919  SILENT
  real stream  24000 Hz  ratio 1.0    SILENT
  real stream  26000 Hz  ratio 1.083  SILENT
  real stream  32000 Hz  ratio 1.333  warns
  real stream  44100 Hz  ratio 1.837  warns
  real stream  48000 Hz  ratio 2.0    warns
```

A 22050 stream played as 24000 is about 8 percent sharp, roughly a semitone and a half. That is
squarely inside the symptom the ledger describes: "wrong-pitch audio sounds like a bad voice, not
like a bug." The check exists to catch that and this window lets it through.

The other two edges:

```
  duration 0 with 96000 bytes -> warnings=[]
  duration -10 -> warnings=[]
```

A reported duration of zero alongside 96000 bytes of audio is skipped by the `if not
self.metrics.audio_duration_ms` guard. That is the most diagnostic input the check will ever see
and it is the one input it ignores.

Rounding, in contrast, is a non-issue and should not be worried about. Integer-millisecond
rounding only trips the window below 5 ms of audio:

```
  clip    1 ms  worst-case rounding ratio 1.500  trips the window
  clip    2 ms  worst-case rounding ratio 1.250  trips the window
  clip    5 ms  worst-case rounding ratio 1.100  inside the window
  clip  100 ms  worst-case rounding ratio 1.005  inside the window
```

Recommendation: tighten to 0.97 to 1.03 and add a floor of, say, 200 ms of reported duration
below which the check is skipped as too short to be meaningful. That catches 22050 while staying
clear of rounding. Warn explicitly when `audio_duration_ms` is present but not a positive number,
rather than returning. Keep it a warning; that part of the decision is right.

### M4. No bound on a turn, and `warnings` grows without limit

**CONFIRMED.** Verdict: **Add**. `TIMEOUT_WS_FRAME` is per `receive()` call, not per turn, so a
server that emits anything at all every 29 seconds keeps the loop alive forever. Every `Warning`
frame is appended to `metrics.warnings` and logged at warning level:

```
OBSERVED  server dribbles Warning frames forever
          receive() calls before it ended=401, warnings recorded=397
          ended only because the fake gave up
          nothing in the client bounds total turn time
```

397 entries in a list and 397 lines in the log, from a fake that had to stop itself. The batch
path has `TIMEOUT_SPEAK` of 60 seconds as a total bound. The socket path, which is the primary
path, has no equivalent.

Recommendation: one `asyncio.timeout` around the whole of `stream()` sized to the longest
utterance worth waiting for, and a cap on `metrics.warnings` with a count of what was dropped.

### M5. `manifest_check.py` fails on a legal optional manifest key

**CONFIRMED.** `scripts/manifest_check.py:69`. Verdict: **Change**. The order check is

```python
if keys != [key for key in REQUIRED_KEYS if key in keys]:
```

which compares the manifest's full key list against a list built only from `REQUIRED_KEYS`. Any
key outside that set makes them unequal regardless of order. Adding `"dependencies": ["tts"]` in
the position hassfest itself uses:

```
CAUGHT  a legal optional manifest key ("dependencies")
        FAIL manifest.json keys out of hassfest order: ['domain', 'name', 'codeowners',
        'config_flow', 'dependencies', 'documentation', ...]
```

The order is correct and the message says it is not. `dependencies`, `after_dependencies`,
`loggers`, `quality_scale` and `dhcp` are all legal and all trip this. That matters more than a
cosmetic false positive: the next person to add a legitimate manifest key will be told the guard
is wrong, and the cheapest way to make it green is to loosen it. This is the check that protects
against the bug the project was founded on not repeating.

Recommendation: check relative order of the required keys only. Filter `keys` down to the ones in
`REQUIRED_KEYS` before comparing, and report unknown keys separately as information rather than
as an order failure.

### M6. `measure_first_frame.py` never imports the code it is the merge gate for

**CONFIRMED by reading.** Verdict: **Change**. The ledger gates chapter 6's merge on this script
"having produced a number on real hardware." The script contains its own websocket client,
its own `Timings` class duplicating `StreamMetrics`, and its own send loop. It imports `aiohttp`,
`asyncio` and stdlib. It never imports `custom_components.deepgram_tts.stream`.

So the number it produces measures Deepgram's API from a given machine. It says nothing about
whether `FluxSocket` yields that first frame to Home Assistant, whether the WAV header is right,
whether the self check fires, or whether the metrics the entity will report are accurate. The
gate and the thing being gated do not touch.

The same applies to the degradation half. `drop_mid_turn` sends the whole text in one `Speak`,
kills the socket, then calls `batch_fallback` directly and sets
`degraded_cleanly = fallback["status"] == 200`. That asserts the batch endpoint works. The
integration's fallback lives in `tts.py` and is never invoked.

Two smaller notes on the same file. The 40 ms inter-chunk `asyncio.sleep` means "first frame
before the text runs out" is measured against a 200 ms send window that the script chose, which
should be stated wherever the number is quoted; it is conservative relative to a real LLM
emitting fifteen words, so it does not flatter the result. And `summarize`'s p95,
`ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]`, is exactly `max` for any run count up
to 20, so the default 10-run invocation prints the same number twice under two labels.

Recommendation: drive `FluxSocket` in a second mode so the gate exercises the shipped code, and
read `socket.metrics` rather than reimplementing it. Report p95 only above 20 runs, or drop it.

---

## Low severity

**L1. `models.py` lowercases the input side of a language comparison but not the catalog side.**
CONFIRMED. `_base_code` in `catalog.py` calls `.lower()`; `VoiceInfo.base_languages` does not. A
catalog that ever reported upper-case codes would advertise a language nothing can serve:

```
5. a catalog whose language codes are upper case
  supported_languages(shouty)       -> ['EN']
  voices_for_language(shouty, "en") -> []
  resolve_voice(shouty, "en", None) -> None
```

Verdict: **Change**, one `.lower()` in `base_languages`. The chapter 3 notes claim "Input is
lowercased, so an Assist pipeline handing over `EN-us` still matches," which is true and is only
half the symmetry.

**L2. A non-string `preferred` raises a raw `TypeError` from a dict lookup.** CONFIRMED.
`preferred=123` returns the default with a warning, but `preferred=['flux-haley-en']` gives
`TypeError: cannot use 'list' as a dict key`. Config data is a string in practice, so this is
theoretical. Verdict: **Flag**.

**L3. `except DeepgramAuthError, DeepgramConnectionError: raise` in `stream.py` is dead code.**
CONFIRMED:

```
DeepgramConnectionError MRO: ['DeepgramConnectionError', 'DeepgramError',
                              'HomeAssistantError', 'Exception', 'BaseException', 'object']
is subclass of ClientError? False    is subclass of OSError? False
```

Neither class can reach the following `except (ClientError, TimeoutError, OSError)`, so reraising
them first changes nothing. Verdict: **Remove**. Worth calling out because it is the only thing in
`stream.py` that looks like the typed-error discipline, and it is decorative while the real hole
(H1) is in the clause underneath it.

**L4. Catalog HTTP status failures are described as unreachability.** CONFIRMED:

```
  catalog HTTP 500 -> Could not read the Deepgram voice catalogs at ... : 500, message=''
  catalog HTTP 401 -> DeepgramConnectionError: Could not read ... : 401, message=''
```

`ConfigEntryNotReady` is the right behavior for both, so this is about the message a user reads in
the log, not the control flow. A 401 on a public endpoint most likely means an intercepting proxy,
and "could not read" sends the reader looking at their network instead of their network's
middleboxes. Verdict: **Flag**, worth a sentence in the message.

**L5. `manifest_check.py` can be fooled three ways, and only one of them matters a little.**
CONFIRMED. The vectors asked about, tested one at a time against a scratch copy of the repo:

| Vector | Result |
| --- | --- |
| `import pydub` at module level | CAUGHT |
| `import pydub` inside a function body | CAUGHT |
| `import pydub` inside `try/except ImportError` | CAUGHT |
| `import pydub` under `if TYPE_CHECKING:` | CAUGHT (arguably a false positive) |
| `import pydub` in a subpackage module | CAUGHT |
| `importlib.import_module("pydub")` | FOOLED |
| `__import__("pydub")` | FOOLED |
| a sibling `pydub.py` decoy plus `import pydub` | FOOLED |
| `__init__.py` re-export of a relative import | not applicable; `rglob` scans the real importer |

The two vectors that actually killed the prior integration, a module-level import and an
`ImportError`-guarded import, are both caught, and `ast.walk` is the reason: nesting does not hide
anything. Does the rest matter? Barely. Dynamic imports in a Home Assistant integration are
unusual and would be visible in review, and the decoy case requires deliberately naming a local
module after a PyPI package. Verdict: **Flag**. Add one line to the docstring saying the check is
static and does not see `importlib`, so the next reader does not over-trust it. The
`TYPE_CHECKING` case is the one worth thinking about, because a typing-only import genuinely does
not need a manifest requirement and the check will insist it does.

**L6. `live_check.py` turns benign catalog growth into a FAIL.** CONFIRMED by reading.
`EXPECTED_FLUX_VOICES = 36` and `EXPECTED_AURA_TTS = 102` are compared with `!=`, and a mismatch
sets `ok = False` and prints "chapter 2 live check: FAIL". Deepgram adding a 37th Flux voice is
good news reported as a failure. Verdict: **Flag**. Report drift as drift, and reserve the failure
exit for a count that went down or a fetch that broke. Separately, when no key is set the script
returns 2 before printing the summary block, so a drift detected in the unauthenticated half is
computed and then discarded.

**L7. `_finish_sender` does swallow an outer cancellation, though nothing observable breaks.**
CONFIRMED, and this one is a correction to the ledger's reasoning rather than a defect. The
comment says `sender.cancelled()` being true means "ours." It does not; it means the sender task
finished cancelled, which says nothing about where the `CancelledError` that was caught came from.
Constructed directly:

```
scenario 2: _finish_sender with an already-cancelled sender and an outer cancel
  _finish_sender: returned normally, swallowing the cancellation
  OK: the cancellation survived _finish_sender
  task.cancelled()=True task.cancelling()=1
```

The swallow happens. The task still ends cancelled, because asyncio tracks `cancelling()`
independently of whether a handler reraised. So the outcome is safe and the stated reason is not
what makes it safe. Verdict: **Flag**. If this becomes a blog post, the mechanism to describe is
`task.cancelling()`, not "we know it was ours."

**L8. `__init__.py` refetches 205 KB on every options change.** CONFIRMED by reading. The update
listener calls `async_reload`, which reruns `async_setup_entry`, which refetches both catalogs.
Changing the speed slider refetches 205 KB of JSON. The ledger already flags the per-setup cost;
this is the multiplier on it. Verdict: **Flag**, and it strengthens the existing case for
measuring before caching. Also: `entry.data[CONF_API_KEY]` raises a raw `KeyError` into
`SETUP_ERROR` for an entry without the key, which is unreachable today.

**L9. `measure_first_frame.py` uses the cleanup pattern the ledger says is wrong.** CONFIRMED by
reading. `finally: sender.cancel(); await asyncio.gather(sender, return_exceptions=True)` swallows
everything including `CancelledError`, which is precisely the naive version `_finish_sender`
exists to avoid. It is a human-run script so the stakes are low, but it is the file someone will
copy from. Verdict: **Flag**.

---

## The ledger, claim by claim

Every `[claim]` entry plus the falsifiable assertions inside the `[decision]` entries that this
review could test. The ledger is the source material for a blog post, so an overstated claim here
becomes an overstated claim in public.

| Ledger entry | Verdict |
| --- | --- |
| "Chapter 1 loads against real Home Assistant 2026.9.2, and it held" | **Holds.** 62 passed against HA 2026.9.2 on Python 3.14.7. The "not yet verified" caveats are still accurate |
| "The live catalogs match the handoff's numbers exactly" | **Holds** as a measurement; not re-checkable here without network. One Flag: the 36 and 102 are hardcoded as equality assertions in `live_check.py` (L6) |
| "138 voices merge with zero key collisions, and seven languages come out" | **Holds.** Also the most carefully worded claim in the file: "no non-English language can reach a Flux voice, **because there is no Flux voice that claims one**" correctly makes the guarantee contingent on the catalog rather than the code |
| "resolve_voice grew a last resort ... Settled decision 4 survives a catalog that is wrong about itself" | **Overstated.** The last-resort branch does survive it, as claimed and as verified. The preferred branch does not: `resolve_voice(mislabeled, "es", "flux-rogue-es")` returns a Flux voice. See H2. This is the one claim that would need rewriting before it appears in a post |
| "The WAV header's sample rate is an assertion, so the client checks its own math" | **Holds, with the reach overstated.** The check exists, the arithmetic is right, it catches a factor of two, and warning rather than raising is the right call. But it is silent at 22050 Hz, silent on a reported duration of zero, and crashes on a string duration. See M3 and M1 |
| "A streaming WAV declares an unknown length, which is the whole point" | **Holds.** Verified against Python's `wave` module as an independent oracle, and the mutation that replaces the sentinel is caught. The "unverified" caveat about tolerant playback paths is honest and still open |
| "The socket's own error was replaced by the cleanup's CancelledError" and its fix | **Holds in behavior, imprecise in reasoning, unprotected by tests.** The fix works; the `sender.cancelled()` rationale is not what makes it work (L7); and deleting the whole cleanup passes the suite (H4). The closing line, "the naive fix passes every test in this file," understates it |
| "The fake socket proves the interleaving, which a fixed message script cannot" | **Holds on substance, wrong on a number.** Mutation testing confirms the state machine discriminates: serializing the sender, buffering the message, and splitting on commas are all caught. But there are **16** socket tests, not 17. 62 in the suite is correct |
| "Chapter 6 gets built on a branch and is not merged, because the trap is real" | **Holds, and it is the best reasoning in the file.** One Flag on the exit condition: the gate is `measure_first_frame.py` producing a number, and that script never imports `stream.py` (M6). Satisfying the gate as written would not validate what the gate is protecting |
| "`manifest_check.py` ... that failure is now a CI-visible error instead of a discovery" | **Holds for the real vectors, with two Flags.** The check catches module-level and `ImportError`-guarded imports, which is the claim that matters. But the CI job running it cannot parse `stream.py` on a pre-3.14 interpreter (H6), and the order check false-positives on legal keys (M5) |
| "sample_rate is dropped only for an explicit encoding=mp3" | **Holds.** The code does exactly this, the test covers it, and the mutation that widens it is caught. Still correctly listed as the top item the first API key settles |
| "container=none falls through the extension chain" | **Holds.** `_extension_for` skips `CONTAINER_NONE` and falls through to encoding, as recorded |

---

## Adds: what a skeptic wants that is not here

1. **A test for a catalog that is wrong about itself.** One fixture with a Flux voice claiming
   `es` closes H2 and H3 at once, and it is the fixture the ledger's strongest design claim
   depends on.
2. **Tests for the socket's cleanup.** Sender failure surfaced, socket closed on abandonment,
   cancellation preserved. Working versions are in `docs/review/repro/`.
3. **A test for a rejected key on the socket handshake**, raising `WSServerHandshakeError` with
   status 401 from `ws_connect`.
4. **A live probe counting `SpeechStarted` messages per turn**, ahead of the latency number, since
   H5 cannot be settled from a fake.
5. **A test for `manifest_check.py` itself.** It is the guard against the failure that motivated
   the whole project and it has no coverage. A fixture tree with a planted bad import and one with
   a legal optional manifest key would have caught M5 before it landed.

---

## The single thing to fix first

**H1, the websocket auth error typing.** Four reasons it outranks the rest. It is the exact defect
HANDOFF section 2.2 puts at the top of the do-not-repeat list. It sits on the primary path, not a
corner. The batch fallback actively hides it, so the symptom a user reports will be a network
problem and the cause will be their key. And the test that looks like it covers this passes
against a path a real expired key probably never takes, so the suite reads as green over a known
hole. The fix is a handler ordered ahead of `ClientError` and one test.

H2 is a close second and is cheaper, but it needs a mislabeled catalog to fire. H1 fires the first
time somebody's key expires.
