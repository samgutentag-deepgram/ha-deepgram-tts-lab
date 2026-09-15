# build-it-too.md, take 2 of 4

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and no Gate D render batch exists.
> **This script cannot be rendered.** `script-to-video` needs `DEEPGRAM_API_KEY` for both its
> TTS narration and its STT timing pass, and there is none on this machine (`F11.1`).

**Style contract:** `script-to-video/styles/build-it-too.md`. Second person. The viewer is
going to clone this, so every beat answers "what would I change here." Leads with the lowest
bar that is honestly true. Names line counts when they are small. Ends on a runnable command.

**Source material:** identical facts to the other three takes. `F2.1`, `F2.5`, `F6.2`, `F4.1`,
`F4.2`, `F4.4`, `F1.5`, `F1.3`, `F3.2`, `F9.4`.

---

| # | Shot direction | Spoken line | Hold |
| --- | --- | --- | --- |
| 1 | Editor showing the whole integration, six files in the tree | If you can subclass a Python class and read a JSON response, you can write a Home Assistant text to speech integration. The scaffold that loads is three hundred and fourteen lines across six files. | 0 |
| 2 | `entity.py` line 93, the method highlighted, cursor resting on the comparison | Read these six lines before you write anything. Home Assistant checks whether your class overrides one method and that is how it decides you support streaming input. | 3 |
| 3 | Same shot, then a diff view adding an empty `async_stream_tts_audio` to a class | So the moment you define that method, every response from the voice assistant goes through it. You do not get to write a rough version and test it later. | 2 |
| 4 | The two dataclasses on screen, `TTSAudioRequest` above `TTSAudioResponse` | Here is everything you have to honor. You take an async generator of text and you return an async generator of bytes plus a file extension. | 0 |
| 5 | The community integration's `message_gen`, the `texto +=` line highlighted | This is the seam to watch. The community integration by alceasan collects the whole generator into a string and yields once, which type checks fine and waits for the last token. If you write this method, that is the line you will accidentally write. | 4 |
| 6 | Terminal, curl with a bogus encoding, the enum in the response | Before you read any docs, ask the API to reject you. Send an encoding that does not exist and Deepgram hands you the list of the ones that do. | 3 |
| 7 | Terminal, curl with `speed=3.0` returning 401 | Know where that stops working. Range checks happen after auth, so out of range speed gives you four oh one and tells you nothing. Enums yes, ranges no. | 2 |
| 8 | `jq` over `GET /v2/models`, 36 rows, then the `languages` field on one | Both voice catalogs are public and need no key, so you can build a voice picker before you have an account. Thirty six Flux voices, every one English. | 3 |
| 9 | `models.py`, `family_for_model`, three lines on screen | This is the routing rule and it is three lines. Flux prefixed ids go to the v2 endpoint, everything else goes to v1, and the API rejects the wrong pairing before it checks your key. | 2 |
| 10 | Editor split: a `manifest.json` with an empty requirements array beside a file importing a third party package | Here is the one to copy from me rather than from the integration I read. If you import something, declare it in the manifest. | 0 |
| 11 | Terminal, the four command chain resolving `tts` to `ffmpeg` to `ha-ffmpeg` to `async-timeout` | Skip it and you might still work, which is worse. The tts component pulls in ffmpeg, which pulls in ha-ffmpeg, which asks for async timeout with no version marker, so an undeclared import survives on somebody else's dependency. | 5 |
| 12 | `python -c "import pydub"` failing | And it only takes one package without a sponsor to break you. pydub is in nobody's dependency tree, so the path that needs it raises every single call. | 3 |
| 13 | `scripts/manifest_check.py`, then a failing CI run on a deliberate bad import | Steal this file. Thirty lines of walking your own imports and comparing them to the manifest, wired into CI so the mistake cannot reach a user. | 0 |
| 14 | This repo's `tts.py`, the raising `async_get_tts_audio` | Clone it today and it will not speak. The entity raises on purpose until chapter five wires the batch endpoint. | 2 |
| 15 | The websocket protocol notes on screen, `Speak` and `Flush` messages visible | The part you would change if you disagree with me. The docs say the server places flush boundaries, so there is no sentence splitter in my design at all. Nobody here has opened the socket to confirm that. | 4 |
| 16 | Terminal, clone and test run, then hold on the passing output | Two commands to get where I am. Clone it, then run pytest, and six tests pass against Home Assistant twenty twenty six point nine point two. | 3 |

---

## Runtime

Estimated with `words x 0.30 + sentences x 0.70`, computed over the table above. 16 beats, 481
spoken words, 35 sentences, 36 seconds of holds.

**Estimate: 3 minutes 24 seconds**, of which 2 minutes 48 seconds is narration. Sixteen
seconds longer than the technical take, which matches the contract's "same as technical".
Treat it as a floor.

## Notes for whoever shoots this

- Beat 13 is the take's payoff for this style and it needs the real file on screen with the
  line count visible.
- Beat 15 hands the viewer the disagreement on purpose, which is what this style is for. Do
  not soften it into a claim.
- Beat 16 ends on a runnable command, per the contract. Show real output.
