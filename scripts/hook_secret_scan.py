"""Stop hook: catch credentials before they reach a commit.

Scans tracked, uncommitted changes for things that look like Azure keys or connection strings.
Advisory -- it reports, it does not block, because the false-positive cost of blocking at the end
of a session is higher than the miss cost of a warning you can act on.
"""

import re
import subprocess
import sys

PATTERNS = [
    (re.compile(r"DefaultEndpointsProtocol=.*AccountKey=[^;\s]{20,}"), "storage connection string"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"AccountKey=[A-Za-z0-9+/=]{40,}"), "storage account key"),
    (
        re.compile(r"(?i)\b(api[_-]?key|speech[_-]?key)\s*[:=]\s*[\"'][A-Za-z0-9]{24,}[\"']"),
        "hardcoded key",
    ),
]

# .env is gitignored; example files are supposed to contain placeholder shapes.
SKIP = ("/.env", ".env.example", "hook_secret_scan.py")


def changed_lines() -> list[tuple[str, str]]:
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--unified=0"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    out, current = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            out.append((current, line[1:]))
    return out


def main() -> int:
    findings = []
    for path, line in changed_lines():
        if any(skip in path for skip in SKIP):
            continue
        for pattern, label in PATTERNS:
            if pattern.search(line):
                findings.append(f"  {path}: possible {label}")
                break

    if findings:
        print("Possible secrets in uncommitted changes:", file=sys.stderr)
        print("\n".join(sorted(set(findings))), file=sys.stderr)
        print("Move these to .env (gitignored) before committing.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
