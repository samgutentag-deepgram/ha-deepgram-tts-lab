# Getting into the HACS default store

Researched against the live HACS docs on 2026-09-15, not from memory. HACS requirements move, so
re-read the two pages linked at the bottom before opening either pull request.

The short version: the integration itself is close. Almost everything still missing is either a
GitHub setting that only exists once this repo is public, or an image file nobody has drawn yet.
The flip to a public repo is one way and terminal, so the useful thing this page does is separate
"fix it now" from "cannot be fixed until after the flip."

Two pull requests are involved, against two different repositories, and people routinely discover
the second one late:

1. [`hacs/default`](https://github.com/hacs/default), adding this repo to the `integration` list.
2. [`home-assistant/brands`](https://github.com/home-assistant/brands), or a `brand/` directory
   shipped inside the integration, for the icon and logo.

---

## 1. General requirements

| # | Requirement | State | Where |
| --- | --- | --- | --- |
| 1 | Public repository hosted on GitHub | **No.** Private lab repo | blocked on the flip |
| 2 | A repository description, a few words, shown in the HACS UI | **No** | GitHub settings, after the flip |
| 3 | Repository topics set | **No** | GitHub settings, after the flip |
| 4 | A README that explains how to use it | **Yes** | [`README.md`](../README.md) |
| 5 | `hacs.json` in the repository root with a `name` key | **Yes** | [`hacs.json`](../hacs.json) |
| 6 | A published GitHub **release**, not just a tag | **No.** No tag exists | [`release.yml`](../.github/workflows/release.yml) builds it |
| 7 | The repo can already be added to HACS as a custom repository | **Not verified.** HACS has never fetched this repo | needs item 1 |

On item 5, `hacs.json` currently carries `name`, `content_in_root: false`, `render_readme: true`,
`homeassistant: "2026.9.0"`, and `zip_release: false`. That is a valid set. If `zip_release` ever
flips to `true` it needs a `filename` key naming the release asset, and
[`deploy-notes.md`](deploy-notes.md) lists the three things that have to change together.

On item 6, HACS reads the version from `manifest.json`, not from the tag. `release.yml` already
fails the build when the two disagree, which is the right place for that check.

---

## 2. Integration requirements

| # | Requirement | State | Where |
| --- | --- | --- | --- |
| 8 | Exactly one integration per repository, one subdirectory under `custom_components/` | **Yes.** Only `deepgram_tts` | `custom_components/` |
| 9 | Every file the integration needs lives inside that directory | **Yes** | `custom_components/deepgram_tts/` |
| 10 | `manifest.json` has `domain`, `name`, `documentation`, `issue_tracker`, `codeowners`, `version` | **Yes.** All six, `version` is `0.1.0` | [`manifest.json`](../custom_components/deepgram_tts/manifest.json) |
| 11 | Brand assets: a `brand/` directory with at least `icon.png`, or an entry in `home-assistant/brands` | **Yes, already.** `home-assistant/brands` has a `custom_integrations/deepgram_tts/` entry with all four files, and the CDN serves them. Verified 2026-09-16 | section 4 |
| 12 | A `country` key in `hacs.json` if the integration is region limited | Not applicable. Deepgram is not region gated | |
| 13 | Not an alpha or beta of a core integration, and does not override one | **Yes.** `deepgram_tts` is not a core domain | |
| 14 | Submitted by the repo owner or a major contributor | **Yes**, once Sam opens it | |

Items 10 and 11 are the two that hassfest and the HACS action actually enforce, and item 11 is the
only one of the pair that fails today.

One thing to check at flip time rather than assume: `manifest.json` points `documentation` and
`issue_tracker` at `github.com/samgutentag-deepgram/ha-deepgram-tts`, which is the flip target and
does not exist yet. Both URLs 404 until the public repo is created. They are correct in advance,
not wrong, but a hassfest run against a public repo is the first thing that would notice if the
flip ever landed under a different name.

---

## 3. Validation

Both actions have to pass with no errors before the `hacs/default` pull request is opened.

| # | Check | State | Where |
| --- | --- | --- | --- |
| 15 | `hacs/action@main` with `category: integration` | Wired, never run against a public repo | [`validate.yml`](../.github/workflows/validate.yml) |
| 16 | `home-assistant/actions/hassfest@master` | Wired, never run locally | [`validate.yml`](../.github/workflows/validate.yml) |
| 17 | ruff check and format | **Passing** | `validate.yml`, `uvx ruff@0.16.7` |
| 18 | Local manifest, translations, and import check | **Passing** | [`manifest_check.py`](../scripts/manifest_check.py) |
| 19 | pytest | **Passing**, 122 tests on main | `validate.yml` |
| 20 | Local HACS and hassfest stand-in | **Passing**, 22 verified, 0 failures | [`hacs_check.py`](../scripts/hacs_check.py) |

hassfest ships as a Docker action and there is no Docker daemon on the build machine, so it has
never run here. `scripts/manifest_check.py` is the local stand-in: manifest keys present and in
hassfest's order, `strings.json` and `translations/en.json` with identical key trees, and every
third-party import declared in manifest requirements. It fails faster than CI and it does not
replace CI.

The HACS action's brand check is the one that will fail on a first real run, for the reason in the
next section.

Unrelated to HACS but on the same pre-flip checklist: `shellcheck` was never run against
`scripts/deploy.sh` or `scripts/tail_ha_log.sh`, because it is not installed on the build machine.
A public repo's shell scripts get read. Run it once before the flip.

---

## 4. Brands: already done, and not by us

**This requirement is already satisfied and nobody here did it.** Checked on 2026-09-16:

```
GET api.github.com/repos/home-assistant/brands/contents/custom_integrations/deepgram_tts -> 200
  icon.png       6267 bytes
  icon@2x.png   10126 bytes
  logo.png       9774 bytes
  logo@2x.png   20627 bytes

GET brands.home-assistant.io/deepgram_tts/icon.png      -> 200, 256x256 PNG
GET brands.home-assistant.io/deepgram_tts/icon@2x.png   -> 200
GET brands.home-assistant.io/deepgram_tts/logo.png      -> 200
GET brands.home-assistant.io/deepgram_tts/dark_icon.png -> 200
```

Brand assets in that repository are keyed on the **integration domain**, not on the repository or
the author. This project's domain is `deepgram_tts`, which is the same domain the community
integration used, so we inherit an entry somebody already got merged for it.

That removes the only requirement on this list that needed an asset nobody had made, and it
removes a pull request into a review queue on someone else's repository.

Two things worth being clear-eyed about:

- **It is somebody else's submission of Deepgram's mark.** It is correct, it is 256x256 as
  specified, and it is already serving. It is also not ours, and if the brands repo ever tightens
  ownership rules for custom integration entries, this is the item that would come back.
- **It is another reason to keep the domain.** Changing `deepgram_tts` to anything else would
  silently lose the icon and put the brands pull request back on the list.

Sam works at Deepgram, which makes checking that the mark in that repo is the current one a
cheap thing to do and not a less necessary one.

The file spec below is kept for reference, in case a dark variant or a refreshed mark is ever
wanted.

### File spec, for reference

This is the item that needs work nobody has started, because it needs image files rather than
code. There are two ways to satisfy it as of Home Assistant 2026.3, and the newer one is easier:

**Option A, ship the images in this repo.** Since Home Assistant 2026.3, a custom integration can
carry its own brand images in `custom_components/deepgram_tts/brand/`. A local `brand/` directory
takes precedence over anything in the brands repository, and the HACS docs accept a `brand/`
directory with at least an `icon.png` as satisfying the brand requirement. No second pull request,
no review queue, and the images ship and update with the integration.

**Option B, a pull request to `home-assistant/brands`.** Images go in
`custom_integrations/deepgram_tts/`. This is the path every guide written before 2026.3 describes,
and it is still supported. It is a review queue on someone else's repository, so it is the slower
of the two.

Either way, the files are the same. Up to eight, all PNG:

| File | Size | Required |
| --- | --- | --- |
| `icon.png` | 256x256, square | Yes, this is the minimum |
| `icon@2x.png` | 512x512, square | Recommended, hi-DPI |
| `logo.png` | shortest side 128 to 256, landscape | Optional |
| `logo@2x.png` | shortest side 256 to 512, landscape | Optional |
| `dark_icon.png`, `dark_icon@2x.png` | as above | Optional, dark theme |
| `dark_logo.png`, `dark_logo@2x.png` | as above | Optional, dark theme |

The brands repository asks for PNGs that are compressed and optimized for the web with lossless
preferred, interlaced (progressive) preferred, and transparency preferred. Icons must be 1:1.
Logos should be landscape and should respect the brand's original proportions rather than being
padded to fit.

**Nobody has made any of these.** There is no `icon.png` anywhere in this repository, in either
location, at any size. That is at minimum one 256x256 square PNG and realistically four files once
you want the `@2x` variants and a dark icon, plus whatever a Deepgram mark needs to look right at
32 pixels in a Home Assistant integration list.

One question to settle before drawing anything, because it is a permission question and not a
design one: these images identify a third-party integration using Deepgram's mark, so the icon
should come from Deepgram's own brand assets rather than be redrawn, and using them on a
personally maintained integration is worth a quick internal check first. Deepgram employs the
author, which makes it easier to ask and not less necessary.

---

## 5. Submitting to `hacs/default`

Only once every box above is checked and a real release exists.

1. Fork [`hacs/default`](https://github.com/hacs/default) and work on **a new branch**, not on the
   default branch. The maintainers need the pull request to be editable.
2. Add the repository to the `integration` file, in **alphabetical order**. The automation checks
   the sort and will fail the pull request if it is out of order.
3. Fill in the pull request template properly. The automated checks cover brand verification,
   manifest validity, HACS validation, JSON linting, and the alphabetical sort.
4. Expect the brand check to be the one that fails if section 4 was skipped.

---

## 6. What cannot be done until after the flip

Everything in this list needs a public repository, and the flip is one way. Get the rest done
first so the flip is followed by a short queue rather than a long one.

1. The public repository itself, `samgutentag-deepgram/ha-deepgram-tts` (item 1).
2. The repository description and topics, which are GitHub settings on the public repo, not files
   in this tree (items 2 and 3).
3. A published release. A release on a private repo is invisible to HACS, so the first tag belongs
   on the public repo (item 6).
4. Adding the repo to HACS as a custom repository to prove the download path works on a clean
   instance (item 7). This is also the last checkbox in
   [`deploying.html`](deploying.html)'s plan, which uses HACS exactly twice: once to prove
   distribution, once after the flip to prove a stranger can install it.
5. The HACS action and hassfest passing on a public repo, which is the state the `hacs/default`
   pull request asserts (items 15 and 16).
6. Both pull requests, since each one names a public repository URL (sections 4 and 5).

Option A for brands is the exception worth noticing: the images can be drawn and committed to
`custom_components/deepgram_tts/brand/` today, before the flip, and then they simply exist on the
public snapshot. That turns the longest-lead item in this whole page into something that does not
need to wait.

---

## Sources

- [Include default repositories](https://hacs.xyz/docs/publish/include/), HACS
- [General requirements](https://hacs.xyz/docs/publish/start/), HACS
- [Integrations](https://www.hacs.xyz/docs/publish/integration/), HACS
- [`hacs/default`](https://github.com/hacs/default)
- [`home-assistant/brands`](https://github.com/home-assistant/brands), for the image sizes and
  format rules
- [Brand images](https://developers.home-assistant.io/docs/core/integration/brand_images), Home
  Assistant developer docs, for the 2026.3 `brand/` directory and its precedence
