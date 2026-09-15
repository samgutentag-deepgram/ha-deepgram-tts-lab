# Capture plan

What to point a camera at, and when. Filled in before the first irreversible success, never
rewritten after it.

The generic half, which is the same for every project:

- **What has to be in frame, and why a screen recording will not do.** If the thing is physical,
  a screen recording is a picture of a terminal and not of a house.
- **What has to be running so the terminal output is a file and not a memory.** Decide the
  capture command before the moment, not during it.
- **Record the failed attempts, in order, narrating what changed between them.** Those clips are
  worth more than the success clip, because everyone has seen a demo that works.
- **If it works first try, say so. Do not manufacture struggle.**

---

## The one-time events in this project

Three firsts, in the order they will happen. None has happened yet.

### 1. First authenticated round trip

Chapter 2's verification. `scripts/live_check.py` against both `/v2/speak` and `/v1/speak` with
a real key. Not filmable and not interesting on camera, but the terminal output is evidence and
it is worth one `asset` entry in the ledger.

- Capture: `script -q .hub/assets/first-round-trip.log scripts/live_check.py`, plus the two
  audio files it writes.
- Blocked on: a `DEEPGRAM_API_KEY` in the environment. There is none on this machine.

### 2. First time Flux speaks in the house

The one that matters. A `tts.speak` call on the real Home Assistant instance producing audible
sound out of a physical speaker. This is the shot the whole campaign rests on and it happens once.

- **Filming this needs a decision made before it happens, not after.** The audio is the payload,
  so the room has to be quiet and the microphone recording the room cannot be the laptop's.
- In frame: the speaker, visibly, and a person in the room. A screen recording of Developer Tools
  is the wrong shot; it proves nothing a viewer cares about.
- Also capture, separately and at the same time: the Home Assistant log filtered to
  `deepgram_tts`, and the HA UI showing the service call. Those are cutaways, not the A roll.
- Blocked on: chapter 5, a deployed integration, an API key, and a speaker. Sam owns zero
  speaker devices today, which is why the hardware bill of materials exists.

### 3. First streaming turn, and the number under it

Chapter 6. Time from the first `Speak` frame to the first audio frame, measured on the target
hardware and not on a laptop. Deepgram's marketing claims as low as 80 ms; that is a claim to
test, not a fact to repeat.

- Capture the measurement as a file, with the hardware named in it. A latency number with no
  hardware attached is not usable in a post.
- Also capture the failure case deliberately: kill the socket mid turn and show it degrading to
  batch rather than raising. **That clip is worth more than the happy path**, because a demo that
  survives being broken on camera is the only kind anybody believes.
- Blocked on: chapter 5 running on real hardware, per the gate in HANDOFF section 6.
