"""PostToolUse hook: format, lint, and enforce the structural rules on Python files.

Runs ruff (fix + format), then checks the two rules that shape the codebase rather than merely
tidy it: the 200-line ceiling and the ban on catch-all module names. Both exist to stop modules
from quietly becoming the place where responsibilities -- and boundary violations -- accumulate.

Exit 2 sends the message back to Claude as feedback.
"""

import contextlib
import json
import subprocess
import sys
from pathlib import Path

LINE_LIMIT = 200

# Names that invite unrelated code to pile up. A module should say what it does.
BANNED_NAMES = {"utils.py", "helpers.py", "common.py", "misc.py", "stuff.py", "shared.py"}


def run(cmd: list[str]) -> None:
    # ruff not being installed yet (pre-venv) is not a reason to fail a write.
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(cmd, capture_output=True, timeout=60, check=False)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    raw_path = (payload.get("tool_input") or {}).get("file_path")
    if not raw_path or not raw_path.endswith(".py"):
        return 0

    path = Path(raw_path)
    if not path.exists():
        return 0

    run([sys.executable, "-m", "ruff", "check", "--fix", "-q", str(path)])
    run([sys.executable, "-m", "ruff", "format", "-q", str(path)])

    problems = []

    if path.name in BANNED_NAMES:
        problems.append(
            f"'{path.name}' is a banned module name. Name modules for what they do "
            "(tier_resolver.py, ffmpeg_mux.py). Catch-all modules are where boundary "
            "violations hide."
        )

    try:
        line_count = len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0

    if line_count > LINE_LIMIT:
        problems.append(
            f"{path.name} is {line_count} lines, over the {LINE_LIMIT}-line ceiling.\n"
            "Split it by responsibility -- do not compress it. If one module is doing two "
            "things, that is the signal to separate them."
        )

    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 2

    # The tier resolver is the one piece with full test coverage and no dependencies; keep it green.
    if path.as_posix().endswith("core/tier_resolver.py"):
        test = Path("tests/test_tier_resolver.py")
        if test.exists():
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test), "-q"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                print(
                    f"tier_resolver tests failing after this edit:\n{result.stdout[-2000:]}",
                    file=sys.stderr,
                )
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
