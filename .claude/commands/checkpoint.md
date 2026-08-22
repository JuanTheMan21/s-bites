---
description: Review, record decisions, rewrite the handoff, and close out the current task
---

Close out the task that was just built. Work through these in order — each step depends on the one
before it.

## 1. Review gate

Launch the `project-reviewer` agent on the current diff.

If it reports findings above a trivial severity, **stop here and report them.** Do not write the
decision log or handoff for work that has not passed review — a checkpoint that records broken work
as done is worse than no checkpoint, because the next session trusts it.

Then run the mechanical checks:

```bash
pytest -q
ruff check .
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py
grep -rn "langgraph" core/ --include=*.py | grep -v "^core/graph/"
```

Both greps must come back empty. Report any `.py` file over 200 lines.

## 2. Append to `decisionlog.md`

Add an entry for any **non-obvious** choice made during this task — a tradeoff, a rejected
alternative, a constraint discovered mid-build. Format:

```
### D<n> — <decision, stated as a claim>
**Rejected:** <the alternative that was seriously considered>
**Reasoning:** <why, in terms that will still make sense in a month>
```

Append only. Never edit or delete existing entries.

Routine implementation choices do not belong here. The test: would someone reading this in three
weeks be confused about why the code looks this way? If not, leave it out. A decision log padded
with obvious choices stops being read.

## 3. Rewrite `handoff.md`

**Replace the file entirely.** It describes the present, not the past — history is what
`decisionlog.md` is for. It must contain:

- What was just completed and what is next, with the task id
- Enough orientation on the next task that a fresh session can start without re-deriving context —
  including the specific traps or subtleties worth knowing
- Current environment state (`RUNTIME_ENV`, provisioning, installed tooling)
- Anything outstanding the user must do themselves before the next session
- Known gaps, open questions, and anything discovered during this task that changes later ones

If this task invalidated an assumption in a later task's description, **update that task in
`tasks.md` now.** Stale task descriptions are how plans quietly drift from reality.

## 4. Mark the task done

Update its status in `tasks.md` to `done`.

## 5. Reindex

If the RepoWise MCP server is available, trigger a reindex so the next session sees current code.

## 6. Offer to push

Summarize what changed and propose a commit message. **Ask before pushing** — do not push
automatically.
