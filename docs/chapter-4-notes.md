# Chapter 4 notes: the config flow

Written 2026-09-15, while building `config_flow.py`. Notes an agent reads, so this stays markdown.

## What I chose

- **No language step, one dropdown with all 138 voices.** Three reasons, in order of weight.
  First, the configured voice is a preference, not a constraint: `resolve_voice` already refuses
  to send a Flux voice down a Spanish pipeline and picks an Aura voice per request, so filtering
  the picker by language would be filtering on something the entity does not treat as binding.
  Second, Home Assistant renders a `SelectSelector` in `DROPDOWN` mode as a combo box that
  filters as you type, so "haley" or "-es" narrows 138 to a handful with no extra click. Third,
  a language step costs every user a click and only 49 of the 138 voices are non-English, so it
  would tax the common case to organize the rare one. Ordering does the work instead: Flux
  (36), then English Aura, then the remaining languages grouped by base code, then by name.
- **The label is `Name (Family, Accent) [voice-id]`**, with the base language codes inserted
  before the id for a voice that cannot speak English. So
  `Haley (Flux, American) [flux-haley-en]` and
  `Celeste (Aura, Neutral, es) [aura-2-celeste-es]`.
  - The id is in the label because **the name is not unique**. With `display_name` null on 61 of
    102 Aura entries, the fallback title-cases the bare name, and the legacy `aura-asteria-en`
    and the current `aura-2-asteria-en` both come out as "Asteria" with the same family and the
    same accent. Family plus accent is not enough to tell them apart; the id always is, because
    it is the catalog's own key. It is also the model string the integration sends, which is what
    someone comparing this against Deepgram's docs wants to read.
  - Language codes are omitted for English voices because 89 of 138 are English and repeating
    `en` on all of them is noise.
- **`sort=False` on the select selector, explicitly.** The default is already false, but the
  whole design is Flux-first ordering, and letting the frontend alphabetize would silently throw
  it away. Written out so nobody flips it as a tidy-up.
- **The entry stores only the API key in `data` and only the voice in `options`.** No seeded
  `speed`, because speed has a default in `const.py` and a stored copy nothing has chosen yet is
  just another thing that can drift. It also matches the shape `tests/conftest.py` already
  assumes for a config entry.
- **Speed visibility is decided by the voice currently in options, not by the voice being
  chosen in the same form.** A form's schema is fixed before the user touches it, so there is no
  way to reveal a field mid-form without a second step. Switching Flux to Aura saves the new
  voice, drops any stored speed, and reloads; the next visit to options shows the right fields.
  Switching Aura to Flux is the same in reverse, and speed falls back to `DEFAULT_SPEED`.
- **The options flow reads the catalog from `runtime_data` and only fetches as a fallback.** A
  loaded entry already holds it, so opening options is normally zero network calls. An entry in
  SETUP_RETRY has no `runtime_data`, and its options are still reachable from the UI, so the
  fallback is a real fetch rather than an empty picker that would silently drop the configured
  voice. A failed fallback aborts with `cannot_connect`, which is a new `options.abort` key in
  both string files.
- **`getattr(self.config_entry, "runtime_data", None)` rather than importing
  `DeepgramRuntimeData`.** Duck typing here keeps `config_flow.py` from importing the package
  `__init__`, which would be a cycle waiting to happen for one attribute read.
- **The reload test proves the existing listener, and counts calls to do it.** `__init__.py`
  already registers `add_update_listener(_async_reload_entry)`, so chapter 4 adds nothing. The
  assertion is exact (`call_count == before + 2`): two catalog GETs from the reload's setup, and
  zero from the options form, which pins both the reuse and the single reload.

## What surprised me

1. **`ConfigFlow.async_create_entry` takes `options=`** and the flow result carries an
   `"options"` key, so the voice lands in options without a follow-up update. I expected to
   need `async_update_entry` after creation.
2. **`AiohttpClientMocker.match_request` returns the first registered match**, so registering a
   401 and then a 200 for the same URL always serves the 401. The recovery test only works
   because `clear_requests()` drops the mocks and the call log together. That is the mechanism
   behind "a typo'd key is one correction away" being testable at all.
3. **`base_languages` is a frozenset**, so the sort key has to sort it before indexing or the
   picker order changes between runs for any voice with more than one base code. Nothing in the
   live catalog has two base codes today, but hash order would have made it a flaky test rather
   than a wrong one.
4. **Finding B is even broader than stated for the picker.** It is not only that the fallback is
   common, it is that the fallback *collides*: two different voices produce byte-identical names.
   A label built from name plus family plus accent is ambiguous on live data, not in theory.

## Still unverified

1. **Nothing authenticated has run.** There is no `DEEPGRAM_API_KEY` on this machine. So the key
   step is verified only against mocks: whether a real rejected key returns 401 or 403, whether
   its body is JSON, and whether `async_verify_key`'s one-word synthesis is fast enough that the
   form does not feel stuck are all open. HANDOFF section 7 item 1 still stands.
2. **The dropdown has never been rendered with 138 options.** The claim that the frontend combo
   box filters as you type is from the selector contract and from how HA renders select
   elsewhere, not from watching this form. If it turns out to render as a plain 138-row list,
   the language step decision should be revisited, and that is a one-step change.
3. **Label length in the UI is unmeasured.** `Celeste (Aura, Neutral, es) [aura-2-celeste-es]`
   may truncate on a phone-width dropdown. The name is first for exactly that reason, but where
   it truncates is unknown.
4. **The `NumberSelector` slider with a 0.05 step over 0.5 to 1.5** has not been used on a
   touchscreen. Twenty stops on a slider may be fiddly, in which case `BOX` is the fix.
5. **Two entries on real hardware.** Two entries with different voices pass in tests, but the
   entity naming and device layout for a second entry has only been seen through
   `hass.states`, not in the UI. Chapter 5 on the real instance is where that shows up.
