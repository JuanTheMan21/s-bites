---
description: Refresh the RepoWise codebase index
---

Trigger a RepoWise reindex of this repository so subsequent queries reflect current code.

If the RepoWise MCP server is not connected, say so plainly and note that code search will fall
back to Grep and Glob — do not silently continue as if it succeeded.

Report what was indexed and anything the index flags as notable (health, dead code, hotspots).
