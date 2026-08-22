"""SessionStart hook: print which stack is active and what the current task is.

Cheap orientation. Most wasted time at the start of a session comes from not knowing which
adapters are wired or which task was next.
"""

import os
import re
import sys
from pathlib import Path

ADAPTERS = {
    "local": "Ollama | Kokoro | disk | asyncio pool | Playwright+HyperFrames",
    "azure": "Azure OpenAI | Azure Speech | Blob | (queue/render stubbed)",
}


def env_value(name: str, default: str) -> str:
    """Read from the process env, falling back to .env, then to a default."""
    if name in os.environ:
        return os.environ[name]
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


def current_task() -> str:
    handoff = Path("handoff.md")
    if not handoff.exists():
        return "no handoff.md -- start with T1"
    match = re.search(r"^\*\*Next:\*\*\s*(.+)$", handoff.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1).strip() if match else "see handoff.md"


def ascii_safe(text: str) -> str:
    """The Windows console is not reliably UTF-8; normalize the punctuation we actually use."""
    for fancy, plain in (("—", "-"), ("–", "-"), ("·", "|"), ("’", "'")):  # noqa: RUF001
        text = text.replace(fancy, plain)
    return text.encode("ascii", "replace").decode("ascii")


def main() -> int:
    runtime = env_value("RUNTIME_ENV", "local")
    wiring = ADAPTERS.get(runtime, "unknown RUNTIME_ENV")

    print(f"RUNTIME_ENV={runtime}  ->  {wiring}")
    print(f"Next task: {ascii_safe(current_task())}")
    if not Path(".env").exists():
        print("note: .env missing -- copy .env.example and fill it in before any Azure task")
    return 0


if __name__ == "__main__":
    sys.exit(main())
