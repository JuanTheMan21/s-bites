# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-22 · after T3_

---

## Where we are

Iteration 1 has started. The six contracts exist and are the only product code in the repo —
`core/`, `adapters/`, `rendering/` and `mux/` are still empty packages. Nothing implements anything
yet, by design.

**Done:** T1 (scaffold), T2 (operating system), T3 (the six interfaces)
**Next:** T4 — domain models

## Next task: T4 — Domain models

`Segment`, `VisualIntent` (closed enum), `Tier`, `VideoJob`, plus the per-intent pydantic slot
schemas the LLM fills. One definition serving three uses: LLM structured output, internal state, and
later the API contract.

Four things to get right:

- **Target length must be a parameter.** `VideoJob` carries `target_duration_ms`. Nothing may
  hardcode 7 minutes or 15 segments — segment count is *derived* (~28s of narration each), so a
  10-minute request produces ~21 segments on its own. This is written into `tasks.md` under T4 as
  well, because it is the kind of thing that gets rediscovered at T15 when the outline node has
  already hardcoded a 15.
- **Azure strict mode constrains every schema.** Every field `required`, `additionalProperties:
  false`. A schema violating that is rejected outright rather than returning bad data, and since
  Azure is now the primary stack, this is not a future concern. Optionality has to be expressed as
  an explicit nullable field, not an absent one.
- **These models must not leak into `interfaces/`.** The dependency runs T3 → T4, never back.
  `SkillPack` and `QueuedJob` already live in `interfaces/` for exactly this reason (D22); don't
  duplicate them in `core/models`.
- **Slot schemas are per-intent.** One schema per `VisualIntent` member, since the point is that the
  LLM fills slots a template owns. `scene-templates` skill has the shape.

## What T3 actually produced

Eight files in `interfaces/`, 35-108 lines each, plus `tests/test_interfaces.py` (153 lines,
47 tests). All contracts, no implementations.

| Contract | Surface |
|---|---|
| `LLMProvider` | `generate(prompt, schema: type[T]) -> T` |
| `TTSProvider` | `synthesize(text, dest) -> (Path, duration_ms)` |
| `Storage` | `put_bytes` `put_file` `get_bytes` `get_file` `exists` `url` |
| `SkillRegistry` | `load` `versions` `list_packs` (+ `SkillPack`) |
| `JobQueue` | `enqueue` `dequeue` `complete` `fail` (+ `QueuedJob`) |
| `RenderBackend` | `capture` `render` `lint` |

All methods are `async` (D19). Every method docstring states **units, the empty/missing case, and
which error it raises** — those docstrings are the parity spec T13 tests both adapters against, so
treat them as contract, not commentary. When a signature or an error changes, the docstrings that
paraphrase it must change in the same edit; four rounds of review were spent on exactly that kind of
drift during T3.

The error vocabulary is in `interfaces/errors.py`. Two things about it that are load-bearing:
`CompositionInvalid` sits **outside** the `AdapterError` family on purpose (D23), and every concrete
error states its own `Retry:` answer because family membership cannot (D24).

## Environment state

| | |
|---|---|
| `RUNTIME_ENV` | `local` in `.env.example`; **flips to `azure` at T8** (D25) |
| Python | 3.11.0, venv **exists and is populated** at `.venv/` |
| Toolchain | pydantic 2.13.4, pytest 9.1.1, pytest-asyncio, ruff 0.16.4 |
| Node | 24.16.0 · ffmpeg 8.1.1 on PATH |
| Azure | PAYG, $200/30-day credit. **Nothing provisioned** — that is T8 |
| Git | initialized, **still no commits** |
| RepoWise | CLI now installed and on PATH; **not registered in `.mcp.json`** |

Use `.venv/Scripts/python.exe` explicitly — the venv is not auto-activated in a fresh shell.

## Before the next session

Nothing blocks T4 — it is pure pydantic and runs offline.

Two things worth doing anyway:

```bash
az login                    # required by the Azure MCP server, and by T8
repowise init               # registers itself in .mcp.json; there is now code worth indexing
```

**T8 is the real deadline.** T4-T7 are the last work that runs entirely offline. Nothing past T7
moves without a resource group, a model deployment, a Speech resource, a storage account, and a
filled-in `.env`. T8's DoD deliberately demands a raw completion and a raw TTS call from the command
line *before* any adapter code is written, because a mis-provisioned subscription with zero TPM
quota fails silently and looks like an adapter bug for hours.

## Known gaps and open questions

- **Nothing is committed.** T1-T3 exist only on this disk. `/push` was offered at this checkpoint.
- **No family for "our own code judged this invalid" errors.** `CompositionInvalid` inherits
  `Exception` directly. A one-member base class was judged speculative during T3, so `errors.py`'s
  module docstring instead names the mistake explicitly. **Decide this at T17**, when a second such
  error plausibly appears — if one does, give them a shared base rather than letting a bare list
  accumulate.
- **`StructuredOutputError` has no way to say "retry, but bounded."** The `Retry:` vocabulary is
  binary. **T14 owns this**: cap it with `QueuedJob.attempt` rather than treating it as freely
  retryable. Named in the docstring so it is not lost.
- **A wrong endpoint URL looks retryable.** It is indistinguishable from an outage at the adapter
  layer, so it arrives as `ProviderUnavailable`. Accepted (D24); T8's command-line verification is
  the mitigation.
- **`JobQueue` documents no `Raises:` per method** — stated on the class instead. The in-process
  implementation never fails that way, so code written against the local pool alone will not have
  seen it. A parity trap for T34.
- **Scope: 35 tasks across 8 iterations.** Iterations 0-3 deliver a working video generator; 4-6 are
  product surface. Still worth confirming with your manager whether RAG (iteration 6) or frontend
  polish (iteration 5) matters more *before* iteration 4 — RAG is scheduled to be the first casualty
  if time compresses, and iteration 5.5 has now been added ahead of it.
- **HyperFrames is not installed.** Needed by T17. `npx hyperframes doctor` when we get there. The
  `hyperframes lint` hook silently no-ops until then, as expected.

## Gotchas worth remembering

- The boundary hook blocks vendor imports in `core/`. If it fires, move the code into an adapter —
  do not work around the hook.
- The hooks fire on `Write|Edit`, **not on Bash heredocs**. Building files through the shell skips
  ruff, the 200-line check, and the boundary check. Run `ruff check . && ruff format .` manually
  after doing that.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
