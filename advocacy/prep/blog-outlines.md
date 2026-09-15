# blog-outlines.md, two outlines, one per branch

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and neither Gate A blog task exists in
> Asana. These are outlines for a campaign that has not started.

`advocacy-cycle` runs two blogs, one per branch, and the two branches are peers rather than a
pipeline. Mapping for this project:

| Branch | Surface | Limit | This outline |
| --- | --- | --- | --- |
| personal | `personal_blog` | 1,200 words | The technical build log. For a developer who might build the same thing |
| corporate | `corporate_blog` | 1,500 words | The Home Assistant community piece. For someone deciding whether to install it |

**Evidence marks used below:** `[HAVE]` cited in `notes.md` with a live or source-verified
tag. `[VENDOR]` in `notes.md` as a vendor claim, so it ships labeled or not at all.
`[MISSING]` does not exist and blocks that section.

---

# Outline 1, personal branch: the technical build log

**Audience:** a developer who writes Python, has a Home Assistant instance, and might build a
TTS integration or is maintaining one now.

**Argument of the whole piece:** the interesting part of wiring a new speech API into Home
Assistant is not the HTTP call. It is a set of contracts that are easy to satisfy on paper and
hard to satisfy correctly, and reading an existing integration against those contracts is the
fastest way to find them.

**What this piece is not:** a launch, a demo, or a result. `F9.4` means there is no synthesis
in the repo. The ending is what gets tested next.

## Section 1: I Read 858 Lines Before Writing One

Argument: the project starts with an audit, not a plan, because the community integration
already encodes what the problem is. State the situation plainly in three sentences: there is
an existing integration by `alceasan`, it is eight months cold, and Flux TTS is a different
endpoint with a different protocol.

Evidence: `F8.1` 858 lines counted `[HAVE]`. `F8.5` environment drift `[HAVE]`. Prior-art
credit to `alceasan/ha-deepgram-tts` in the first mention `[HAVE]`.

## Section 2: One Method Is The Whole Opt-In

Argument: **the strongest section in the piece, and it goes second so it lands before any
reader leaves.** Home Assistant infers streaming support by comparing your class method
against the base class method, so the act of defining `async_stream_tts_audio` routes every
Assist response through it. Quote the six lines. Then explain the failure shape that produces:
`tts.speak` works, the voice assistant raises.

Evidence: `F2.1` with the source quote `[HAVE]`. `F2.2` and `F2.3` `[HAVE]`. `F2.4` the two
dataclasses `[HAVE]`.

## Section 3: The Generator That Wasn't

Argument: the streaming contract is small enough to satisfy accidentally. Show the fork's
`message_gen` accumulating the whole response into one string and yielding once. It matches
the type signature exactly. Frame as a property of the contract, not as a confession by
anybody.

Evidence: `F2.5` with the code quote and line range `[HAVE]`. `F2.6` `[HAVE]`.

## Section 4: Ask The API To Reject You

Argument: the parameter surface was mapped without a key, because query-parameter validation
runs before auth on this endpoint. Show two live rejections that quote the enums back. Then
show the limit of the trick immediately: `speed=3.0` returns 401, because range validation
happens after auth, so an unauthenticated probe sees the enums and nothing checked later.

Evidence: `F6.1` to `F6.5` `[HAVE]`. `F6.6` the limit `[HAVE]`. `F6.7` the range as
documentation rather than measurement `[VENDOR]`, ships labeled.

## Section 5: Thirty Six Voices, One Language

Argument: the constraint that shaped the architecture. 36 Flux voices, all English, against
102 Aura models across seven languages, and zero Flux entries in the older catalog. So both
families ship, routing is by model prefix, and a non-English pipeline must never resolve to
Flux. Include the kind finding: the fork's discovery is not broken, it queries the catalog
that does not contain Flux.

Evidence: `F4.1` to `F4.5` `[HAVE]`. `F5.1` the `V1_MODEL_ON_V2_SPEAK_ENDPOINT` rejection
`[HAVE]`. `F5.3` `[HAVE]`.

## Section 6: Declare It Anyway

Argument: the dependency finding, told as the reversal it was. The manifest declares no
requirements while the code imports two packages. The obvious conclusion is that it cannot
load. Then the chain: `tts` depends on `ffmpeg`, which requires `ha-ffmpeg`, which asks for
`async-timeout` with no environment marker. So it probably does load, on somebody else's
dependency graph. pydub has no such patron and the streaming path raises every time.

Evidence: `F1.1` to `F1.5` `[HAVE]`. `F1.6`, which forbids the simpler framing `[HAVE]`.
`F1.9` the CI check in this repo `[HAVE]`.

## Section 7: What Chapter Six Has To Prove

Argument: the honest ending. The socket design says the server places flush boundaries, which
is what makes a sentence splitter unnecessary. That is documentation, not a result. State what
gets measured and on what hardware, and state that the entity currently raises.

Evidence: `F3.1` and `F3.2` `[VENDOR]`, ship labeled as untested. `F3.3` the 206 lines
`[HAVE]`. `F9.4` the placeholder entity `[HAVE]`. `F11.1` to `F11.4` `[HAVE]` as stated
holes.

**`[MISSING]` for this section, and it is deliberate:** the socket message sequence, any
latency number, and any hardware result. The section exists to say they are missing.

## Wrap Up

One short paragraph. What is on disk, what is next, no conclusion that claims a shipped
integration. Link the repo and the HA TTS entity source.

**Budget:** 1,200 words. Sections 2 and 6 get the most room. Section 1 stays under 150.

---

# Outline 2, corporate branch: the Home Assistant community piece

**Audience:** a Home Assistant user who wants a better voice for their assistant and will not
read any Python.

**Gate status, stated up front:** `corporate_blog` is earned when the claim is proven rather
than simulated. Today it is not. `F9.4` means there is no synthesis, `F11.3` means there is no
speaker, and `F11.6` means nothing has been installed. **This outline is the shape to write
into once chapters 2 to 5 run on real hardware. It cannot be drafted today, and that is the
correct answer rather than a scheduling problem.**

Recorded so the shape is ready the day the evidence lands.

## Section 1: Your Assistant Can Sound Like A Person

Argument: lead with the artifact. What it is in one sentence, then audio. A Home Assistant
integration that uses Deepgram Flux TTS as the voice of your Assist pipeline.

Evidence: **`[MISSING]`** an audio sample of the integration answering a real question on real
hardware. Nothing else in this section works without it. Blocked on `F11.1`, `F11.3`,
`F11.6`.

## Section 2: Pick A Voice, Any Of Thirty Six

Argument: the voice picker is the feature a user cares about. 36 Flux voices, each with an
accent, an age, and a playable sample in the catalog. The shipped default is Haley.

Evidence: `F4.1`, `F4.2`, `F4.6` `[HAVE]`, including the sample URLs, which means voice
samples can be embedded without hardware. `F4.7` the default `[HAVE]`.
`[MISSING]` screenshots of the picker, which need chapter 4 landed and installed.

This is the one section with real evidence today, which is worth knowing: the catalog is
public, so the voice-browsing content can be built before the integration works.

## Section 3: If You Don't Speak English

Argument: honest limits, stated as facts rather than apologies, and stated early rather than
in a closing caveat. Every Flux voice is English. If your assistant runs in German, Spanish,
French, Italian, Japanese, or Dutch, the integration serves you an Aura-2 voice and the
Flux voices will not appear. Nothing is taken away, and the new voices are English only.

Evidence: `F4.2`, `F4.3`, `F4.4` `[HAVE]`. Fully supported today.

## Section 4: What It Costs

Argument: cloud TTS is metered and a user is entitled to know before installing. Flux TTS is
$0.045 per 1,000 characters as of 2026-09-15, and the date ships with the number.

Evidence: `F6.9` `[VENDOR]`, cited with its date.
`[MISSING]` any real usage figure, such as what a week of ordinary assistant use actually
costs. That needs the integration running on hardware and would be the most useful number in
the whole piece.

## Section 5: Install It

Argument: HACS custom repository, add the key, pick a voice, restart, choose it in your Assist
pipeline. Numbered steps, imperative mood, no explanation of why HACS works the way it does.

Evidence: **`[MISSING]`** the entire section. There is no release, no tag, and no install path.
Blocked on chapter 7 per `F9.8`.

## Section 6: What It Doesn't Do Yet

Argument: the limits a user will hit, as a list of facts. No barge-in, because HA's TTS entity
API has no hook for it today. English only for the Flux family. Cloud, so it needs network.

Evidence: `F5.4`, the barge-in scope note `[HAVE]` for the missing HA hook, `[VENDOR]` for the
`SpeechInterrupted` fields. `F4.2` `[HAVE]`.
`[MISSING]` behavior when the network drops mid-response, which needs the batch fallback in
chapter 6 tested.

## Wrap Up

Where to file issues, what is coming next, and that it is a custom integration rather than a
core one.

**Budget:** 1,500 words. Sections 1, 2, and 5 carry the piece. Section 3 stays short and
early.

---

## Evidence that blocks both outlines

| Needed by | Missing thing | Unblocked by |
| --- | --- | --- |
| Outline 1, section 7 | Websocket message sequence for a real multi-sentence turn | An API key, then one logged session |
| Outline 1, section 7 | Confirmation that the server places flush boundaries | Same session |
| Outline 2, sections 1 and 5 | Audio from the real instance, and an install path | Chapters 2 to 5 landed, installed, plus a speaker |
| Outline 2, section 4 | A real cost figure for ordinary use | A week of real usage with billing visible |
| Both, nowhere | Any latency number | Deliberately absent. `F11.2` forbids it, and it stays forbidden until measured with a sample size |

Outline 1 can be drafted today and is drafted in `blog-technical-draft.md`. Outline 2 cannot.
