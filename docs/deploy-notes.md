# Deploy notes

Raw facts and open questions behind `scripts/deploy.sh`, `scripts/tail_ha_log.sh`, and
`.github/workflows/release.yml`. The reader-facing version is `docs/deploying.html`; this file is
for the next agent. Written 2026-09-15, targeting Home Assistant 2026.9.x.

---

## Questions only Sam can answer

Three answers unblock the chapter 5 gate. Nothing here was guessed, and the tooling reads all of
it from variables, so answering these is filling in an env file rather than editing code.

1. **What install type is the instance?** Home Assistant OS, Supervised, Container, or Core. This
   decides whether the apps (formerly add-ons) store exists at all, and therefore whether Samba,
   SSH, and Studio Code Server are even options.
2. **What is its hostname or IP, and what port is the UI on?** For example
   `http://homeassistant.local:8123`. Both scripts need this for the API path.
3. **Which apps are installed, if any?** Specifically Advanced SSH and Web Terminal, Samba, and
   Studio Code Server. If none are installed and it is an OS install, transport choices narrow to
   installing one or using the port 22222 host shell.

Nice to have, not blocking:

4. Is the config directory a bind mount from a host that this laptop can write to? If yes, the
   `local` transport is the fastest option and needs no SSH at all.
5. Does `rsync` exist on the far side? The official SSH apps are Alpine based and do not all ship
   it. Without it on both ends, `rsync` over ssh fails at the far end, not the near end, which
   reads as a confusing error.

---

## hacs.json and zip_release

`hacs.json` currently has `"zip_release": false`. The release workflow builds and attaches
`deepgram_tts.zip` anyway, because the zip is useful on its own for manual installs and for anyone
who does not run HACS.

**If that flag ever flips to `true`, three things have to change together:**

1. `hacs.json` needs a `filename` key naming the asset, so `"filename": "deepgram_tts.zip"`. HACS
   documents `filename` as required whenever `zip_release` is set, and only integrations support
   `zip_release` at all.
2. The asset name in `release.yml` and the `filename` value must match exactly. They are two
   independent strings today and nothing checks them against each other. A mismatch makes HACS
   report a release with no installable content.
3. Every release from then on must carry that asset. With `zip_release: true` HACS stops reading
   the repository tree and looks only for the named asset, so a release that fails to attach it is
   an install failure rather than a missing extra.

Also worth knowing before flipping it: the zip's internal layout matters. The workflow zips from
inside `custom_components/deepgram_tts/`, so `manifest.json` sits at the archive root. That is the
layout HACS extracts into `config/custom_components/deepgram_tts/`. A zip containing a
`custom_components/deepgram_tts/` prefix would install nested and not load.

Do not flip it as part of this work. It is a distribution decision, and chapter 7 is where the
first tag happens.

---

## Verified facts used by the tooling

- **Add-ons are called apps as of Home Assistant 2026.2.** The panel was renamed and refactored
  into the frontend. Old `/hassio/addon/...` URLs may break. The Samba app's shares were renamed
  too: `addons` became `local_apps` and `addon_configs` became `app_configs`, with both names still
  working.
- **`GET /api/error_log`** returns "all errors logged during the current session of Home Assistant
  as a plaintext response." It is a whole-document fetch, not a stream. There is no server side
  tail, which is why `tail_ha_log.sh` polls and diffs by line count.
- **`POST /api/services/<domain>/<service>`** is the only service call endpoint. There is no
  dedicated restart endpoint, so a restart is `POST /api/services/homeassistant/restart`.
- **Authorization header is `Bearer <token>`**, from a long lived access token created on the HA
  profile page at `/profile`.
- **`homeassistant.reload_config_entry`** "reloads an integration's config entry without restarting
  Home Assistant" and "briefly unloads the integration, so its entities are unavailable for a
  moment while it sets up again." It takes an optional `entry_id` and can also be targeted at an
  entity, device, area, floor, or label. Admin only.
- **Studio Code Server is `aarch64` and `amd64` only.** Its config lists exactly those two
  architectures, so a 32 bit armv7 Pi cannot run it. It maps `homeassistant_config` at `/config`
  writable, plus addons, all_addon_configs, backup, media, share, and ssl.
- **The Home Assistant OS host shell is SSH on port 22222 as root**, enabled by putting an
  `authorized_keys` file on the root of a FAT, ext4, or NTFS USB partition named `CONFIG`
  (case sensitive), LF newlines, ASCII only, then rebooting. That is separate from the SSH app,
  which listens on 22 inside a container.
- **Container installs mount the config directory as `-v /PATH:/config`.** The `/config` path is
  internal; the host side is whatever the run command or compose file says.
- **Container and Core installs have no Supervisor**, so they have no apps store. The installation
  docs show Container lacking Apps, one-click updates, and backups compared to OS.
- **Core is on the way out.** It is documented as not recommended or supported for end users going
  forward, mainly a developer path.

---

## Open questions the tooling does not answer

1. **Whether `reload_config_entry` is ever useful here.** It re-runs `async_setup_entry` against
   the module Python already imported, so an edited `.py` is not picked up. It is useful for
   re-reading options and re-fetching the catalog, nothing more. Unverified: whether HA 2026.9
   drops the integration from its loader cache on unload. The safe assumption, and the one the
   script's help text states, is that it does not.
2. **First-frame latency on the target hardware** is still unmeasured, per HANDOFF section 7. The
   deploy path exists now, so this becomes measurable as soon as chapter 6 lands.
3. **Whether the SSH app on this instance has `rsync`.** See question 5 above. If it does not, the
   fallback is `tar` over ssh or the Samba share, and `deploy.sh` would need a third transport.
4. **Whether the instance has a `home-assistant.log` file on disk.** The default logger writes one
   to the config directory, but a custom `logger:` or `recorder:` setup can change that. The `ssh`
   log source assumes the file exists; the `api` source does not.
5. **shellcheck was not installed on this machine**, so the two scripts were checked with
   `bash -n` only. Whoever has shellcheck should run it once before the flip to public.

---

## Why no devcontainer path

HANDOFF section 2.2 lists a dangling `.devcontainer.json` as one of the fork's defects. A
devcontainer is a good way to run tests but it is not the chapter 5 gate: the gate is specifically
real hardware. Adding one here would compete with the real instance for attention. If it happens,
it belongs in chapter 7 alongside the README work.
