# Asterism web UI

The browser face of the proving engine: a night-sky reading of the
workspace. Vite + React + TypeScript + Tailwind, self-hosted fonts
(Inter for UI, JetBrains Mono for identifiers, Fraunces for the
display voice). No router/state libraries — a hand-rolled hash router
and one polling hook.

## Screens

- **Board** (`#/`) — the survey sheet. Problems in attention order:
  needs you / in motion / recent (incl. just-created) / archive with
  namespace clusters. `/` focuses the filter; "New problem" lives here.
- **New problem** (`#/new`) — a name + a natural-language description
  (+ optional pinned Defs.lean/Root.lean behind an advanced fold). The
  server composes the Manifest; no yaml in the UI.
- **Problem** (`#/problems/<name>`) — the cockpit. Run/Stop for THIS
  problem in the header (single-problem runs are the only mode);
  health line (last progress / top blocker / paused-on-you);
  constellation (defs are diamonds, newborn stars get a welcome halo,
  struggle leaves grey residue); Manifest tab = NL instructions +
  control-style settings, hot-reloaded, locked while an amend is
  pending; Goals / Timeline (day rules, filters) / Files (Manifest
  typeset, Lean highlighted).
- **Library** (`#/library`) — the atlas. Each harvested problem is a
  constellation of its real declarations; search lights matching
  stars; click a star to copy its citation (shift: with import).
- **Inbox** (`#/inbox`) — decisions. Amend requests with word-level
  diffs + age escalation; ingest sign-offs resolve anchors/claims to
  their statements.
- **Engine** (`#/telemetry`) — status (what it's working on), settings
  (per-pipeline models + engine knobs, comment-preserving yaml edits),
  usage (this run), and a developer-log fold.

## Development

```
npm install
npm run dev        # http://localhost:5173, proxies /api to :8642
npm run build      # tsc + vite; production is served by FastAPI
npm run lint       # oxlint
npm run smoke      # Playwright suite against a live `asterism serve`
```

The UI is read-only against the engine database; every mutation goes
through the same HTTP chokepoints as the CLI.
