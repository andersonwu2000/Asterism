# Staged prompt changes — human interface (HID)

Not loaded by anything. Each section names one live prompt file, the exact
line to replace, and the replacement. Same line in the three mirrors
(`strategist/inject_batch_done.md`, `strategist/pending_review.md`,
`adversary/_contract.md`) must stay verbatim-identical.

(`## Summary` on the proposal: dropped — owner 09-02, the Programme is
already prose a mathematician reads.)

---

## `RequestUserAmend` gains `title`
Files: `strategist/inject_batch_done.md:74`, `strategist/pending_review.md:75`, `adversary/_contract.md:18`

Replace `… proposed_body`, `question`, `reason`.` with:

```
`proposed_body`, `question`, `title`, `reason`. `title`: one line naming the ask.
```

(rest of the line unchanged)

## `Ingest` gains `report`
Files: `strategist/inject_batch_done.md:76`, `strategist/pending_review.md:77`, `adversary/_contract.md:17`

Replace `- `Ingest` — optional `reason`.` with:

```
- `Ingest` — `report`, optional `reason`.
```

and append to the end of that line:

```
`report`: a short paper in English markdown, LaTeX for math, written for a mathematician who has never seen this system — no framework words (goal, brick, batch, Programme). Sections, in this order: `## Introduction` (the question and why it matters), `## Main Result` (the statement as proved, or the counterexample), `## Proof Sketch` (the route in prose, citing the formal lemma names in backticks where a reader would look them up), `## What Remains` (what was refuted or left open). It becomes `REPORT.md`.
```

Flip `verify.INGEST_REPORT_REQUIRED` to `True` in the same commit; the gate
checks the four headings exist, nothing else.

## Assistant system prompt
File: `Tooling/serve/chat.py`, `_SYSTEM_PROMPT` (a string literal, not a prompt file)

Replace rule 1 with:

```
1. You never change proofs, goals, the database or the running engine, and you never approve or sign anything. You may write documents under the Project's `agent/` shelf (`write_project_doc`; `user/` is the person's). You may prepare a framework command (`prepare_command`): it checks the command and shows what it would affect, then stops — the person confirms it in the console. Asked to shelve, delegate, mark or inject: prepare it, say what it would close, hand it over.
```

Add after rule 4:

```
5. Tools: `inspect` reads files and the record; `loogle` searches Mathlib; `paper_search` / `paper_fetch` find and shelve papers; `compute` runs a sandboxed calculation; `daemon_status` says what the engine is doing; `list_project_docs` / `read_project_doc` / `write_project_doc` are the Project's documents. Read `user/` before writing beside it. Documents are for a mathematician: English, LaTeX for math.
```
