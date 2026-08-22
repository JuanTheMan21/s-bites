---
name: adapter-contract
description: How the interface/adapter boundary works in this project and how to extend it. Load when adding or modifying anything in interfaces/, adapters/, or config.py, or when a boundary hook has blocked a write.
---

# The adapter contract

The project's central claim is that swapping a local stack for Azure is a config change, not a
refactor. Everything here exists to keep that true.

## The shape

```
core/  ──calls──>  interfaces/  <──implements──  adapters/local/
                                <──implements──  adapters/azure/
                                       ▲
                                  config.py picks one
```

`config.py` is the **only** module in the repo permitted to name a concrete adapter class. If a
second module needs to know which adapter is active, that is a design error — pass the instance in.

## Writing an interface

An interface is correct when both a local and an Azure implementation can satisfy it without either
one contorting. Two failure modes to watch for:

**Too vendor-specific.** A parameter like `deployment_name` or a return type from an SDK means the
interface was written from one implementation's perspective. The other adapter then has to fake it.

**Too vague.** `generate(prompt: str) -> str` is implementable by anyone but pushes JSON parsing,
schema validation, and repair logic up into `core/` — which is exactly what the boundary exists to
prevent. The real signature is:

```python
def generate(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...
```

Taking a pydantic class lets the Azure adapter use strict `json_schema` and the Ollama adapter use
its format constraint, from one signature, with validation living on the adapter side where it
belongs.

The same principle drives `TTSProvider`:

```python
def synthesize(self, text: str) -> tuple[Path, int]:   # (audio_path, duration_ms)
```

Returning measured duration is not a convenience — it is how the TTS-before-scene-authoring rule
becomes structurally enforceable instead of a comment someone eventually ignores.

## Writing an adapter

Everything vendor-specific lives here and stops here:

- Retry, backoff, rate limiting, concurrency bounds
- Authentication and credential handling
- Schema dialect quirks — Azure strict mode requires every field `required` and
  `additionalProperties: false`; the schema emitter must satisfy that or strict mode rejects it
- **Exception translation.** Vendor exceptions must never escape the adapter. Callers cannot catch
  `azure.core.exceptions.*` and stay portable.

Units are the most common parity bug. `duration_ms` is milliseconds in every implementation, always.

## Stubs are load-bearing

An unimplemented adapter with exact signatures and a `NotImplementedError` naming what is missing
is what makes "switchable later" reviewable now. A stub whose signatures have drifted is worse than
nothing — it makes the boundary look verified when it is not.

## When the hook blocks you

The `PreToolUse` boundary hook blocks vendor imports in `core/`. When it fires, the fix is nearly
always to move the code into an adapter and depend on the interface.

Genuine cases where the interface itself is wrong do exist — the signature cannot express what
`core/` legitimately needs. Then the fix is to **change the interface**, propagate it to both
implementations, and record why in `decisionlog.md`. What is never the fix: routing around the hook,
aliasing the import, or moving the logic to a file that happens to sit outside `core/`.

## Verify

```bash
grep -rE "^\s*(from|import)\s+(adapters|azure|openai|huggingface|ollama|playwright)" core/ --include=*.py
grep -rn "langgraph" core/ --include=*.py | grep -v "^core/graph/"
```

Both empty. Then run the `adapter-parity` agent.
