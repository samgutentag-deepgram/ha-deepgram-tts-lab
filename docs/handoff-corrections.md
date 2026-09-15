# Corrections to HANDOFF.md

`HANDOFF.md` is the historical record of what was known on 2026-09-15, before anything was
built. **It is not edited in place**, because rewriting it would destroy the record of what the
project believed when it started, and half the value of a build log is being able to see where
the starting assumptions were wrong.

This file is the correction. Every entry names the section it corrects, what the handoff claims,
what is actually true, how that was established, and what the code would do wrong if the
handoff's version were believed.

Corrections are appended, never edited. Each carries the date it was established.

---

## C1. `async_timeout` IS available on a real instance. Section 2.1 overstates the failure.

**Established 2026-09-15.** Corrects section 2.1 and, by extension, the framing of section 2.

**What the handoff says:**

> `async_timeout` is not in HA core requirements, and aiohttp dropped it as a dependency at 3.10
> (HA ships 3.14.3). Nothing installs it, so the integration almost certainly did not load at all.

**What is actually true.** `async_timeout` is importable on any Home Assistant instance that has
the `tts` component loaded, which is every instance a TTS integration runs on. The dependency
chain is three hops and none of them are obvious:

```
homeassistant/components/tts/manifest.json   dependencies: ["http", "ffmpeg"]
homeassistant/components/ffmpeg/manifest.json requirements: ["ha-ffmpeg==3.2.2"]
ha-ffmpeg==3.2.2                              requires: "async-timeout"
```

The last line is the load-bearing one, and what makes it easy to miss is that every **other**
package in the graph guards it behind a Python version marker:

```
bleak==3.0.2      ->  "async-timeout>=3.0.0 ; python_full_version < '3.11'"
aiohttp==3.14.3   ->  "async-timeout<6.0,>=4.0; python_version < \"3.11\""
ha-ffmpeg==3.2.2  ->  "async-timeout"
```

`ha-ffmpeg` has no marker at all, so pip installs `async-timeout` on Python 3.14 too. Confirmed
present in the test environment at version 5.0.1.

**How this was established.** Enumerated with `importlib.metadata.requires` over every installed
distribution in the project's own test venv, which runs the real Home Assistant 2026.9.2, then
cross-checked against the installed `tts` and `ffmpeg` manifests. Reproducible in one command:

```bash
.venv/bin/python -c "
from importlib.metadata import distributions, requires
for d in distributions():
    for r in requires(d.metadata['Name']) or []:
        if 'async' in r and 'timeout' in r:
            print(d.metadata['Name'], '->', r)"
```

**What this changes.**

- **The pydub half of section 2.1 still stands, and it is the real cause.** `pydub` is absent
  from the environment, nothing in a working Home Assistant requires it, and the prior
  integration's optional-import guard left `AudioSegment = None` so its streaming path raised
  `RuntimeError("pydub is not available")` on every request. That is a real, total failure of
  the streaming path.
- **"It almost certainly did not load at all" is not supportable and must not be published.**
  The integration most likely loaded fine and then failed on every Assist pipeline response,
  which is a different and more interesting bug: direct `tts.speak` calls kept working, so it
  looked healthy to anyone testing it by hand.
- Nothing in this repo's code depended on the wrong version of the claim. We use
  `asyncio.timeout` because it is stdlib and correct, not because `async_timeout` is missing.
  That reasoning is unaffected.
- `scripts/manifest_check.py` is unaffected and arguably more valuable: an undeclared import that
  happens to resolve through somebody else's transitive dependency is worse than one that fails
  outright, because it works until that dependency drops it.

**Where this matters most.** `advocacy/prep/notes.md` records it as F1.5 and F1.6, and the
technical blog draft was written against the corrected version. A post claiming the integration
never loaded would have been wrong in a way a reader could check in five minutes.

---

## C2. `/v2/speak` does not range check `speed` before auth. Section 3.4's speed row is from the docs.

**Established 2026-09-15.** Corrects section 3.4.

**What the handoff says.** Section 3.4 presents its query parameter table as "enumerated by
sending deliberately invalid values and reading the rejections," and lists:

> | `speed` | 0.5 to 1.5, 0.05 increments |

**What is actually true.** That range was never enumerable by probing. Deliberately invalid
speeds all return 401 rather than 400:

```
speed=3.0   -> HTTP 401  {"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}
speed=1.07  -> HTTP 401  {"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}
speed=0.1   -> HTTP 401  {"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}
```

So the `speed` range comes from Deepgram's documentation, not from observed behavior, and it is
unverified. Whether an off-grid value like 1.07 is rejected or quietly rounded is unknown.

**What still holds, and this is the useful part.** Not every check runs after auth. Two do run
before it, which is what made the rest of section 3 possible:

```
bogus_param=1              -> HTTP 400  INVALID_QUERY_PARAMETER: unknown field `bogus_param`
model=aura-2-thalia-en     -> HTTP 400  V1_MODEL_ON_V2_SPEAK_ENDPOINT
```

Unknown-field rejection and the family routing check are pre-auth. Value range checks are not.
So section 3's enum lists (`encoding`, `container`) and the two-families finding are sound, and
only the numeric ranges are docs-sourced.

**How this was established.** Six requests to the live `/v2/speak` with a dummy 40-character
token, run twice by two different sessions, with the two pre-auth controls above as a baseline
so "everything returns 401" could be ruled out.

**What this changes.**

- The comment in `const.py` next to `SPEED_MIN` and `SPEED_MAX` claimed the endpoint validates
  that range. Corrected to say where the range comes from.
- We still constrain speed to 0.5 to 1.5 in 0.05 steps in the options flow, which is right: a
  documented range is a better guess than no constraint.
- Add to the first-API-key list: send `speed=1.37`, off the 0.05 grid, and record whether it is
  rejected or rounded. The options flow's slider step depends on the answer.

---

## C3. Section 4.3's constant list is correct and incomplete.

**Established 2026-09-15.** Corrects section 4.3 by addition.

Everything section 4.3 names is exactly right in the installed Home Assistant 2026.9.2:
`ATTR_VOICE = "voice"`, `ATTR_PREFERRED_FORMAT = "preferred_format"`,
`ATTR_PREFERRED_SAMPLE_RATE = "preferred_sample_rate"`, `_DEFAULT_FORMAT = "mp3"`.

Also present and exported, and not mentioned: `ATTR_AUDIO_OUTPUT = "audio_output"`,
`ATTR_PREFERRED_SAMPLE_CHANNELS`, `ATTR_PREFERRED_SAMPLE_BYTES`, `ATTR_PREFERRED_BITRATE`,
`ATTR_MEDIA_PLAYER_ENTITY_ID`, `ATTR_PLATFORM`, `CONF_LANG`.

Two behaviors worth knowing that section 4.3 does not cover:

1. The five `preferred_*` options bypass `supported_options` validation entirely. Advertising one
   only decides whether it stays in `options` for the entity to act on, or gets popped and
   applied by ffmpeg afterwards.
2. `async_get_tts_audio(self, message, language, options)` takes `options` as a **required
   positional** `dict[str, Any]`, not `dict | None = None`. Chapter 1's placeholder had the
   optional shape and was wrong.

`ATTR_AUDIO_OUTPUT` is deliberately not advertised by this integration. See
`docs/chapter-5-notes.md` for why: the only two core consumers give it incompatible meanings,
and honoring it as a second format knob fights `preferred_format`.

---

## C4. `mutagen` is pinned to a version the handoff never named, and the first guess was wrong.

**Established 2026-09-15.** Not a correction to the handoff, which does not mention `mutagen`.
Recorded here because the wrong number was briefly in this repo.

The installed `homeassistant/components/tts/manifest.json` requires `mutagen==1.48.1`.
`requirements-test.txt` initially pinned `1.47.0`, which was a guess. Corrected to match the
manifest, so the test environment matches a real instance rather than approximating one.
`ha-ffmpeg==3.2.2` added alongside it for the same reason.

Neither belongs in our `manifest.json`. They are the `tts` component's requirements, and
declaring somebody else's dependency is how a manifest starts lying, which is the failure mode
section 2.1 is about.
