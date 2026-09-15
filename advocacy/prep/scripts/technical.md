# technical.md, take 1 of 4

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and no Gate D render batch exists.
> **This script cannot be rendered.** `script-to-video` narrates with Deepgram TTS and times
> its karaoke pass with Deepgram STT, and there is no `DEEPGRAM_API_KEY` on this machine
> (`F11.1`). It is a text deliverable until a key exists.

**Style contract:** `script-to-video/styles/technical.md`. Declarative, present tense, the code
is the subject. Describes what the thing does and how it is built. **No lessons-learned
framing, no sentence whose subject is my own growth.** Bugs appear as properties of the stack.

**Source material:** the same facts as the other three takes. `F2.1`, `F2.5`, `F6.2`, `F4.1`,
`F4.2`, `F4.4`, `F1.5`, `F1.3`, `F3.2`, `F9.4`. A style changes framing and never a claim.

**One beat per shot change.** The third column is seconds of silence held after the line, where
the real edit sits in silence.

---

| # | Shot direction | Spoken line | Hold |
| --- | --- | --- | --- |
| 1 | Title card, then `custom_components/deepgram_tts/` open in the editor, tree visible | A Home Assistant integration that makes Deepgram Flux TTS the voice of an Assist pipeline. Two model families, one entity, and a websocket the server controls the pacing of. | 0 |
| 2 | `homeassistant/components/tts/entity.py` scrolled to line 93, the method highlighted | Home Assistant decides whether a text-to-speech entity accepts streaming input by comparing the subclass method against the base class method. | 3 |
| 3 | Same file, cursor on `async_stream_tts_audio` in the comparison | Defining that method is the opt-in. There is no flag and no manifest key, so every Assist response routes through it as soon as it exists on the class. | 2 |
| 4 | Split view, `TTSAudioRequest` and `TTSAudioResponse` dataclasses side by side | The contract is two dataclasses. A generator of text chunks in, a generator of audio bytes out, and an extension string that tells Home Assistant what it received. | 0 |
| 5 | The community integration's `tts.py`, scrolled to the `message_gen` function | The community integration by alceasan implements that method by accumulating every chunk into one string and yielding it once. The type signature is satisfied and the first synthesis call waits for the last token. | 4 |
| 6 | Terminal, run the curl with `encoding=flac16`, error response on screen | Deepgram's v2 speak endpoint validates query parameters before it checks auth. An encoding value that does not exist returns the full enum: linear16, mulaw, alaw, mp3, opus, flac, aac. | 3 |
| 7 | Terminal, run the curl with `speed=3.0`, 401 on screen | Range checks run after auth. Speed out of bounds returns four oh one, so an unauthenticated probe reaches the enums and nothing validated later in the request. | 2 |
| 8 | Browser or `jq` output of `GET /v2/models`, the 36 entries scrolling | The Flux catalog is public and returns thirty six voices. Every one of them is English. The v1 catalog returns one hundred and two Aura models across seven base languages and zero Flux entries. | 3 |
| 9 | `models.py`, `family_for_model` highlighted, then the `V1_MODEL_ON_V2_SPEAK_ENDPOINT` response in the terminal | The model id is the routing signal. Flux prefixed models go to v2, everything else goes to v1, and the API enforces the split itself before it authenticates. | 2 |
| 10 | Editor, the community integration's `manifest.json` with `"requirements": []` selected | That integration declares no requirements while importing async timeout and pydub. Neither is a Home Assistant dependency. | 0 |
| 11 | Terminal, four commands in sequence: the tts manifest, the ffmpeg manifest, `pip show ha-ffmpeg`, then `import async_timeout` succeeding | The tts component depends on ffmpeg. The ffmpeg component requires ha-ffmpeg. ha-ffmpeg requires async timeout with no environment marker, so the undeclared import resolves on a transitive dependency of the component being extended. | 5 |
| 12 | Terminal, `python -c "import pydub"` failing with ModuleNotFoundError | pydub has no such dependency behind it. It is absent from the environment and from the constraints file, and the streaming path raises on every call that reaches it. | 3 |
| 13 | `scripts/manifest_check.py` on screen, then the CI run passing | This build declares no third party requirements and a check fails the build if an undeclared import ever appears. | 0 |
| 14 | `tts.py` in this repo, `async_get_tts_audio` raising, the exception message visible | The entity in this repository raises. Chapter five wires the batch endpoint and chapter six wires the socket, and neither has run on hardware. | 4 |
| 15 | The Flux websocket protocol section of the handoff document on screen | The design rests on the server placing flush boundaries internally, which removes client side sentence segmentation entirely. That behavior is documented and untested here, because no socket has been opened. | 3 |
| 16 | `git log --oneline`, three commits, then cut to black | Three commits, three hundred and fourteen lines, six passing tests against Home Assistant twenty twenty six point nine point two. The next measurement is first frame timing on the target hardware. | 0 |

---

## Runtime

Estimated with the skill's formula, `words x 0.30 + sentences x 0.70`, computed over the table
above rather than guessed. 16 beats, 441 spoken words, 32 sentences, 34 seconds of holds.

**Estimate: 3 minutes 08 seconds**, of which 2 minutes 34 seconds is narration. Treat it as a
floor. Presenting to camera runs slower than
synthesis, and beats 6, 7, 11, and 12 are live terminal commands whose real duration depends
on the network.

## Notes for whoever shoots this

- Beats 6, 7, 11, and 12 are live commands and want real output on screen, not a paste of it.
  If the network is slow, cut the wait rather than faking the response.
- Beat 5 is the only beat about somebody else's code and it names alceasan in the line. Keep
  that. The finding is about the contract being easy to satisfy on paper.
- No latency number appears anywhere in this script. Beat 16 names what will be measured, and
  that is the whole claim available.
