# Chapter 3 notes: the voice catalog

Written 2026-09-15, while building `catalog.py`. Notes an agent reads, so this stays markdown.

## What I chose

- **One timeout around both fetches.** `asyncio.gather` inside a single `asyncio.timeout`
  (`TIMEOUT_CATALOG`), so setup waits 15 seconds total rather than 15 per endpoint. Only
  `ClientError` and `TimeoutError` become `DeepgramConnectionError`; anything else escapes as
  itself rather than being laundered through the wrong error class.
- **Flux is merged first.** That makes the collision rule fall out of insertion order instead of
  needing a family comparison, and it leaves the dict in a Flux-before-Aura order that matches
  how the picker reads. A collision warns and keeps what is already there.
- **One place splits a language code.** `_base_code` in `catalog.py`, plus
  `VoiceInfo.base_languages` in `models.py`, and both split on `-`. Input is lowercased, so an
  Assist pipeline handing over `EN-us` still matches.
- **Voice resolution is a four step ladder:** the preferred voice when it exists and can speak
  the language, then `DEFAULT_VOICE` when the base code is English, then the first Aura voice
  for the language, then the first voice of any family but only when the base code is English.
  That last step is guarded on the language code rather than on the voice family on purpose. If
  Deepgram ever mislabels a Flux voice with a non-English language, settled decision 4 still
  holds without anyone having to notice.
- **Malformed entries are skipped one at a time.** A non-object entry, or one with no
  `canonical_name`, is logged at warning and dropped. Nothing else in a payload is lost with it.
  `_optional_string` treats `null`, `""`, and whitespace as absent, which matters because the
  live catalog uses `null` rather than omitting keys.

## What surprised me

1. **`metadata.display_name` is `null` for 61 of the 102 Aura entries.** The key is present and
   the value is null, so a plain `"display_name" in metadata` check would have passed and then
   put `None` into the UI. The title-cased `name` fallback is the normal path for most of the
   Aura list, not a defensive edge case. Handoff 3.3 shows a Flux entry, where the field is
   always populated, so the handoff is not wrong, just unrepresentative. All 36 Flux entries
   have a real display name; the nulls are 49 `aura-2` and all 12 legacy `aura` voices.
2. **English has 89 voices once merged**, 36 Flux plus 53 Aura. So the Aura fallback inside
   `resolve_voice` for English is a real branch with real voices behind it, not a theoretical
   one.
3. **`/v1/models` is 183 KB, and 445 of its entries are `stt` models we throw away.**
   `/v2/models` is 22 KB with 2 `stt` entries. Both are parsed for their `tts` key only. Worth
   remembering if catalog fetch time on a Raspberry Pi ever shows up as slow setup.
4. **`metadata` also carries `color` and `image`**, neither of which is in the handoff's example
   entry. Unused here, but a voice picker with avatars is sitting right there.

## Live catalog against handoff section 3.3

Fetched with `curl` against `api.deepgram.com` on 2026-09-15, no auth header, both HTTP 200.

| Handoff claim | Live | Verdict |
| --- | --- | --- |
| `/v2/models` returns exactly 36 voices | 36 | match |
| all 36 are `architecture: "flux-tts"` | 36 of 36 | match |
| the 36 Flux ids listed in 3.3 | identical, id for id | match |
| Flux language set `en, en-AU, en-GB, en-IE, en-IN, en-PH, en-SG, en-US` | same 8 codes | match |
| `/v2/models` contains only Flux | 36 `flux-` ids, 0 others | match |
| `/v1/models` returns 102 TTS models | 102 | match |
| 90 `aura-2` plus 12 legacy `aura` | 90 and 12 | match |
| Aura language set, the 22 codes listed in 3.3 | same 22 codes | match |
| `/v1/models` contains zero Flux entries | 0 | match |
| payload is `{"stt": [...], "tts": [...], "languages": {...}}` | both endpoints | match |

**Nothing drifted.** Section 3.3 is accurate as written. Running the real merge over the live
payloads gives 138 voices, zero key collisions, and `supported_languages` of
`['de', 'en', 'es', 'fr', 'it', 'ja', 'nl']`. Live resolution with no preference: `en` and
`en-US` both pick `flux-haley-en`, and `es`, `de`, `fr`, `nl`, `it`, `ja` pick
`aura-2-agustina-es`, `aura-2-aurelia-de`, `aura-2-agathe-fr`, `aura-2-beatrix-nl`,
`aura-2-cesare-it`, `aura-2-ama-ja`. The voice list is fetched at runtime and no part of it is
hardcoded, so these numbers are a check on the handoff, not an input to the code.

## Still unverified

1. **Nothing here has been authenticated.** Both model endpoints are public, so chapter 3 is
   fully verifiable without a key, but that also means chapter 3 proves nothing about whether
   any of these 138 voices actually synthesize. Handoff section 7 item 1 is still open.
2. **The 12 legacy `aura` voices are in the merged catalog and untested.** They carry no
   `display_name`, they route to `/v1/speak` by prefix like any other non-Flux model, and
   whether Deepgram still serves them is a chapter 5 question.
3. **Fallback display names have not been eyeballed against Deepgram's own UI.** Title-casing
   `name` gives "Asteria" and "Amalthea", which look right, but "aura-2" style compound names
   would not survive it well if any appear later.
4. **Catalog fetch latency on the real Home Assistant host is unmeasured.** 205 KB of JSON
   across two requests at every entry setup, and `TIMEOUT_CATALOG` of 15 seconds is a guess
   nobody has tested against a Pi on wifi.
