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
- **New problem** (`#/new`) — a name + a natural-language description,
  paper checkboxes to ground the run, and two advanced folds (pinned
  Defs.lean/Root.lean; engine constraints: axiom whitelist / forbidden
  lemmas / lemma hints). Settings land in the DB via the chokepoint;
  Manifest.md is the human prose.
- **Problem** (`#/problems/<name>`) — the cockpit. Run/Stop for THIS
  problem in the header (single-problem runs are the only mode); a
  run strip while the engine works it (phase in plain words, wall
  clock, per-agent roster, weighted burn); health line whose named
  blocker opens its star. The constellation is a two-region sky:
  what grew from the root above the horizon, other forward work
  below, citation threads crossing where it is used; while anything
  is live the unproved stars carry the light and the proved mass
  recedes (a finished sky flips back to trophy). Manifest tab = NL
  instructions + settings controls (DB-backed, hot-reloaded) + paper
  bindings; Goals / Timeline / Files.
- **Papers** (`#/papers`) — the shelf. Add a PDF (or .md/.tex) by
  path; each paper lists its size, citing problems, and index state;
  opening one renders the original document beside a rail for
  switching papers. Delete is refused while cited.
- **Library** (`#/library`) — the atlas. Each harvested problem is a
  constellation of its real declarations; search lights matching
  stars; click a star to copy its citation (shift: with import).
  Opening a constellation reads its **chapter**
  (`#/library/<problem>`), three views: Highlights (the short list
  worth reading — vouched claims or, where ingest wore the flags off,
  the keystones other modules demonstrably reach for, plus the
  vocabulary), Map (modules and their imports), and Modules (the full
  curated text, one file at a time — docstrings as prose, kernel-true
  signatures). The engine record (goals, attempts) stays on the
  problem page, one link away.
- **Inbox** (`#/inbox`) — decisions. Amend requests with word-level
  diffs + age escalation; ingest sign-offs show every vouchable
  statement in full (defs with their bodies — the construction is
  what you vouch for) and carry the Library decision: approve as
  "harvest to Library" or "archive only" — a human signs, nothing is
  harvested automatically.
- **Run** (`#/run`) — mission control. Status light + phase in plain
  words (warming / planning / proving / harvesting / stopping), the
  scoped problem's progress bar, one lane per live agent (its unit,
  its statement, the tail of the file it is writing — spawn writes go
  through to the real path), burn against the trailing-5h
  subscription window, recent decisions, and Stop. Idle, it keeps
  telling the last run's story (clean / force-stopped / crashed).
- **Settings** (`#/settings`) — the machine room: per-pipeline model
  selects + engine knobs (comment-preserving yaml edits), the
  all-time usage ledger (weighted burn, cache hit share), and a
  developer-log fold.

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
