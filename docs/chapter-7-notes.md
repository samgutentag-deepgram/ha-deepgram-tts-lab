# Chapter 7 notes: the documentation half

Written 2026-09-15, alongside `README.md`, `CHANGELOG.md`, `docs/hacs-submission.md`, and
`LICENSE`. Notes an agent reads, so this stays markdown.

## The CHANGELOG grouping decision

**Standard Keep a Changelog headings, not the seven build chapters.** Three reasons, in order of
weight.

The changelog is for someone who installed the integration, and a user has no idea what chapter 3
was. "Voice catalog merged from both Deepgram endpoints" is a line they can act on. "Chapter 3:
voice catalog" makes them read the whole section to find out whether it affects them.

The lab convention rewrites this history into build order before the public snapshot, so the
public commit log already tells the chapter story, and it tells it better than a changelog can
because each chapter is a diff you can read. A chapter-grouped changelog would be a second copy of
that narrative in a file that nobody updates when the rewrite reorders anything. Two records of
the same thing, one of which silently goes stale.

The build story is already written down twice, in `.hub/ledger.md` and in the chapter notes, and
both are better at it. The ledger records what a repo scan cannot recover. A changelog records
what changed for a user. Making the changelog do the ledger's job costs the ledger nothing and
costs the changelog its audience.

Consequence worth accepting up front: `[Unreleased]` is all `Added`, with no `Changed` or `Fixed`,
which looks thin. It is correct. There is no released version for anything to have changed from,
and the note at the top of the section says so rather than letting it read as an omission.

## What contradicted the brief

1. **`tts.py` in this worktree is still the chapter 1 stub, and `async_get_tts_audio` raises
   `DeepgramRequestError`.** The brief for this chapter said batch synthesis works. It does not,
   not on the commit this branch was cut from (`ee50613`, chapter 4). Chapter 5 was in flight in
   another worktree while this was written. So the README describes batch as the path the
   integration uses, which is true of the design and of the API client that backs it, and puts
   what is actually unverified in one honest section instead: no authenticated request has ever
   run, and nothing has run on real hardware. Both of those stay true after chapter 5 merges,
   which is the point of phrasing it that way.
2. **The test count is 77, not the 62 the ledger records.** The ledger's 62 was true when chapter
   6's socket tests landed; chapter 4 added 15 more. `.venv/bin/python -m pytest -q` reports
   `77 passed`. The README cites 77 and nothing else cites a count.
3. **`stream.py` is on main, not on a branch.** The ledger entry for the chapter 6 hold says
   chapter 6 "is built fully, on its own branch" and is not merged. The file is in fact committed
   on main (`dc0ac84`, "inert until the entity opts in"). The hold is real and the reasoning is
   unchanged, because `tts.py` does not override `async_stream_tts_audio` and that override is the
   only opt-in there is. Only the location is different from what the ledger says. The README
   describes it as written and not enabled, which matches the code.

## Facts the README deliberately does not state

- **No latency number, anywhere.** None has been measured. Deepgram's 80ms claim appears once, as
  a claim to test, attributed to marketing.
- **No "fast" framing.** The strongest supported angle today is the audit, not speed, and the
  audit belongs in a blog post where there is room to be fair to a volunteer's open source work.
  The README credits `alceasan/ha-deepgram-tts` plainly and does not hint at the audit at all.
  Two places do describe integration behavior that exists *because* of an audit finding, the typed
  errors in the troubleshooting section and the absent `async_stream_tts_audio` override, and both
  name the defect without naming who wrote it.
- **No claim of a release, tag, or HACS listing.** All three are false today and
  `docs/hacs-submission.md` says exactly which boxes are unchecked.

## Open, for whoever tags 0.1.0

1. **No brand images exist.** Not in `custom_components/deepgram_tts/brand/`, not in
   `home-assistant/brands`. It is the only HACS default-store requirement that needs work nobody
   has started, and since HA 2026.3 it can be satisfied inside this repo before the flip. Details
   and sizes are in `docs/hacs-submission.md` section 4.
2. **The repository description and topics are unverifiable from here.** The active `gh` account
   is the personal one, so `gh repo view` cannot see this private repo (HANDOFF section 8.3).
   Both are GitHub settings on the public repo anyway, so they are flip-time work either way.
3. **`manifest.json` version is `0.1.0` and no tag exists.** `release.yml` fails the build if the
   tag and the manifest disagree, so the first tag has to be `v0.1.0` or the manifest has to move
   first.
