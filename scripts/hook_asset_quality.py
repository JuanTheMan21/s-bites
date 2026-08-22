"""PostToolUse hook for non-Python assets: scene templates and frontend sources.

Scene templates are linted by HyperFrames itself -- catching an invalid composition at write time
is far cheaper than discovering it mid-render, several minutes into a job.

Both branches no-op silently when their toolchain is absent, which is the normal state until T17
(HyperFrames) and T24 (frontend) respectively.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], timeout: int = 90) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def lint_scene_template(path: Path) -> int:
    if not shutil.which("npx"):
        return 0
    result = run(["npx", "--no-install", "hyperframes", "lint", str(path)])
    if result is None or result.returncode == 0:
        return 0
    # A missing local install exits non-zero too; only surface real lint output.
    combined = f"{result.stdout}{result.stderr}"
    if "could not determine executable" in combined.lower() or "not found" in combined.lower():
        return 0
    print(f"hyperframes lint failed for {path.name}:\n{combined[-2000:]}", file=sys.stderr)
    return 2


def format_frontend(path: Path) -> int:
    if not Path("web/node_modules").exists():
        return 0
    run(["npx", "--no-install", "prettier", "--write", str(path)])
    run(["npx", "--no-install", "eslint", "--fix", str(path)])
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    raw_path = (payload.get("tool_input") or {}).get("file_path")
    if not raw_path:
        return 0

    path = Path(raw_path)
    if not path.exists():
        return 0

    posix = path.as_posix()
    if posix.endswith(".html") and "rendering/templates" in posix:
        return lint_scene_template(path)
    if path.suffix in (".ts", ".tsx", ".jsx") and "web/" in posix:
        return format_frontend(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
