#!/usr/bin/env python3
"""Check this repository against the HACS default-store requirements, locally.

`scripts/manifest_check.py` guards correctness: that the manifest does not lie about its
imports. This one guards **distribution**: whether HACS and Home Assistant would accept the
repository at all. They fail differently, so they are separate scripts.

Both of the real gates run as Docker actions, `hacs/action` and
`home-assistant/actions/hassfest`, and there is no Docker daemon on this machine. So this covers
the checks whose failure would only surface in CI after a push, plus the ones hassfest performs
on a manifest that no local tool otherwise looks at.

    .venv/bin/python scripts/hacs_check.py
    .venv/bin/python scripts/hacs_check.py --offline     # skip the network checks

Three kinds of result:

  ok      verified here
  SKIP    a real requirement that cannot be checked from a private repo on a laptop, named
          rather than silently passed
  FAIL    would be rejected

A SKIP is not a pass. The GitHub-side requirements, a public repo with a description and topics
and a published release, are listed as skips on purpose so the count of unverified things stays
visible instead of reading as a clean bill of health.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "custom_components"

# From homeassistant/loader.py. hassfest rejects anything outside this set.
VALID_IOT_CLASSES = {
    "assumed_state",
    "cloud_polling",
    "cloud_push",
    "local_polling",
    "local_push",
    "calculated",
}
VALID_INTEGRATION_TYPES = {
    "device",
    "entity",
    "hardware",
    "helper",
    "hub",
    "service",
    "system",
    "virtual",
}
# HACS reads these and ignores unknown keys, so a typo is silent rather than an error.
KNOWN_HACS_KEYS = {
    "name",
    "content_in_root",
    "filename",
    "country",
    "homeassistant",
    "hacs",
    "persistent_directory",
    "render_readme",
    "zip_release",
    "hide_default_branch",
}

results: list[tuple[str, str]] = []


def ok(message: str) -> None:
    results.append(("ok", message))


def skip(message: str) -> None:
    results.append(("SKIP", message))


def fail(message: str) -> None:
    results.append(("FAIL", message))


def fetch(url: str, timeout: int = 10) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "hacs_check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, b""
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return 0, str(err).encode()


def check_structure() -> str | None:
    """One integration per repository, everything inside its own directory."""
    if not COMPONENTS.is_dir():
        fail("no custom_components/ directory")
        return None

    domains = sorted(
        p.name for p in COMPONENTS.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    if len(domains) != 1:
        fail(f"HACS allows exactly one integration per repository, found {len(domains)}: {domains}")
        return None

    domain = domains[0]
    ok(f"exactly one integration: {domain}")

    if not (COMPONENTS / domain / "manifest.json").is_file():
        fail(f"custom_components/{domain}/manifest.json is missing")
        return None

    for required in ("__init__.py", "manifest.json"):
        if not (COMPONENTS / domain / required).is_file():
            fail(f"custom_components/{domain}/{required} is missing")

    if (ROOT / "README.md").is_file():
        ok("README.md present, which HACS renders in its UI")
    else:
        fail("no README.md; HACS requires one that explains how to use the integration")

    if (ROOT / "LICENSE").is_file() or (ROOT / "LICENSE.md").is_file():
        ok("LICENSE present")
    else:
        fail("no LICENSE file")

    return domain


def check_manifest(domain: str) -> dict:
    manifest = json.loads((COMPONENTS / domain / "manifest.json").read_text())

    if manifest.get("domain") != domain:
        fail(f"manifest domain {manifest.get('domain')!r} does not match the directory {domain!r}")
    else:
        ok(f"manifest domain matches the directory name: {domain}")

    # HACS requires version on a custom integration. Core integrations must NOT have it, which
    # is why hassfest's rule reads backwards if you only know the core half.
    for key in ("domain", "name", "documentation", "issue_tracker", "codeowners", "version"):
        if not manifest.get(key):
            fail(f"manifest.json is missing {key!r}, which HACS requires for a custom integration")
    if all(
        manifest.get(k)
        for k in ("domain", "name", "documentation", "issue_tracker", "codeowners", "version")
    ):
        ok("manifest has all six keys HACS requires, version included")

    version = str(manifest.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+([.-][0-9A-Za-z.]+)?", version):
        fail(f"manifest version {version!r} is not a version HACS will sort")
    else:
        ok(f"manifest version parses: {version}")

    iot_class = manifest.get("iot_class")
    if iot_class not in VALID_IOT_CLASSES:
        fail(f"iot_class {iot_class!r} is not one of {sorted(VALID_IOT_CLASSES)}")
    else:
        ok(f"iot_class is valid: {iot_class}")

    integration_type = manifest.get("integration_type")
    if integration_type not in VALID_INTEGRATION_TYPES:
        fail(
            f"integration_type {integration_type!r} is not one of {sorted(VALID_INTEGRATION_TYPES)}"
        )
    else:
        ok(f"integration_type is valid: {integration_type}")

    for owner in manifest.get("codeowners", []):
        if not owner.startswith("@"):
            fail(f"codeowner {owner!r} must start with @")

    if manifest.get("config_flow") and not (COMPONENTS / domain / "config_flow.py").is_file():
        fail("manifest sets config_flow true but config_flow.py does not exist")
    elif manifest.get("config_flow"):
        ok("config_flow is true and config_flow.py exists")

    if manifest.get("single_config_entry"):
        fail("single_config_entry is set; two entries must stay possible for this integration")

    return manifest


def check_hacs_json() -> dict:
    path = ROOT / "hacs.json"
    if not path.is_file():
        fail("no hacs.json in the repository root")
        return {}

    data = json.loads(path.read_text())
    if not data.get("name"):
        fail("hacs.json has no name key, which HACS requires")
    else:
        ok(f"hacs.json name: {data['name']}")

    unknown = set(data) - KNOWN_HACS_KEYS
    if unknown:
        # HACS ignores what it does not recognize, so a typo here is silent.
        fail(f"hacs.json has keys HACS does not read, so they do nothing: {sorted(unknown)}")
    else:
        ok("every hacs.json key is one HACS actually reads")

    floor = data.get("homeassistant")
    if floor:
        ok(f"hacs.json declares a Home Assistant floor: {floor}")
    else:
        skip("hacs.json declares no homeassistant floor, so HACS offers it to every version")

    if data.get("zip_release") and not data.get("filename"):
        fail("hacs.json sets zip_release without filename; HACS needs to know what to download")
    if data.get("content_in_root"):
        fail(
            "content_in_root is true, but this repo keeps the integration under custom_components/"
        )

    return data


def check_translations(domain: str) -> None:
    strings = COMPONENTS / domain / "strings.json"
    english = COMPONENTS / domain / "translations" / "en.json"

    if not strings.is_file():
        fail("no strings.json, so both flows render bare step ids")
        return
    if not english.is_file():
        fail("no translations/en.json")
        return

    if json.loads(strings.read_text()) == json.loads(english.read_text()):
        ok("strings.json and translations/en.json are identical")
    else:
        fail("strings.json and translations/en.json disagree")


def check_config_flow_strings(domain: str) -> None:
    """Every step the flow shows needs a strings.json entry, or the UI renders the step id."""
    flow = COMPONENTS / domain / "config_flow.py"
    strings_path = COMPONENTS / domain / "strings.json"
    if not flow.is_file() or not strings_path.is_file():
        return

    source = flow.read_text()
    strings = json.loads(strings_path.read_text())

    shown = set(re.findall(r'step_id=["\']([a-z_]+)["\']', source))
    described = set(strings.get("config", {}).get("step", {})) | set(
        strings.get("options", {}).get("step", {})
    )
    missing = shown - described
    if missing:
        fail(f"config flow shows steps with no strings.json entry: {sorted(missing)}")
    elif shown:
        ok(f"every shown flow step has a translation: {sorted(shown)}")

    raised = set(re.findall(r'errors\[["\']base["\']\]\s*=\s*["\']([a-z_]+)["\']', source))
    declared = set(strings.get("config", {}).get("error", {}))
    missing_errors = raised - declared
    if missing_errors:
        fail(f"config flow sets error keys with no translation: {sorted(missing_errors)}")
    elif raised:
        ok(f"every config flow error key has a translation: {sorted(raised)}")


def check_workflows() -> None:
    workflows = ROOT / ".github" / "workflows"
    if not workflows.is_dir():
        fail("no .github/workflows, so nothing validates on push")
        return

    text = "\n".join(p.read_text() for p in workflows.glob("*.yml"))
    for needle, label in (
        ("hassfest", "hassfest action"),
        ("hacs/action", "HACS validation action"),
    ):
        if needle in text:
            ok(f"{label} is wired into CI")
        else:
            fail(f"{label} is not in any workflow; HACS expects it to pass on the public repo")

    if "setup-python" in text:
        ok("a workflow pins a Python version, which the ast-based checks need")


def check_brands(domain: str, offline: bool) -> None:
    """Brand assets, which live in a different repository and are easy to discover late."""
    local = COMPONENTS / domain / "brand" / "icon.png"
    if local.is_file():
        ok(f"local brand icon present at custom_components/{domain}/brand/icon.png")
        return

    if offline:
        skip("brand assets not checked (--offline). They live in home-assistant/brands")
        return

    status, body = fetch(f"https://brands.home-assistant.io/{domain}/icon.png")
    if status == 200:
        ok(
            f"brands.home-assistant.io already serves an icon for {domain} "
            f"({len(body)} bytes), so no brands pull request is needed"
        )
        for extra in ("icon@2x.png", "logo.png", "dark_icon.png"):
            extra_status, _ = fetch(f"https://brands.home-assistant.io/{domain}/{extra}")
            if extra_status == 200:
                ok(f"  and {extra}")
    elif status == 0:
        skip(f"could not reach brands.home-assistant.io ({body.decode()[:80]})")
    else:
        fail(
            f"no brand icon for {domain}: brands.home-assistant.io returned {status}. "
            f"Either add custom_components/{domain}/brand/icon.png (256x256 PNG, supported "
            "since Home Assistant 2026.3) or open a pull request on home-assistant/brands"
        )


def has_flipped() -> bool:
    """Whether the public snapshot repo exists yet.

    `.hub/hub.yml` gets a `public_repo:` key at the moment of the flip, and its absence is the
    convention's way of saying the project is still private. Read it rather than guessing from a
    404, so a genuinely wrong URL stays a failure.
    """
    hub = ROOT / ".hub" / "hub.yml"
    if not hub.is_file():
        return False
    return bool(re.search(r"^public_repo:\s*\S", hub.read_text(), re.M))


def check_manifest_urls(manifest: dict, offline: bool) -> None:
    """HACS shows these to users, and a 404 is a bad first impression."""
    flipped = has_flipped()
    for key in ("documentation", "issue_tracker"):
        url = manifest.get(key)
        if not url:
            continue
        if offline:
            skip(f"manifest {key} not fetched (--offline): {url}")
            continue
        status, _ = fetch(url)
        if status == 200:
            ok(f"manifest {key} resolves: {url}")
        elif status == 0:
            skip(f"could not reach manifest {key}: {url}")
        elif status == 404 and not flipped:
            # Expected, not broken. These point at the flip target, which does not exist until
            # the public snapshot is created. A 404 here after the flip IS a failure, which is
            # why this is keyed off hub.yml rather than off the status code alone.
            skip(f"manifest {key} is 404 because the public repo does not exist yet: {url}")
        else:
            fail(f"manifest {key} returns {status}: {url}")


def check_github_side() -> None:
    """Named rather than silently passed, because none of it is checkable from here."""
    if has_flipped():
        ok("hub.yml records a public_repo, so the flip has happened")
    else:
        skip("public repository on GitHub: this is a private lab repo until the flip")
    skip("repository description: a GitHub setting, shown in the HACS UI")
    skip("repository topics: a GitHub setting")
    skip("a published GitHub release, not just a tag: none exists yet")
    skip("addable to HACS as a custom repository: HACS has never fetched this repo")
    skip("hassfest and hacs/action passing on a public repo: both need item one")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip every network check")
    args = parser.parse_args()

    domain = check_structure()
    if domain:
        manifest = check_manifest(domain)
        check_hacs_json()
        check_translations(domain)
        check_config_flow_strings(domain)
        check_workflows()
        check_brands(domain, args.offline)
        check_manifest_urls(manifest, args.offline)
    check_github_side()

    width = max(len(level) for level, _ in results)
    for level, message in results:
        print(f"{level:<{width}}  {message}")

    failures = sum(1 for level, _ in results if level == "FAIL")
    skips = sum(1 for level, _ in results if level == "SKIP")
    passes = sum(1 for level, _ in results if level == "ok")

    print()
    print(f"{passes} verified, {skips} unverifiable from here, {failures} would be rejected")
    if failures:
        print("Not ready for hacs/default.")
    elif skips:
        print("Everything checkable here passes. The skips are real requirements, not noise.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
