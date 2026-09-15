# fun.md, take 3 of 4

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and no Gate D render batch exists.
> **This script cannot be rendered.** `script-to-video` needs `DEEPGRAM_API_KEY` for narration
> and for its timing pass, and there is none on this machine (`F11.1`).

**Style contract:** `script-to-video/styles/fun.md`. Somebody made a thing they like and wants
to show you. First person, contractions throughout, leads with the friction. Everyday detail
that places the thing in a real life. One self-aware aside per beat at most, and this is the
only take where a parenthetical earns its place. Slightly longer than the technical take,
because warmth costs words.

**Source material:** identical facts to the other three takes. `F2.1`, `F2.5`, `F6.2`, `F4.1`,
`F4.2`, `F4.4`, `F1.5`, `F1.3`, `F3.2`, `F9.4`. Warmth changes the framing, never a number.

---

| # | Shot direction | Spoken line | Hold |
| --- | --- | --- | --- |
| 1 | Handheld, kitchen, asking the existing assistant for the weather, flat robotic answer plays | I ask my house what the weather's doing roughly twice a morning, and every single time it answers like a parking garage. That's the whole reason this project exists. | 3 |
| 2 | Cut to desk, browser open on the community integration's GitHub page | There's already a Deepgram integration for Home Assistant. Somebody named alceasan wrote it, people installed it, and it does the job it was built for. My plan was to fork it before breakfast and get on with my day. | 2 |
| 3 | Editor, the fork open, `wc -l` output showing 858 in the terminal | Eight hundred and fifty eight lines. I read all of them, which was not the plan, and I'm glad I did because it taught me more about Home Assistant than the docs did. | 3 |
| 4 | `entity.py` scrolled to line 93, six lines on screen, zoomed in | This is my favourite six lines in Home Assistant. It works out whether your integration can stream text by checking if you overrode one method. | 3 |
| 5 | Same shot, highlight moving between the two sides of the comparison | That's it. That's the whole opt-in. Write the method and every single thing your voice assistant says goes down that path immediately (there's no flag, I looked). | 2 |
| 6 | The community integration's `message_gen` on screen | So here's the bit I find genuinely lovely, in a sad way. This function collects every chunk into one string and then yields it. It's a perfectly valid async generator that waits for the whole answer before it starts. | 4 |
| 7 | Terminal, curl with a nonsense encoding value, error on screen | I didn't have an API key when I started, so I spent an afternoon being wrong at Deepgram on purpose. Ask for an encoding that doesn't exist and it just tells you all the real ones. | 3 |
| 8 | Terminal, `speed=3.0` returning 401 | It stops helping eventually. Speed out of range gives you a bored four oh one, because it checks your key before it checks your numbers. | 2 |
| 9 | Browser with the voice catalog, clicking through sample WAVs, a couple playing | And then there's this, which is the most fun I've had all week. Thirty six voices, all public, each with a playable sample, and I listened to every one of them instead of doing the work. | 5 |
| 10 | Same browser view, a language field visible reading `["en", "en-US"]` | Here's the catch, and it's a real one. Every Flux voice is English. If your house speaks Spanish or German or Japanese, this family has nothing for you and you stay on the older one. | 3 |
| 11 | Editor, `family_for_model`, three lines | Which is why there are two endpoints and a three line function that picks between them. Not glamorous. Does the job. | 2 |
| 12 | Terminal, `import pydub` failing, then `import async_timeout` succeeding | Then I went to prove why the old one was broken and accidentally proved it probably isn't. The import I was sure would fail worked fine, because the tts component drags in ffmpeg, which drags in the thing it needed. | 4 |
| 13 | Same terminal, scrolled to the pydub failure | The other one really is missing though, so the streaming path does fall over. One out of two, which is about my hit rate on confident diagnoses. | 3 |
| 14 | This repo's `tts.py`, the raising method, exception message readable | Now the honest part. Clone my repo today and it says nothing at all, out loud, to anybody. The entity raises an exception that tells you which chapter will fix it. | 3 |
| 15 | The websocket notes on screen, `Speak` and `Flush` visible | The bit I'm actually excited about is that the server decides where the sentences break, so there's no splitter in my version. That's what the docs say. I haven't opened the socket yet, so for now it's a nice idea I like. | 4 |
| 16 | Back in the kitchen, empty counter where a speaker would sit, shrug to camera | I also don't own a speaker. So the next thing on the list isn't chapter six, it's a shopping trip. | 2 |

---

## Runtime

Estimated with `words x 0.30 + sentences x 0.70`, computed over the table above. 16 beats, 505
spoken words, 39 sentences, 48 seconds of holds.

**Estimate: 3 minutes 46 seconds**, of which 2 minutes 58 seconds is narration. The longest of
the four takes, which is what the contract asks for. Treat it as a floor.

## Notes for whoever shoots this

- Beat 1 needs the current assistant voice audible and unflattering, which is the whole hook.
  No speaker required for that one, since it's whatever is answering today.
- Beat 9 is the delight beat and should run long. Let two voices actually play.
- Beat 16 is the ending and it is a joke at my own expense rather than at anybody's code. Keep
  it there. It also happens to be the most useful fact in the take.
- Beat 13's "one out of two" is about my own diagnosis, not about the integration I read.
  That distinction is the difference between this take being warm and being smug.
