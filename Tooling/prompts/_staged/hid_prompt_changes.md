# Staged prompt changes — human-interface design (HID)

Proposed wording for the owner's review. **Nothing here is loaded by
anything**: no spawn reads this directory, and the live prompt files are
untouched until the owner approves a line and it is moved by hand.

Each section names one live prompt file and quotes the exact line to
replace, then the replacement. One `##` section per file.

---

## Tooling/prompts/strategist/inject_batch_done.md (line 74)

Package A2 — `RequestUserAmend` now carries an optional `title` that the
human's inbox shows as the row's one line. Absent, the inbox derives one
from the question's first 80 characters, which is a paragraph's opening,
not a name.

Replace:

```
- `RequestUserAmend` — `problem`, `file ∈ {"Defs.lean", "Root.lean", "charter"}`, `proposed_body`, `question`, `reason`. Only when a user file — or the problem's charter (the top group's goal) — is wrong. The user's word is never amendable.
```

With:

```
- `RequestUserAmend` — `problem`, `file ∈ {"Defs.lean", "Root.lean", "charter"}`, `proposed_body`, `question`, `title`, `reason`. Only when a user file — or the problem's charter (the top group's goal) — is wrong. The user's word is never amendable. `title` — one line naming the ask, for the human's inbox.
```

## Tooling/prompts/strategist/pending_review.md (line 75)

Same line, same replacement as above — the two Strategist wakes carry the
decision vocabulary verbatim, and they must not drift apart.

## Tooling/prompts/adversary/_contract.md (line 18)

Same line, same replacement as above. The Adversary judges a batch against
the same contract the Strategist wrote to; a field the judge's copy does
not list reads as a schema violation.

---

## Tooling/prompts/strategist/inject_batch_done.md (the `## Programme proposal` layout block, lines 42-56)

Package D1 — every passed revision gains an optional human-readable
`## Summary` (`programme_revisions.summary`, HID §1.2 / §3.4): one
paragraph for a mathematician who has not read the Programme. It is not
judged material; the Adversary rules on Argument / Proof / Roadmap, and
the summary says what came of them. Position is deliberately free — the
render puts it under the title — so no batch can lose a round to where
the paragraph goes.

Add after the `## Conventions` line of the layout block:

```
    ## Summary      OPTIONAL, and written last: one short paragraph for a
                    mathematician who has not read this Programme — what this
                    revision changes and why. English; LaTeX for the mathematics.
                    Not judged: it says what the sections above came to. The
                    reader sees it first (the render moves it under the title),
                    so write it wherever you like.
```

## Tooling/prompts/strategist/pending_review.md (the `## Programme proposal` layout block, lines 43-57)

Same addition as above — the two Strategist wakes carry the proposal
layout verbatim, and they must not drift apart.

## Tooling/prompts/adversary/adversary.md (line 15)

The judge's copy of the proposal layout must list the section, or an
optional `## Summary` reads as a schema violation — and the line must
say that it is NOT judged, so a rebuttal is never spent on it.

Replace (tail of line 15, after the `## Roadmap` clause):

```
closures name the exact dead instantiation and a self-producible restart condition).
```

With:

```
closures name the exact dead instantiation and a self-producible restart condition). An optional `## Summary` may appear anywhere: one paragraph of human-readable prose for a reader who has not read the Programme. It is NOT under judgment — rule on the Argument, the Proof and the Roadmap, never on the summary.
```

## Tooling/prompts/strategist/inject_batch_done.md (line 76 — the `- `Ingest`` line)

Package D2 — `Ingest` gains a `report`: the terminal's human-readable
summary (`problems.ingest_report`, rendered as `REPORT.md`; HID §1.2 /
§3.4). The verifier's structural check exists already, behind
`verify.INGEST_REPORT_REQUIRED = False`; **flip that constant to True in
the same commit that lands this wording**, or the gate and the prompt
drift apart in the direction that refuses a field nobody asked for.

Replace:

```
- `Ingest` — optional `reason`. The problem's only exit: emit once the marked set fully satisfies the charter. With a root: the proved root — or the `disproved` root, which closes the problem as `refuted`. `RequestUserAmend` only for a claim the user wrote wrong.
```

With:

```
- `Ingest` — `report`, optional `reason`. The problem's only exit: emit once the marked set fully satisfies the charter. With a root: the proved root — or the `disproved` root, which closes the problem as `refuted`. `RequestUserAmend` only for a claim the user wrote wrong. `report` — the complete summary of this result in English markdown, LaTeX for the mathematics: the statement settled, the route in prose, which bricks carry it, what was refuted, what is left open. It is the only part of this result a mathematician who has not read the Programme reads; it becomes `REPORT.md`.
```

## Tooling/prompts/strategist/pending_review.md (line 77 — the `- `Ingest`` line)

Same line, same replacement as above — the two Strategist wakes carry the
decision vocabulary verbatim, and they must not drift apart.

## Tooling/prompts/adversary/_contract.md (line 17 — the `- `Ingest`` line)

Same line, same replacement as above. The Adversary judges a batch against
the same contract the Strategist wrote to; a field the judge's copy does
not list reads as a schema violation.

## Tooling/serve/chat.py — `_SYSTEM_PROMPT` (the Assistant's rule 1, and one new rule)

Package E3 gave the console Assistant a tool surface (HID §1.1's capability
matrix, §3.5, §3.8): it may write documents into the Project's `agent/`
shelf, list and read that Project's documents, prepare a framework command
for the person to confirm, and read the engine's status. The tools are
wired and seat-scoped (`envelope.SEAT_ASTERISM_TOOLS["explainer"]`), but
rule 1 of the live prompt still says the opposite — **it will decline to
use them**, which is the correct behaviour for a prompt that has not been
told. Nothing here is loaded; the tools stay inert until this is approved
and moved by hand.

The prompt is not a file under `Tooling/prompts/` — it is the
`_SYSTEM_PROMPT` string literal at the top of `Tooling/serve/chat.py`.

Replace:

```
1. READ-ONLY, always. You explain; you never act. If asked to change, approve, reject, run, or delete anything, decline in one sentence and point at the UI control that does it. No exceptions — acting would break the system's soundness boundary.
```

With:

```
1. YOU DO NOT ACT ON THE RUN. You never change a proof, a goal, the database or a running engine, and you never approve or sign anything — that boundary is what makes the results trustworthy, and there is no exception to it. Two things you MAY do, both through your tools: write documents into the Project's own `agent/` shelf (`write_project_doc`; `user/` is the person's and is not yours to write), and PREPARE a framework command (`prepare_command`) — which checks the command and shows what it would affect, and then stops. You never run it; the person presses the button in the console. If asked to shelve, delegate, mark or inject, prepare the command, say plainly what it would close, and hand it over.
```

And add, after rule 4:

```
5. Tools. `inspect` reads files and the framework's own record; `loogle` searches Mathlib; `paper_search` finds papers; `daemon_status` says what the engine is doing; `list_project_docs` / `read_project_doc` / `write_project_doc` are the Project's documents. Read the person's `user/` notes before writing beside them. Documents are for a mathematician: English prose, LaTeX for the mathematics.
```

Note for the reviewer: rule 1's replacement is deliberately longer than
the line it replaces. The rule now has to draw a boundary in a place the
model can find — "never act" was one word to obey, "never act on the run,
but here are two things that are yours" needs the two named, or the model
resolves the tension by refusing the tools it was given.
