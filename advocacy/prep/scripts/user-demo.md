# user-demo.md, take 4 of 4

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy-intake` has not run, and no Gate D render batch exists.
> **This script cannot be rendered**, and it also cannot be **shot**. `script-to-video` needs
> `DEEPGRAM_API_KEY` (`F11.1`), and every beat below that plays the product needs a product
> that speaks plus a speaker to hear it on (`F9.4`, `F11.3`). This is the most blocked of the
> four takes and by a long way.

**Style contract:** `script-to-video/styles/user-demo.md`. A person who will never read the
code is deciding whether to use this. Leads with what it is in one sentence, then plays it.
Almost all internals cut: no file paths, no line numbers, no API parameters. Plain second
person, no engineering vocabulary. **Naturally the shortest take, and the contract says let it
be.** Runtime is bought with holds while the thing plays, never with more narration.

**Source material:** identical facts to the other three takes. Where the contract forbids
internals, the fact appears in its user-visible form rather than being dropped, so nothing
drifts: `F4.1` and `F4.2` become "thirty six voices, all English", `F4.4` becomes "if your
house speaks another language, you keep the voices you have", `F6.9` becomes the price,
`F9.4` and `F11.3` become "it does not work yet". `F2.1`, `F2.5`, `F6.2`, `F1.5`, and `F3.2`
are internals and are correctly absent from this take.

---

| # | Shot direction | Spoken line | Hold |
| --- | --- | --- | --- |
| 1 | Kitchen, ask the assistant a question, it answers in a Flux voice, no narration over it | This gives your Home Assistant voice assistant a better voice. Listen. | 8 |
| 2 | Same shot, ask a second question, longer answer plays out fully | That is the whole idea. Same assistant, same questions, different voice. | 10 |
| 3 | Screen, the voice list open, scrolling slowly through names and accents | You pick from thirty six voices. Each one has a sample you can play before you choose. | 4 |
| 4 | Tap a voice, hear its sample, tap another, hear that one | Try a few. They sound different from each other in ways that matter once you hear one every morning. | 9 |
| 5 | Select a voice, save, then ask the assistant the same question from beat 1 | Pick one, save, and your assistant sounds like that from then on. | 6 |
| 6 | Screen, the language setting visible, a non-English option selected | One thing to know before you install. All thirty six of these voices are English. If your assistant speaks Spanish, German, French, Italian, Japanese, or Dutch, you keep the voices you already have and these do not appear. | 3 |
| 7 | Screen, a plain card showing the price | It runs in the cloud and it is metered. Four and a half cents per thousand characters, as of September twenty twenty six. You need an account and a key. | 3 |
| 8 | Screen, the repository page, no install button | And the honest one. It is not finished. There is nothing to install yet, the voice you heard is a sample from the catalog rather than the integration running, and it cannot answer you out loud today. | 4 |
| 9 | Hold on the repo page, then cut to black | Follow the repo if you want to know when it can. | 0 |

---

## Runtime

Estimated with `words x 0.30 + sentences x 0.70`, computed over the table above. 9 beats, 186
spoken words, 19 sentences, 47 seconds of holds.

**Estimate: 1 minute 56 seconds**, of which only 1 minute 09 seconds is narration. Holds are
40 percent of the runtime, which is correct for a take that buys time by letting the thing
play. Shortest of the four by 88 seconds, as the contract intends. Treat it as a floor.

## Notes for whoever shoots this

- **Beats 1, 2, 4, and 5 do not exist yet and cannot be faked.** They need a working batch
  path on the real instance and a speaker in the room. Shooting a stand-in with a laptop
  speaker and calling it a home assistant is the exact thing this file refuses to plan for.
- Beat 8 is not an apology and should not be delivered as one. It is a fact about the state of
  the project, stated in the same register as the price.
- Beat 6 goes before the price and before the repo link on purpose. A user who speaks German
  should find that out in the first minute, not in a comment thread.
- The voice drift note from `F4.9` is deliberately **absent** from this take. It is engineering
  advice about choosing a default and means nothing to somebody browsing a picker.
- If beat 1 cannot be shot, the whole take waits. There is no version of a product demo that
  does not play the product.
