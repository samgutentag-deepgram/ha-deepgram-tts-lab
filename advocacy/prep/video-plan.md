# video-plan.md, the slate

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and no Gate D render batch exists. Nothing
> here is scheduled and nothing here has been shot.

Six videos across three formats. Every one is blocked on something, and the blockers are the
useful part of this file.

## Two dependencies that block the whole slate

**1. Hardware Sam does not own.** `F11.3`: zero speaker devices today. A Home Assistant voice
assistant that cannot speak out loud cannot be filmed doing the thing it exists to do. Five of
the six videos below need a speaker in frame. This is the single largest blocker on the slate
and no amount of scripting moves it.

**2. No Deepgram API key on this machine.** `F11.1`: `DEEPGRAM_API_KEY` is unset. This blocks
the work twice over:

- Nothing in the integration can synthesize, so there is no audio to record (`F9.4`).
- **`script-to-video` cannot render a base layer.** It narrates with Deepgram TTS and drives
  its karaoke timing by sending that audio back through Deepgram STT, so the renderer needs
  the same key. With no key there are no animatics, no timing references, and no scratch cuts.
  The scripts in `scripts/` are therefore text deliverables today and not render inputs.

Everything below assumes both get solved. Neither is solved.

## Orientation, and what the cycle will and will not do

`advocacy-cycle` renders Gate D horizontal only, and it states that vertical is out of scope
and gets extracted by hand when a clip earns it. So the vertical shorts on this slate are
hand-cut work outside the cycle, which is why they carry their own row rather than hiding
inside the long-form entry.

Video derives from the personal blog only, per the same skill. There is no corporate video
surface, and proposing one would put a Gate D batch under a branch that has no video script.

---

## V1. The build log

| | |
| --- | --- |
| **Format** | Long-form screen capture with a talking-head cold open and outro |
| **Target length** | 11 to 14 minutes. Under the `personal_video_script` 15 minute limit |
| **Platform** | YouTube, own channel |
| **Audience** | Python developers who own a Home Assistant instance. The same reader as the technical blog |
| **Goal** | The viewer understands Home Assistant's streaming TTS contract well enough to avoid the opt-in trap in their own integration. Call to action is the repo |
| **On camera** | Cold open to camera, roughly 45 seconds. Then screen: the six lines of `async_supports_streaming_input`, the fork's `message_gen`, a terminal running the curl probes live, and the config flow voice picker. Outro to camera |
| **Needs before shooting** | Chapters 2 to 5 landed and installed on the real instance. An API key, so the curl probes return real audio rather than 401. A speaker, for the one shot where it answers a question out loud. Chapter 6 **not** required, since the honest ending is what gets tested next |
| **Blocked on hardware** | Partially. The curl probes, the source reading, and the config flow all film without a speaker. The single "ask it something" shot does not |

The cold open is the piece of this that cannot be reshot cheaply: the first time it answers out
loud on real hardware. Hub init scaffolds a `Capture the first time it works` task for exactly
that moment, and a recording started afterwards is a reenactment.

## V2. The short demo

| | |
| --- | --- |
| **Format** | Single continuous take, screen plus room audio, no cuts |
| **Target length** | 60 to 90 seconds |
| **Platform** | YouTube, embedded in both blogs, and the LinkedIn post as a voiceless version with captions |
| **Audience** | Someone deciding in the first ten seconds whether this is worth their evening |
| **Goal** | Show the artifact working. No mechanism, no file paths, no API parameters |
| **On camera** | The Assist pipeline being asked something, the speaker answering, the voice picker showing a different voice, the same question answered in that voice. One take |
| **Needs before shooting** | A speaker. Chapter 5 installed and working on the real instance. At least two voices selectable, so the voice switch is real rather than described |
| **Blocked on hardware** | **Yes, completely.** This video is the speaker |

One continuous take on purpose. A cut in a 60 second demo of a voice assistant reads as hiding
a retry, and this is the video most likely to be watched by somebody skeptical that it works
at all.

## V3. The audit walkthrough

| | |
| --- | --- |
| **Format** | Screen capture, no camera, editor and terminal only |
| **Target length** | 6 to 8 minutes |
| **Platform** | YouTube, own channel |
| **Audience** | Developers who inherit codebases. Wider than the Home Assistant audience |
| **Goal** | Teach two transferable things: the streaming opt-in trap, and following a dependency chain to find out that the obvious diagnosis was wrong |
| **On camera** | Nothing. `entity.py:93-98` on screen, the fork's buffered generator, then the five commands that trace `tts` to `ffmpeg` to `ha-ffmpeg` to `async-timeout` |
| **Needs before shooting** | **Nothing that does not already exist.** Every fact in it is `LIVE` or `SOURCE` in `notes.md` today, and none of it needs a key, a speaker, or a working integration |
| **Blocked on hardware** | **No.** This is the only video on the slate that could be shot this week |

The one to shoot first, and the reason to notice that the most defensible video on the slate is
the one with no product in it. It also carries the whole prior-art tone risk, since seven of
its eight minutes are somebody else's code on screen. Script accordingly, and credit
`alceasan/ha-deepgram-tts` in the first fifteen seconds rather than in a description.

## V4 to V6. Vertical shorts, one reel cut into clips

| | |
| --- | --- |
| **Format** | Vertical 1080x1920, hook plus payoff plus call to action per clip, cut from one render |
| **Target length** | 6 clips at a 30 second target for Reels and TikTok. A separate 8 to 10 clip pass at a 15 second target if Stories is wanted, because its card is a hard 15 seconds |
| **Platform** | Reels, TikTok, YouTube Shorts |
| **Audience** | Cold scroll. Assume no context and no prior clip watched |
| **Goal** | One surprising fact per clip, pointing at the repo or the long-form video |
| **On camera** | Nothing for four of them, screen recordings with large type. Two want a face for the hook |
| **Needs before shooting** | The `script-to-video` renderer, which needs the key. Then hand cutting, since the cycle renders horizontal only |
| **Blocked on hardware** | Four of six are not. The two that show the speaker answering are |

Clip topics, each self-contained, each already supported by a `LIVE` or `SOURCE` fact:

1. Defining one method is the entire opt-in for streaming TTS (`F2.1`). No hardware.
2. Send an API a parameter value that does not exist and it hands you its schema (`F6.2`). No
   hardware.
3. Thirty six voices and every one of them is English (`F4.1`, `F4.2`). No hardware.
4. The generator that satisfies the type and buffers everything anyway (`F2.5`). No hardware.
5. The voice picker, browsing and auditioning voices. **Needs a speaker.**
6. Asking the assistant something and hearing it answer. **Needs a speaker.**

Clips 1 to 4 are shootable against today's facts. That is worth stating plainly: two thirds of
the vertical slate does not depend on the integration working.

Holds stay at 3 seconds or get dropped in vertical. A long hold on a social clip is dead air
and it masks the cut points the render exists to mark.

---

## Slate summary

| # | Video | Length | Blocked on a speaker | Shootable today |
| --- | --- | --- | --- | --- |
| V1 | Build log | 11 to 14 min | One shot only | No. Needs chapters 2 to 5 |
| V2 | Short demo | 60 to 90 s | Yes, entirely | No |
| V3 | Audit walkthrough | 6 to 8 min | No | **Yes** |
| V4 | Shorts, clips 1 to 4 | 4 x ~30 s | No | Yes, once the renderer has a key |
| V5 | Shorts, clip 5, voice picker | ~30 s | Yes | No |
| V6 | Shorts, clip 6, it answers | ~30 s | Yes | No |

## What to buy and what to ask for

- **A speaker device.** Anything that works as a Home Assistant Assist satellite. This unblocks
  V2, V5, V6, and the best shot in V1. Cheapest unblock on the slate by a wide margin.
- **A Deepgram API key in the environment.** Unblocks all synthesis, and separately unblocks
  every `script-to-video` render including the timing references for V1.
- **Chapter 5 on the real instance.** The gate for intake per HANDOFF section 8.5, and the gate
  for four of the six videos here.
