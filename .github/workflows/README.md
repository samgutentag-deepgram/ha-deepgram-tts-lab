`validate.yml` runs hassfest, HACS validation, ruff, the local manifest and import check, and
pytest. hassfest and HACS are the two that gate distribution; the other three gate merges.

`release.yml` runs on a `v*` tag or a published release. It refuses to build when the `version`
in `manifest.json` disagrees with the tag, then attaches a zip of the integration to the
release. `hacs.json` sets `zip_release: false`, so HACS installs from the repository tree and
that zip is for manual installs only. `docs/deploy-notes.md` lists what would have to change
together if `zip_release` ever flips.
