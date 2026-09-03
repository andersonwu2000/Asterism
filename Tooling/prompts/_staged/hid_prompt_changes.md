# Staged prompt changes — human_interface_design.md §3

Wording changes the HID work wants in the live prompts, collected here
for one review rather than applied one at a time (§3 preamble).

A change lands in the LIVE prompt before review only when the existing
text became FALSE — a prompt that names a path which no longer exists
teaches the agent a probe that fails. Those are listed too, marked
`applied`, so the review sees the whole set either way.

---

## §3.9 — Papers retire into the Project document roots (2026-09-03)

### applied — `adversary/adversary.md`, the `{papers_dir}` line

The placeholder is substituted with the problem's Project document root
now (`Problems/<project>/_docs`), so `each \`Papers/<id>/\` holds …`
named a directory the judge cannot open.

    -  the fetched papers (each `Papers/<id>/` holds `text.md` + `map.md` + `meta.json`)
    +  this Project's documents; its papers are under `<area>/papers/<id>/`
    +  (each holds `text.md` + `map.md` + `meta.json`)

### not applied — the three `paper_search` / `paper_fetch` lines

`adversary/_contract.md`, `strategist/inject_batch_done.md` and
`strategist/pending_review.md` each carry:

> Papers are fetched with your tools, not with a decision: `paper_search`
> resolves a citation to open copies, `paper_fetch` downloads, shelves
> and binds one to this problem …

That sentence names no path and stays true under §3.9 — "shelves" is now
"onto this problem's Project shelf", which is what `paper_fetch` does.
§3.9 lists these three as sites to check; the check found nothing to
change. If the review wants the shelf named explicitly, the smallest
edit is `shelves (on this problem's Project) and binds one`.
