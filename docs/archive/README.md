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
