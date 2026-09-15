#!/usr/bin/env python3
"""Local stand-in for the parts of hassfest that matter most to this integration.

hassfest runs as a Docker action and cannot run on a machine with no daemon, so this covers
the checks whose failure is expensive:

1. manifest.json has every required key, in hassfest's order.
2. strings.json and translations/en.json have identical key trees.
3. Every third-party module the integration imports is declared in manifest requirements.

Check 3 is the one that matters. The community integration this project replaces declared
`"requirements": []` while importing async_timeout and pydub, and neither is an HA dependency,
so the integration could not load at all. A CI-visible check is cheaper than that discovery.

Usage: python3 scripts/manifest_check.py
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import sysconfig

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "deepgram_tts"

# Anything HA core already ships. Importing one of these needs no manifest requirement.
HA_PROVIDED = {"homeassistant", "aiohttp", "voluptuous", "yarl", "attr", "attrs", "propcache"}

REQUIRED_KEYS = [
    "domain",
    "name",
    "codeowners",
    "config_flow",
    "documentation",
    "integration_type",
    "iot_class",
    "issue_tracker",
    "requirements",
    "version",
]


def stdlib_modules() -> set[str]:
    """Top-level stdlib module names for the running interpreter."""
    return set(sys.stdlib_module_names) | {"__future__"}


def top_level_imports(path: Path) -> set[str]:
    """Every top-level module name imported by a python file, relative imports excluded."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def check_manifest(manifest: dict) -> list[str]:
    errors = []
    keys = list(manifest)
    missing = [key for key in REQUIRED_KEYS if key not in keys]
    if missing:
        errors.append(f"manifest.json missing keys: {', '.join(missing)}")

    # Only the keys we require are order checked, and only against each other. Optional keys
    # like `dependencies` and `after_dependencies` are legal and may appear anywhere, so
    # comparing the whole key list against REQUIRED_KEYS reported a false ordering failure for
    # a manifest that was correct.
    present = [key for key in keys if key in REQUIRED_KEYS]
    expected = [key for key in REQUIRED_KEYS if key in keys]
    if present != expected:
        errors.append(f"manifest.json required keys out of hassfest order: {present}")
    if manifest.get("single_config_entry"):
        errors.append("single_config_entry is set; two entries must stay possible")
    return errors


def key_tree(value: object, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix}
    out: set[str] = set()
    for key, child in value.items():
        out |= key_tree(child, f"{prefix}.{key}" if prefix else key)
    return out


def check_translations() -> list[str]:
    strings = json.loads((COMPONENT / "strings.json").read_text())
    english = json.loads((COMPONENT / "translations" / "en.json").read_text())
    only_strings = key_tree(strings) - key_tree(english)
    only_english = key_tree(english) - key_tree(strings)
    errors = []
    if only_strings:
        errors.append(f"in strings.json but not translations/en.json: {sorted(only_strings)}")
    if only_english:
        errors.append(f"in translations/en.json but not strings.json: {sorted(only_english)}")
    return errors


def check_requirements(manifest: dict) -> list[str]:
    declared = {
        requirement.split("==")[0].split(">=")[0].strip().replace("-", "_").lower()
        for requirement in manifest.get("requirements", [])
    }
    local = {path.stem for path in COMPONENT.glob("*.py")}
    allowed = stdlib_modules() | HA_PROVIDED | local | declared | {"custom_components"}

    errors = []
    for path in sorted(COMPONENT.rglob("*.py")):
        for module in sorted(top_level_imports(path)):
            if module.replace("-", "_").lower() not in allowed:
                errors.append(
                    f"{path.relative_to(ROOT)} imports {module!r}, "
                    "which is neither stdlib, HA-provided, nor in manifest requirements"
                )
    return errors


def main() -> int:
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    errors = check_manifest(manifest) + check_translations() + check_requirements(manifest)

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1

    print(f"ok  manifest, translations, and imports agree ({sysconfig.get_python_version()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
