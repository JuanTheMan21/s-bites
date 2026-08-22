"""PreToolUse hook: keep vendor SDKs out of core/.

The project's central rule is that business logic in core/ talks to interfaces, never to a
concrete backend. Conventions like that erode -- especially across many sessions with different
models building under time pressure. This makes it mechanical instead.

Exit 2 blocks the write and shows stderr to Claude.
"""

import json
import re
import sys
from pathlib import Path

# Import roots that must never appear under core/. langgraph is handled separately: it is
# permitted, but only inside core/graph/ where orchestration lives.
BANNED = ("adapters", "azure", "openai", "huggingface", "ollama", "playwright", "azure_identity")

IMPORT_LINE = re.compile(r"^\s*(?:from\s+([.\w]+)|import\s+([.\w]+))", re.MULTILINE)


def imported_roots(source: str) -> set[str]:
    """Root module names imported by `source`, ignoring comments and strings."""
    roots = set()
    for match in IMPORT_LINE.finditer(source):
        module = match.group(1) or match.group(2) or ""
        root = module.lstrip(".").split(".")[0]
        if root:
            roots.add(root.lower())
    return roots


def added_source(tool_input: dict) -> str:
    """The text this tool call introduces, for Write and Edit alike."""
    if "content" in tool_input:
        return tool_input["content"]
    return tool_input.get("new_string", "")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on a malformed payload

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path:
        return 0

    path = Path(raw_path).as_posix()
    if "/core/" not in f"/{path}" and not path.startswith("core/"):
        return 0
    if not path.endswith(".py"):
        return 0

    in_graph = "/core/graph/" in f"/{path}" or path.startswith("core/graph/")
    roots = imported_roots(added_source(tool_input))

    violations = sorted(roots & set(BANNED))
    if "langgraph" in roots and not in_graph:
        violations.append("langgraph")

    if not violations:
        return 0

    names = ", ".join(violations)
    print(
        f"BLOCKED: {path} imports {names}.\n\n"
        "core/ must not import vendor SDKs or adapters -- it calls interfaces only, and "
        "config.py chooses the implementation. See CLAUDE.md, 'The one rule'.\n\n"
        "The fix is almost always to move this code into an adapter under adapters/ and depend "
        "on the matching interface instead. Retry, backoff, and rate limiting belong in adapters "
        "too.\n"
        + (
            "langgraph is permitted, but only under core/graph/.\n"
            if "langgraph" in violations
            else ""
        ),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
