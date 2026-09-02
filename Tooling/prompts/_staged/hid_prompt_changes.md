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

## Tooling/prompts/strategist/inject_batch_done.md (the `## Programme proposal` layout block, lines 42-54)

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

## Tooling/prompts/strategist/pending_review.md (the `## Programme proposal` layout block, lines 43-55)

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
