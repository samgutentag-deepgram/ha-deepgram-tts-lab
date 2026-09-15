# blog-technical-draft.md

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and there is no Gate A task in Asana for
> this piece. It is a full draft written ahead of the gate so the cycle is a short job later.
> It has had a `de-slop` pass (report at the bottom). It has not been reviewed by anyone.
>
> **Every claim traces to a fact id in `notes.md`.** Unverified claims are marked inline in
> the body with `[unverified: ...]`, which stays in the text until someone verifies the thing
> or cuts the sentence. There is no latency number anywhere in this draft, on purpose.

---

# Reading Somebody Else's Home Assistant Integration Before Writing Mine

I wanted a better voice on my Home Assistant voice assistant. There's already a community
integration for Deepgram TTS, [`alceasan/ha-deepgram-tts`][fork], so the obvious move was to
fork it, point it at the newer API, and be done by lunch.

I read it instead. It's 858 lines of Python, it was last touched in January, and about a
quarter of it is a sentence splitter. Reading it taught me more about Home Assistant's
text-to-speech contract than the docs did, mostly because it's written against that contract
carefully enough to show where the contract is sharp.

None of what follows is a knock on that repo. It shipped a working one-shot path against a
real API, people installed it, and it's the reason I knew the shape of this problem before I
wrote a line. Every defect I found in it is a defect I would have written myself, and two of
them I probably would have written worse.

## One Method Is The Whole Opt-In

Home Assistant supports streaming text into a TTS entity. You get an async generator of text
chunks as the language model produces them and you return an async generator of audio bytes.

There is no flag for this. Here's how Home Assistant decides whether your entity can do it:

```python
# homeassistant/components/tts/entity.py
def async_supports_streaming_input(self) -> bool:
    """Return if the TTS engine supports streaming input."""
    return (
        self.__class__.async_stream_tts_audio
        is not TextToSpeechEntity.async_stream_tts_audio
    )
```

It compares your class's method against the base class's method. If they differ, you stream.
Defining `async_stream_tts_audio` **is** the opt-in, which means there's no state between "not
written" and "carrying every response your voice assistant makes."

That produces a failure shape I want to name, because it looks unexplainable in a bug report.
Call `tts.speak` from a script and it works, because that goes through
`async_get_tts_audio`. Talk to your assistant and it fails, because that goes through the
streaming method. Same integration, same key, same voice. Nothing in the integration's own
configuration distinguishes those two paths, so the natural conclusion is that your voice
pipeline is broken.

## The Generator That Wasn't

The contract is small. Two dataclasses:

```python
@dataclass
class TTSAudioRequest:
    language: str
    options: dict[str, Any]
    message_gen: AsyncGenerator[str]

@dataclass
class TTSAudioResponse:
    extension: str
    data_gen: AsyncGenerator[bytes]
```

Small enough to satisfy by accident. Here's the fork's streaming path:

```python
async def message_gen() -> AsyncGenerator[str, None]:
    texto = ""
    if hasattr(request, "message_gen") and request.message_gen is not None:
        async for chunk in request.message_gen:
            texto += chunk
    yield texto
```

It's an async generator. It has the right type. It consumes the whole input before yielding
anything, so nothing starts synthesizing until the language model has finished talking. The
type signature can't tell you that, and neither can a test that checks you got audio back.

Below that generator sits a sentence splitter with a buffer threshold of
`min_len = 2 ** count * 10`, where `count` goes up once per input chunk. By chunk twenty that
threshold is over ten megabytes of text. It never fires, because the generator above it sends
exactly one chunk. Two problems canceling each other out, and the one that looks scarier is
the harmless one.

## Ask The API To Reject You

I mapped Deepgram's `/v2/speak` parameter surface without a key, because that endpoint
validates query parameters before it checks auth. Send a value that doesn't exist and the
server hands you the list:

```
$ curl -X POST "https://api.deepgram.com/v2/speak?model=flux-haley-en&encoding=flac16" ...
400 {"err_code":"INVALID_QUERY_PARAMETER",
     "err_msg":"unknown variant `flac16`, expected one of `linear16`, `mulaw`, `alaw`,
                `mp3`, `opus`, `flac`, `aac`"}
```

Same trick gets you the container values (`wav`, `ogg`, `none`), the fact that `sample_rate`
isn't allowed alongside `encoding=mp3`, and the exact bit rates mp3 accepts.

The trick has a limit, and I'd rather show it than let you find it later. `speed=3.0` comes
back 401, not 400. Range checks happen after auth, so an unauthenticated probe sees the enums
and nothing validated later in the request. Deepgram documents `speed` as 0.5 to 1.5 in 0.05
steps `[unverified: the range and the step. Probing can't reach it. Verified by sending
boundary values with a real key.]`

## Thirty Six Voices, One Language

`GET /v2/models` is public and unauthenticated, and it returns exactly 36 Flux voices. Every
one of them is English: `en`, `en-AU`, `en-GB`, `en-IE`, `en-IN`, `en-PH`, `en-SG`, `en-US`.

The older `GET /v1/models` returns 102 Aura models across seven base languages, and zero Flux
entries.

That's the constraint that decided the architecture. A Flux-only integration collapses
`supported_languages` to `["en"]` and takes the voice away from anyone running Assist in
German, Spanish, French, Italian, Japanese, or Dutch. So both families ship, and the model id
is the routing signal, because the API enforces the split itself:

```
$ curl -X POST "https://api.deepgram.com/v2/speak?model=aura-2-thalia-en" ...
400 {"err_code":"V1_MODEL_ON_V2_SPEAK_ENDPOINT",
     "err_msg":"Only flux models are supported on the `/v2/speak` endpoint."}
```

`flux-` prefixed models go to v2, everything else to v1, one synthesize signature and two
URLs.

This is also the kindest thing I can say about the fork's voice discovery, and it's true: it
isn't broken. It queries `/v1/models`, which has no Flux voices in it. No amount of correct
code in that module could have surfaced one. When a vendor ships a new model family on a new
API version, dynamic discovery against the old version keeps working and keeps being wrong.

One engineering note on defaults. The catalog carries accent, age, tags, and a playable sample
per voice, so a picker builds straight off it. I default to `flux-haley-en`. Two of the 36,
`flux-marcus-en` and `flux-brittany-en`, drift in pitch and volume between calls and can click
at the start of a clip `[unverified: this comes from Deepgram's own notes, not my listening
test. Verified by synthesizing the same greeting twenty times per voice and comparing.]` A
home assistant speaks in short bursts all day, which is where per-call drift is most audible.
That's a reason to default to something else, not a reason to leave them out of the picker.

## Declare It Anyway

The fork's `manifest.json` declares `"requirements": []` while the code imports
`async_timeout` and `pydub`. Neither is a Home Assistant dependency, so the obvious conclusion
is that the integration can't load.

I went to confirm that and it imported fine. The chain is worth following:

```
components/tts/manifest.json      "dependencies": ["http", "ffmpeg"]
components/ffmpeg/manifest.json   "requirements": ["ha-ffmpeg==3.2.2"]
ha-ffmpeg metadata                Requires-Dist: async-timeout    <- no marker
```

Every other package in my environment that wants `async-timeout` marks it
`python_version < "3.11"`, so on Home Assistant's Python 3.14 they contribute nothing.
`ha-ffmpeg` has no marker, and it arrives because the `tts` component depends on `ffmpeg`. The
undeclared import survives on a transitive dependency of the exact component it's extending.

So the better version of the rule isn't "declare your requirements or you won't load." It's
that an undeclared import makes your ability to load a property of somebody else's dependency
graph, and nobody sends you a note when that changes. My repo fails CI if a third-party import
appears without a matching manifest entry, which is a boring fix for a problem I'd rather not
diagnose from a user's log.

`pydub` has no such patron. It isn't required by anything in a working Home Assistant
environment, it isn't in the constraints file, and the fork's streaming path raises
`RuntimeError("pydub is not available to join mp3 fragments")` when it's absent. That one is
real, reproducible, and it's the half of the diagnosis that held up.

## What Chapter Six Has To Prove

Here's where I am, which is earlier than this post probably reads. There are three commits.
Chapter one is 314 lines, six passing tests against Home Assistant 2026.9.2, and a config
entry that loads. `async_get_tts_audio` currently raises an exception telling you chapter five
will implement it. **Nothing in this repo synthesizes audio yet**, and I have no Deepgram API
key on this machine, so nothing past an auth check has been exercised at all.

The design bet is the websocket. Deepgram's docs say the server places flush boundaries
internally, so a client streams tokens straight in and does no segmentation of its own
`[unverified: the entire protocol behavior. Nobody here has opened the socket. Verified by
one authenticated session logging the message sequence for a multi-sentence turn.]` If that
holds, the 206-line sentence splitter has no counterpart in my build. If it doesn't hold, those
206 lines are a workaround for a real problem and I need my own version of them.

That's the thing I want to test next, on the Raspberry Pi and not on this laptop, and I'm not
going to publish a latency number until I've measured one there with a sample size worth
quoting.

[fork]: https://github.com/alceasan/ha-deepgram-tts

---

## Editorial state of this draft

**Word count of the body:** 1,320 prose words, measured with code blocks stripped, against the
1,200 word `personal_blog` limit. **Over by 120 and it has to come down at Gate A.** The
`speed` caveat in "Ask The API To Reject You" and the two-paragraph split in "The Generator
That Wasn't" are the cheapest 120 words in the piece. Do not cut from "Declare It Anyway";
that section is the reversal and it needs its chain intact.

**Claims cut from this draft for lack of evidence:**

| Cut | Why |
| --- | --- |
| Any latency figure, including Deepgram's own marketed first-audio number | `F11.2`. Nothing measured on any hardware, and the vendor figure measures something else |
| "The integration did not load" | `F1.6`. The dependency chain in `F1.5` makes the opposite more likely |
| "We deleted 206 lines because the server does the work" | `F3.6`. That is a design bet until the socket is opened. Reframed as a bet in the last section |
| "About 180 lines survived the rewrite" | `F8.3` is an estimate from a repair plan and would read as a diffstat |
| Anything about installing it, a release, or a HACS listing | `F9.4`, `F11.6`. There is no release and no install path |
| Any before-and-after on perceived Assist latency | No measurement exists on either path |

**Inline `[unverified: ...]` markers still in the body:** three. The `speed` range, the
voice-drift observation, and the whole websocket protocol.

## de-slop pass

Run on the finished body on 2026-09-15, before handing it over.

**An honesty note about the table, because the skill's format invites a fake one.** The
de-slop rules were applied while drafting rather than as a separate rewrite, so there is no
pre-pass snapshot to count and no legitimate "before" column. What follows is a measured
census at two real points: the body as first written, and the body after the length trim.
Both were counted with the skill's own greps on the extracted body, code blocks included.

| Tell | As first written | After the trim |
| --- | --- | --- |
| DiGiorno construct (`is not X`, `, not Y`) | 2 | 3 |
| "worth ~ing" hedges | 1 | 1 |
| "rather than" lines | 1 | 0 |
| Flat openers (`That is` / `It is` / `This is` at a sentence start) | 1 | 1 |
| Contractions (this one should be high) | 47 | 45 |
| Em dashes | 0 | 0 |
| Words from the never-use list | 0 | 0 |

The DiGiorno count went **up** by one during the trim, which is the kind of thing this census
exists to catch. The added one is "That's a reason to default to something else, not a reason
to leave them out of the picker", and it stays, because the wrong assumption it preempts is
the one a reader will actually make about a voice with a known artifact. All three surviving
constructions preempt a specific wrong belief: that there is a flag for streaming support,
that the fork's voice discovery is buggy, and the voice-default one. Under the cap of three.

The one "worth" is "a sample size worth quoting," where it modifies the sample size instead of
hedging an insight, so it is not the tell.

**Step 7, reading every metaphor out loud and picturing it.** Six images in the body. **None
of them broke.**

- "where the contract is sharp" resolves. An edge you can cut yourself on.
- "two problems canceling each other out" resolves, and it is arithmetic more than an image.
- "`pydub` has no such patron" resolves, and it carries the section's argument: one package is
  sponsored by somebody else's dependency graph and the other is not.
- "the undeclared import survives on a transitive dependency" resolves. Something living on
  something else.
- "the design bet is the websocket" resolves, and the following two sentences pay it off by
  naming both outcomes of the bet.
- "be done by lunch" is an idiom rather than a metaphor and needs no picture.

**Deliberately left alone:** "chapter" appears repeatedly as this project's own term for a
build stage and stays consistent. "unverified" appears in all three inline markers by design,
because the marker is a format rather than prose. The header "The Generator That Wasn't" is
the one aphoristic flourish in the piece, and it is the only one.
