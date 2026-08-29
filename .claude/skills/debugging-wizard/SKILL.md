---
name: debugging-wizard
description: General hypothesis-driven debugging methodology — reproduce, isolate, hypothesize/test, fix, prevent — plus git-bisect and pdb tooling. Load for a bug outside pipeline-debugging's known failure list (a FastAPI/React/adapter bug, a flaky test, a regression with no obvious cause), or once a fix attempt has failed twice. For the video pipeline's own recurring failure modes (A/V drift, frozen renders, tier misassignment), load pipeline-debugging first — it's faster for those specific cases.
---

# Debugging wizard

Systematic methodology for bugs that `pipeline-debugging`'s known-failure-mode list doesn't cover —
a FastAPI route, a React component, an adapter that isn't drifting audio but is doing something
else wrong, a flaky test, a regression with no obvious cause. Adapted from the `debugging-wizard`
skill in [jeffallan/claude-skills](https://github.com/jeffallan/claude-skills); the systematic-phase
structure below traces back further to obra/superpowers (MIT).

## Core principle

No fix without a root cause. A fix applied before the cause is understood tends to produce the
"fix one thing, break two more" cycle — especially risky here since `core/` code is shared between
the local and Azure adapters (Invariant 4: adapter parity). A patch that papers over a symptom in
one adapter can silently break the semantic match with the other.

## Core workflow

1. **Reproduce** — get a reliable, documented reproduction before touching anything. If it's in the
   pipeline, `artifacts/<job_id>/` already has every stage's output on disk (see
   `pipeline-debugging`) — use that instead of adding logging.
2. **Isolate** — narrow to the smallest failing case. Run with `RUNTIME_ENV=local` to remove Azure
   as a variable; if the bug reproduces on both stacks it's in `core/`, if only on one it's in that
   adapter (and that's also an adapter-parity finding worth reporting).
3. **Hypothesize and test** — one testable theory, one minimal change, verified before moving on.
4. **Fix** — implement the smallest change that addresses the root cause, not the symptom.
5. **Prevent** — add a regression test. A bug found once and not pinned down with a test will
   reappear.

## Read the error message completely first

Not just the first line — the full traceback, every frame. For a Python stack trace: what exact
operation failed, where (file, line), what was the call chain, is this one error or several
compounding. Trace the failing value backward through the call chain until you find where it
diverged from what was expected — that's usually the actual bug location, not where the exception
was raised.

## The three-fix threshold

After three failed fix attempts in different locations, stop fixing symptoms. Three failures
usually means the problem is architectural, not local — question the design rather than trying a
fourth patch. At that point: document the pattern of failures, name the architectural assumption
that's being violated, and propose a structural change rather than another patch.

Red flags that mean "stop and restart from reproduction," not "try one more thing":

- Proposing a fix before tracing the data flow back to its source
- Changing more than one thing at once (you won't know which change mattered)
- Skipping the regression test because the fix "obviously" works
- "Let's try this and see" — that's shotgun debugging, not hypothesis testing

## Tools

**Python (pdb)**
```bash
python -m pdb script.py
# b 42        set breakpoint at line 42
# n           step over
# s           step into
# p some_var  print variable
# bt          full traceback
```
`pytest --pdb` drops into the debugger at the point of the first test failure — usually faster than
adding print statements to a test.

**Git bisect (regression hunting)** — most useful here because `handoff.md`/`decisionlog.md` give
you good "last known good" reference points per task:
```bash
git bisect start
git bisect bad                   # current commit is broken
git bisect good <last-good-sha>  # e.g. the commit from the previous /checkpoint
git bisect run pytest tests/test_the_failing_area.py   # automate if there's a reliable test
git bisect reset
```

**Delta debugging** — when something recently broke and you don't yet have a specific test:
```bash
git log --oneline -10
git log -p -- path/to/suspect_file.py
```

## Strategy quick reference

| Strategy | Best for |
|---|---|
| Binary search (comment out half, test, repeat) | Unknown bug location in a long pipeline |
| Minimal reproduction | Complex bugs, before filing/reporting |
| Git bisect | Regression — worked before, broken now |
| Trace backward from the error | Known error location, unknown cause |
| Rubber duck (explain line by line) | Logic errors that "should" work |

## Output shape

1. **Root cause** — what specifically caused it, not just where it surfaced
2. **Evidence** — the trace, log, or failing test that proves the cause
3. **Fix** — the specific change, minimal and targeted
4. **Prevention** — the regression test or safeguard added

## Constraints

- Reproduce before proposing a fix — never guess without testing.
- One hypothesis, one change, verified — never stack multiple changes and hope.
- Remove all temporary debug prints/logging before considering the fix done.
- A fix isn't complete without a regression test (this project has no bare-`except` allowance either
  — catch what you can handle, per `CLAUDE.md`).
