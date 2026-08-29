---
name: the-fool
description: Devil's-advocate / pre-mortem stress-testing for a plan, architecture choice, or decision before committing to it. Load when about to lock in an adapter or interface design, before recording a decision in decisionlog.md, or whenever the user asks "what could go wrong," "poke holes in this," or wants a second opinion before /checkpoint closes out a task.
---

# The Fool

Structured critical reasoning for stress-testing an idea before it becomes committed work — an
architecture choice, an adapter design, a decision about to be written into `decisionlog.md`. Five
modes, each a different angle of attack. Adapted from the `the-fool` skill in
[jeffallan/claude-skills](https://github.com/jeffallan/claude-skills).

## When to use this

Reach for this before a decision hardens, not after: before choosing between two adapter designs,
before scoping a task in `tasks.md` that assumes something untested, before `/checkpoint` writes a
decision into `decisionlog.md` that later tasks will build on. It is not a replacement for
`project-reviewer` (which checks a diff against invariants that already exist) — this is for
decisions that haven't been made yet.

## Core workflow

1. **Steelman first.** Restate the plan or decision in its strongest form before challenging it.
   Confirm that restatement is accurate before proceeding — challenging a strawman produces
   nothing useful.
2. **Pick a mode.** Match the situation to one of the five below, or ask the user which angle they
   want.
3. **Challenge.** Apply the mode's method. Present the 3-5 strongest points — not a pile of minor
   objections. Depth over breadth.
4. **Let the user respond.** Don't synthesize past their input.
5. **Synthesize.** Integrate what held up into a strengthened position. Offer a second pass with a
   different mode if the domain spans more than one of the categories below.

## Five modes

| Mode | Method | Use when |
|---|---|---|
| Expose assumptions | Socratic questioning | The plan feels obvious or has quiet consensus ("everyone agrees...") |
| Argue the other side | Hegelian dialectic + steel manning | About to commit to X over Y; needs the strongest counter-argument |
| Find failure modes | Pre-mortem + second-order thinking | "This will definitely work" overconfidence; architecture or infra decisions |
| Attack this | Red teaming | Security-adjacent design, anything gameable, adapter boundary that touches untrusted input |
| Test the evidence | Falsificationism + evidence grading | A decision leans on a claim ("the pilot showed...", "Azure docs say...") |

### Expose assumptions (Socratic)

Ask what's being taken for granted rather than asserting a counter-position. Group probing
questions by theme (technical, timeline, people). Good for a plan that sounds right because no one
has pushed on it yet.

### Argue the other side (Dialectic)

Construct the strongest real counter-argument, not a token one. State a synthesis: what survives
from both positions. Rate confidence in the final position. Use this before locking in a choice
between two named alternatives (e.g., "Azure Service Bus stub vs. building it now").

### Find failure modes (Pre-mortem)

Invert the question: "It's six months from now and this failed — why?" Failure narratives must be
specific — a trigger, a chain of effects, a detection point, a root cause — not "it didn't scale."
Trace at least two orders of consequence:

```
Trigger: [event]
  -> 1st order: [immediate effect]
    -> 2nd order: [consequence of the 1st order effect]
```

Then invert again: "what would guarantee this fails?" and check whether any of those conditions
already exist. Close with early warning signs — observable signals that would show up before the
failure does, and how often to check for them.

### Attack this (Red team)

Adopt the adversary's mindset, not to cause harm but to find the vulnerability first. Build a
specific persona (role, motivation, capability, access, constraints) rather than a generic
"attacker" — generic personas produce generic findings. For this codebase the relevant personas
are less often external attackers and more often: a malformed LLM response the adapter didn't
validate, a segment whose audio measurement is wrong, a config that silently selects the wrong
adapter. Rank attack vectors by likelihood x impact; propose a specific countermeasure per vector,
not "add more validation."

Also surface perverse incentives: what does the current design reward that isn't actually wanted?
("Fastest render time" as the only tracked metric could reward skipping Tier 2 renders that would
have looked better.)

### Test the evidence (Falsification)

Extract the specific claims in a proposal — causal, predictive, comparative, quantitative — and for
each, state what would disprove it. A claim with no falsification criterion ("this will help in
some cases") is a red flag, not a fact. Grade evidence quality:

| Grade | Description |
|---|---|
| A | Controlled, reproducible, large sample |
| B | Observational, reasonable sample, consistent with other evidence |
| C | Case study, single source — needs corroboration |
| D | Anecdote, vendor marketing — do not decide on this alone |
| F | No evidence cited |

Then generate 2-3 competing explanations for the same evidence before accepting the proposed one.
Watch for confirmation bias, survivorship bias, and sunk-cost framing ("we've already built half of
it") creeping into the justification.

## Output shape

Every pass ends with:

1. **Steelmanned thesis** — the position restated at its strongest
2. **Challenges** — 3-5 points from the chosen mode, concrete and specific
3. **Space for the user's response** before moving to synthesis
4. **Synthesis** — a strengthened position, not a pile of unresolved objections
5. **Next steps** — a second mode worth running, if the domain warrants it

## Constraints

- Never strawman the position being challenged, and never manufacture disagreement for its own
  sake — every mode above is diagnostic, not adversarial theater.
- Concede points that hold up. Intellectual honesty is the point of running this at all.
- Never leave the user with a list of problems and no synthesis. The output is a stronger decision,
  not a teardown.
- This complements `project-reviewer` and `adapter-parity`, it doesn't replace them — those check
  code against rules that already exist; this checks a decision before it becomes one.
