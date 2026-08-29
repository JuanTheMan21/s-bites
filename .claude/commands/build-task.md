---
description: Load context and plan the next build task (run at the start of a session)
argument-hint: <task-id, e.g. T3>
model: opus
---

Plan the implementation of task **$1**.

## Load context first

Read, in this order:

1. `handoff.md` — current state, environment, known gaps. This is the most important file.
2. The `$1` entry in `tasks.md` — intent, DoD, dependencies.
3. `decisionlog.md` — scan for decisions bearing on `$1`. **If a past decision constrains this
   task, follow it.** If you believe it should be reopened, say so explicitly with your reasoning
   rather than quietly working around it.
4. `CLAUDE.md` — the rules. Non-negotiable unless the user overrides them in this session.

Then survey the existing code for what `$1` should reuse. If the RepoWise MCP server is available,
query it rather than reading files directly — that is what it is for. Otherwise use Grep and Glob,
and read only the files that matter.

## Check readiness

Confirm `$1`'s dependencies are `done` in `tasks.md`. If they are not, say so and stop — building
on an incomplete dependency produces work that gets thrown away.

Check whether anything in `handoff.md`'s "Before the next session" section is still outstanding
(venv, `az login`, provisioning). If so, flag it before planning, not after.

## Then plan

Enter plan mode and produce a plan for `$1` covering:

- Exactly which files will be created or modified
- The interfaces and existing code being reused, by path
- Which side of the `core/` boundary each piece of new code belongs on, and why
- How the DoD will be verified concretely — the command to run, the assertion to check
- Anything genuinely ambiguous in the task description, raised as a question rather than
  assumed away

Keep the plan proportional to the task. Do not expand scope beyond `$1` — later tasks exist for
later work, and pulling their scope forward is how iterations slip.

**Stop after presenting the plan.** The user will approve it, then switch to a smaller model for
the build. That model reads the plan, not this conversation, so the plan must stand on its own.

**Do not trust the model to switch itself.** This has shipped a real build on Opus twice already
(T18A entirely, T18B until the user caught it) — the harness does not reliably revert to Sonnet
just because this command's own `model: opus` frontmatter only applies to this one turn; a session
already pinned to a specific model by an explicit `/model` call stays pinned. So: the moment the
plan is approved, **before making any `Write`/`Edit`/`Bash` call**, check your own current-model
line from this turn's system info. If it is not Sonnet, stop immediately and tell the user plainly
which model you are on and that `/model sonnet` needs to run first. Do not begin the build on the
wrong model "just this once" — CLAUDE.md's "Which model runs what" section is the durable version
of this rule; this is the reminder at the exact moment it matters.
