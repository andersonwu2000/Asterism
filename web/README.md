# Asterism web UI

The browser face of the proving engine: a night-sky reading of the
workspace. Vite + React + TypeScript + Tailwind, self-hosted fonts
(Inter for UI, JetBrains Mono for identifiers, Fraunces for the
display voice). No router/state libraries — a hand-rolled hash router
and one polling hook.

## Shape

A **Project** is a shelf of tasks (`human_interface_design.md` §1.4). It
is the first screen, and every other screen lives inside one, so there
are exactly two frames and no sidebar.

- **Projects** (`#/`) — the picker. One large tile per shelf: its name,
  its description, a quiet count of tasks and of anything running, and a
  warn dot when something on it waits on you. No menu — a gear, a help
  glyph, and a tile that mints a new shelf.
- **Inside a Project** (`#/p/<project>/<section>[/<task>]`) — one header
  row: the wordmark (back to the picker), the six sections, and exactly
  two corner glyphs (gear, Assistant). Beside the content, a collapsible
  task column; it is hidden when the shelf holds one task, and on the
  Tasks shelf itself, which IS the list. No section carries a title of
  its own: the menu has said which one you are reading.

### The six sections

- **Tasks** — the shelf, and the engine control that acts on it. Tick
  tasks and Run (an explicit list, never a pattern); Stop, with its
  force step; and the run parameters folded beside them — models per
  seat, time budget, shelve threshold, quota behaviour. What waits on
  you rides at the top of the shelf: amend requests with word-level
  diffs, ingest sign-offs with every vouchable statement in full.
  A task name opens that task's own page: Run, the parameters, then
  **the goal** and **your standing word** (the engine may propose a
  change to the first and can never touch the second), settings and
  paper bindings, and the delete confirm.
- **Sky** — the task's constellation: what grew from the root above the
  horizon, other forward work below, citation threads crossing. While
  anything is live the unproved stars carry the light and the proved
  mass recedes. `map` / `list` is the same data read two ways, not two
  pages; clicking a star opens its panel (routes, subgoals, dead
  attempts), and a route's file link lands in Documents.
- **Groups** — the discussion tree: each group by code and charter, its
  Programme, the round it is arguing right now, and the bricks it handed
  back. One renderer, live or archived.
- **Engine room** — read-only observation: slots (one lane per agent,
  its unit, its statement, the tail it is writing, plus `cold-building
  sN` rows for promotion builds `in_flight` cannot see), each provider's
  quota bars, the all-time ledger, and the engine log.
- **Timeline** — what happened to this task, newest first; every row
  names an object, and the name opens it on the Sky.
- **Documents** — two roots in one file column: `proofs` (what the
  engine wrote for a task) and `documents` (the Project's own `_docs/`
  shelf). Read-only until the documents package.

### Outside a Project

- **Settings** (`#/settings`) — the one gear page, shared by the picker
  and every Project: the accounts the engine spends and what is left of
  them, the machine's parameters, appearance, and quit. Run parameters
  are deliberately NOT here.
- **New task** (`#/new`) — a name and a natural-language description,
  paper bindings, and two advanced folds (pinned Defs/Root; axiom
  whitelist, forbidden lemmas, lemma hints). The description IS the
  goal.
- **Papers** (`#/papers`) — the shelf a task binds its sources from.
- **Assistant** — the right-hand drawer, opened by the corner glyph or
  `Ctrl+/`. It is handed the Project and the task on screen.
- `#/problems/<name>` still opens: it asks the DB which shelf the task
  is on and redirects. The name's first segment is only a default at
  registration (§3.1), so it is never split to guess.

## Development

```
npm install
npm run dev        # http://localhost:5173, proxies /api to :8642
                   # ASTERISM_API=http://127.0.0.1:8643 npm run dev
                   #   points it at a second serve instead
npm run build      # tsc + vite; production is served by FastAPI
npm run lint       # oxlint
npm run test       # vitest — the pure route/IA/data laws
npm run smoke      # Playwright against a live `asterism serve`
                   # SMOKE_URL=http://localhost:5173 to hit the dev server
```

The UI is read-only against the engine database; every mutation goes
through the same HTTP chokepoints as the CLI.
