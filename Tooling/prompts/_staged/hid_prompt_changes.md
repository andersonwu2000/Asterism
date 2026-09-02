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
