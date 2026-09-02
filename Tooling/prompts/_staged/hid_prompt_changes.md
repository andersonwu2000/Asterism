# Staged prompt changes — human interface (HID)

Not loaded by anything. Each section names one live prompt file, the exact
line to replace, and the replacement. Same line in the three mirrors
(`strategist/inject_batch_done.md`, `strategist/pending_review.md`,
`adversary/_contract.md`) must stay verbatim-identical.

---

## `RequestUserAmend` gains `title`
Files: `strategist/inject_batch_done.md:74`, `strategist/pending_review.md:75`, `adversary/_contract.md:18`

Replace `… proposed_body`, `question`, `reason`.` with:

```
`proposed_body`, `question`, `title`, `reason`. `title`: one line naming the ask.
```

(rest of the line unchanged)

## `## Summary` on the proposal
Files: `strategist/inject_batch_done.md` layout block (42-56), `strategist/pending_review.md` layout block (43-57)

Add after the `## Conventions` line:

```
    ## Summary      Optional. One short paragraph for a mathematician who has not
                    read this Programme: what this revision changes and why.
                    English, LaTeX for math. Not judged.
```

File: `adversary/adversary.md:15` — append to the end of the line:

```
An optional `## Summary` may appear anywhere; it is not under judgment.
```

## `Ingest` gains `report`
Files: `strategist/inject_batch_done.md:76`, `strategist/pending_review.md:77`, `adversary/_contract.md:17`

Replace `- `Ingest` — optional `reason`.` with:

```
- `Ingest` — `report`, optional `reason`.
```

and append to the end of that line:

```
`report`: English markdown, LaTeX for math — the statement settled, the route in prose, the bricks that carry it, what was refuted, what is left open. It becomes `REPORT.md`.
```

Flip `verify.INGEST_REPORT_REQUIRED` to `True` in the same commit.

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
