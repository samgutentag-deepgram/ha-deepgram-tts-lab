"""Can scripts/manifest_check.py be fooled, and does it false-positive?

    .venv/bin/python docs/review/repro/repro_manifest_check.py

Copies the repo into a scratch tree, plants each attack, and runs the real script as a
subprocess. Prints the script's exit code and output per case. The repo itself is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path("/Users/samgutentag/LABS/ha-deepgram-tts-lab/.claude/worktrees/agent-a72565c57ade8ce4a")
PYTHON = "/Users/samgutentag/LABS/ha-deepgram-tts-lab/.venv/bin/python"


def run_case(name: str, expectation: str, mutate) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        shutil.copytree(
            REPO,
            root,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".claude"),
        )
        mutate(root / "custom_components" / "deepgram_tts")
        proc = subprocess.run(
            [PYTHON, "scripts/manifest_check.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (proc.stdout + proc.stderr).strip().splitlines()
        verdict = "CAUGHT" if proc.returncode != 0 else "PASSED"
        print(f"{verdict:<7} {name}")
        print(f"        expected: {expectation}")
        for line in out[:4]:
            print(f"        | {line}")
        print()


def plant(component: Path, filename: str, body: str) -> None:
    (component / filename).write_text(body, encoding="utf-8")


print(f"python {sys.version.split()[0]}\n")

run_case(
    "baseline, repo as committed",
    "PASSED (nothing planted)",
    lambda component: None,
)

run_case(
    "plain `import pydub` at module level",
    "CAUGHT, this is the bug the script exists for",
    lambda c: plant(c, "sneak.py", '"""S."""\n\nimport pydub\n\nprint(pydub)\n'),
)

run_case(
    "`import pydub` inside a function body",
    "CAUGHT (ast.walk sees nested imports)",
    lambda c: plant(
        c, "sneak.py", '"""S."""\n\n\ndef go():\n    """G."""\n    import pydub\n\n    return pydub\n'
    ),
)

run_case(
    "`import pydub` inside a try/except ImportError",
    "CAUGHT (this is exactly how the old integration hid it)",
    lambda c: plant(
        c,
        "sneak.py",
        '"""S."""\n\ntry:\n    import pydub\nexcept ImportError:\n    pydub = None\n',
    ),
)

run_case(
    "`import pydub` under `if TYPE_CHECKING:`",
    "CAUGHT, arguably a false positive for a typing-only import",
    lambda c: plant(
        c,
        "sneak.py",
        '"""S."""\n\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import pydub\n',
    ),
)

run_case(
    "importlib.import_module('pydub')",
    "FOOLED: no Import node exists to find",
    lambda c: plant(
        c,
        "sneak.py",
        '"""S."""\n\nimport importlib\n\npydub = importlib.import_module("pydub")\n',
    ),
)

run_case(
    "__import__('pydub')",
    "FOOLED: same reason",
    lambda c: plant(c, "sneak.py", '"""S."""\n\npydub = __import__("pydub")\n'),
)

run_case(
    "a sibling module named pydub.py, plus `import pydub` elsewhere",
    "FOOLED: the stem whitelists the name, but Python 3 resolves it to the installed package",
    lambda c: (
        plant(c, "pydub.py", '"""Decoy."""\n'),
        plant(c, "sneak.py", '"""S."""\n\nimport pydub\n\nprint(pydub)\n'),
    ),
)

run_case(
    "a subpackage that imports a third-party module",
    "CAUGHT (rglob scans subpackages)",
    lambda c: (
        (c / "sub").mkdir(),
        plant(c / "sub", "__init__.py", '"""Sub."""\n'),
        plant(c / "sub", "helper.py", '"""H."""\n\nimport pydub\n\nprint(pydub)\n'),
    ),
)

run_case(
    "a subpackage imported absolutely by its own package path",
    "FALSE POSITIVE: `local` is a non-recursive glob, so the subpackage name is not known",
    lambda c: (
        (c / "sub").mkdir(),
        plant(c / "sub", "__init__.py", '"""Sub."""\n'),
        plant(c / "sub", "helper.py", '"""H."""\n'),
        plant(
            c,
            "user.py",
            '"""U."""\n\nfrom custom_components.deepgram_tts.sub import helper\n\nprint(helper)\n',
        ),
    ),
)


def add_manifest_key(component: Path) -> None:
    path = component / "manifest.json"
    manifest = json.loads(path.read_text())
    ordered = {}
    for key, value in manifest.items():
        ordered[key] = value
        if key == "config_flow":
            # hassfest's real order puts dependencies here. It is a legal optional key.
            ordered["dependencies"] = ["tts"]
    path.write_text(json.dumps(ordered, indent=2))


run_case(
    'a legal optional manifest key ("dependencies")',
    "FALSE POSITIVE: the order check cannot tolerate any key outside REQUIRED_KEYS",
    add_manifest_key,
)
