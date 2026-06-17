# archive/

Two lifecycles, two subdirs:

| Subdir | Lifecycle | Tracked? |
|---|---|---|
| `design/` | Framework design history — shipped-design docs (code shipped, doc kept as forensic reference) and stalled design exploration (decision rounds that never resolved). | Yes |
| `delivered/` | Frozen external deliverables (proposal package, slide deck). Working tree keeps the files so the operator can re-open them locally, but git doesn't track new changes. | No (gitignored — see root `.gitignore`) |

If you add a new archived doc, decide which lifecycle it belongs to.
When in doubt: anything *internal* to the framework's design history
goes in `design/`; anything *delivered to a third party* at a fixed
date goes in `delivered/<date>_<label>/`.

**Some `design/` docs are still code-referenced** (the shipped code points
at them by section anchor, e.g. `phase2/pipelines.md §2.4`,
`librarian_plan.md §4`). They live here because the *design* is frozen, not
because nobody reads them. Do **not** move or rename them without updating
every `git grep`-able reference in `Tooling/` and `tests/` in the same
commit — a stale anchor is a dangling reference.
