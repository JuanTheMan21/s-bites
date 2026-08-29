---
name: python-pro
description: Python 3.11+ typing, async, and pytest patterns — Protocol/generics, dataclasses, TaskGroup, fixtures and mocking. Load when writing or reviewing code in core/, interfaces/, adapters/, or tests/, or when a type hint, async pattern, or pytest fixture needs a concrete example rather than a reminder of the rule.
---

# Python pro

Concrete patterns for the type-safe, async-first Python this project already requires (`CLAUDE.md`:
type hints on every public function, Pydantic for anything crossing a boundary, no bare `except`).
This skill is the "how," not the "whether" — the rules themselves live in `CLAUDE.md` and
`adapter-contract`. Adapted from the `python-pro` skill in
[jeffallan/claude-skills](https://github.com/jeffallan/claude-skills).

## Where this project's conventions differ from generic Python advice

- **Interfaces here are `ABC`, not `Protocol`.** Every file in `interfaces/` (see
  `interfaces/tts_provider.py` for the canonical example) defines its contract as an
  `abstractmethod`-bearing `ABC`, because the interface also carries docstrings that are part of the
  contract (units, error semantics, what "empty" means) — `Protocol` doesn't have a natural home for
  that. Reach for `Protocol` inside `core/` for a small structural shape that doesn't deserve a whole
  adapter-backed interface, not as a replacement for the six ABCs.
- **Anything crossing a boundary is a Pydantic `BaseModel`, not a bare dataclass.** Adapter return
  values, LLM-validated payloads, anything the `json_schema` strict-mode contract touches — Pydantic,
  with `model_config = ConfigDict(extra="forbid")` on strict-schema types (see `WordMark` /
  `SynthesisResult` in `interfaces/tts_provider.py`). Reach for a plain `@dataclass` for a value
  object that stays inside one module and never gets serialized.
- **Retry/backoff/rate-limiting belongs in adapters, never in `core/`** — don't reach for `tenacity`
  or a manual retry loop inside `core/` even if a pattern here suggests it; that logic is an adapter
  concern by design (`CLAUDE.md`).

## Type system

```python
from typing import Protocol, TypeVar, Generic, Literal, Self, TypeAlias

# Prefer X | None over Optional[X] (3.10+), and collections.abc over typing for containers
from collections.abc import Sequence, Mapping, Callable

def find_user(user_id: int | str) -> dict[str, str] | None: ...

# Protocol for a structural shape inside core/ that doesn't need a full ABC
class Rankable(Protocol):
    def rank_key(self) -> float: ...

def top_n(items: Sequence[Rankable], n: int) -> list[Rankable]:
    return sorted(items, key=lambda x: x.rank_key(), reverse=True)[:n]

# Generic class
T = TypeVar("T")

class Cache(Generic[T]):
    def __init__(self) -> None:
        self._data: dict[str, T] = {}
    def get(self, key: str) -> T | None:
        return self._data.get(key)

# Literal for a closed set of string values (e.g. RUNTIME_ENV)
RuntimeEnv: TypeAlias = Literal["local", "azure"]

# Self for fluent builders
class Builder:
    def add(self, n: int) -> Self:
        ...
        return self

# Exhaustiveness checking on a closed enum/Literal
from typing import assert_never

def handle(env: RuntimeEnv) -> str:
    if env == "local":
        return "local"
    elif env == "azure":
        return "azure"
    else:
        assert_never(env)
```

`mypy --strict` config, if/when this project adds mypy:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
disallow_untyped_defs = true
no_implicit_optional = true
```

## Async patterns

Relevant anywhere the pipeline fans out concurrent adapter calls (TTS, LLM, render) — see
`AZURE_OPENAI_MAX_CONCURRENCY` and `scripts/measure_segment_concurrency.py`.

```python
import asyncio
from asyncio import TaskGroup, Semaphore

# Structured concurrency (3.11+) - prefer over asyncio.gather when any task can fail
async def process_batch(items: list[int]) -> list[int]:
    async with TaskGroup() as tg:
        tasks = [tg.create_task(process_item(item)) for item in items]
    return [t.result() for t in tasks]
    # a single failing task cancels the rest and raises ExceptionGroup - no silent partial results

# Semaphore for bounded fan-out (the pattern behind AZURE_OPENAI_MAX_CONCURRENCY)
class RateLimiter:
    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = Semaphore(max_concurrent)
    async def process(self, item: str) -> str:
        async with self._semaphore:
            return await expensive_call(item)

# Timeout a single call rather than letting a hung adapter block the graph
async def fetch_with_timeout(coro, timeout: float):
    try:
        async with asyncio.timeout(timeout):
            return await coro
    except TimeoutError:
        raise ProviderUnavailable("timed out") from None

# Async context manager for a resource that needs guaranteed cleanup
class AsyncResource:
    async def __aenter__(self) -> Self:
        self._conn = await connect()
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._conn.close()
```

Never mix a blocking call into an `async def` without `run_in_executor` — a synchronous Playwright
call or a blocking `subprocess.run` inside an async node stalls the whole event loop, not just that
task.

## Testing (pytest)

This project's suite runs against fakes, no network (`CLAUDE.md`: `pytest` must be runnable
offline). Fixtures and fakes are how that holds.

```python
import pytest
from collections.abc import Iterator

# Fixture with cleanup - the fake-adapter pattern this project's tests rely on
@pytest.fixture
def fake_tts_provider() -> Iterator[TTSProvider]:
    provider = FakeTTSProvider()
    yield provider
    provider.reset()

# Parametrize over the interesting cases, not one test per case
@pytest.mark.parametrize(
    "duration_ms,expected_tier",
    [(0, 0), (1500, 1), (8000, 2)],
    ids=["instant", "short", "long"],
)
def test_tier_resolution(duration_ms: int, expected_tier: int) -> None:
    assert resolve_tier(duration_ms) == expected_tier

# Async test
@pytest.mark.asyncio
async def test_synthesize_returns_measured_duration(fake_tts_provider: TTSProvider) -> None:
    result = await fake_tts_provider.synthesize("hello", Path("out.wav"))
    assert result.duration_ms > 0

# Mock only at the adapter boundary - never mock core/ business logic itself
from unittest.mock import AsyncMock

async def test_retries_on_rate_limit() -> None:
    mock_client = AsyncMock()
    mock_client.call.side_effect = [RateLimited("429"), {"status": "ok"}]
    result = await call_with_retry(mock_client)
    assert result["status"] == "ok"
```

Prefer a `Fake*` implementation of the relevant interface (matching what an adapter would return)
over mocking individual methods — it exercises the same contract every real adapter is held to, and
it's usually what an `adapter-parity` check expects to find already exercised in tests.

## Constraints

- Type hints on every public function signature — no exceptions for "it's obvious."
- No mutable default arguments (`def f(items: list = [])` — use `None` + `field(default_factory=...)`
  or a local default inside the body).
- No bare `except:` — catch the specific exception type you can actually handle (`CLAUDE.md`).
- `X | None`, not `Optional[X]`.
- Dataclasses/plain classes for internals; Pydantic `BaseModel` for anything crossing an
  interface/adapter boundary or touching structured LLM output.
- Async for I/O-bound adapter calls; never a blocking call inside `async def` without an executor.
