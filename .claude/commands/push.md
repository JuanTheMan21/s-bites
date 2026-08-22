---
description: Commit and push the current work
argument-hint: <commit message>
---

Commit and push with the message: **$ARGUMENTS**

Before committing:

1. `git status` and `git diff` — review what is actually staged. Never commit blind.
2. Confirm no secrets: `.env` must not appear, and no key-shaped strings in the diff.
3. Confirm the current task passed `project-reviewer`. If `/checkpoint` has not run for this task,
   say so and ask whether to push anyway — pushing unreviewed work is the user's call, not yours.
4. If on the default branch and this is feature work, offer to branch first.

Then stage, commit with the given message, and push. If no message was given, propose one from the
diff and ask for confirmation.

Report the resulting commit hash and branch.
