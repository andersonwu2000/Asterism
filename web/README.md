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
  diffs, ingest sign-offs with every vouchable statement in full; a row
  a person has benched says so, and Groups is where it goes back.
  A task name opens that task's own page: Run, the parameters, then
  **the goal** and **your standing word** (the engine may propose a
  change to the first and can never touch the second), settings and
  paper bindings, and the delete confirm.
- **Sky** — the task's constellation: what grew from the root above the
  horizon, other forward work below, citation threads crossing. While
  anything is live the unproved stars carry the light and the proved
  mass recedes. `map` / `list` is the same data read two ways, not two
  pages; clicking a star opens its panel (routes, subgoals, dead
  attempts), and a route's file link lands in Documents. The panel is
  also where a person ACTS on a goal — park it, mark it delivered, hand
  it a proof, hand it to a new group — through the command queue: a
  preview, a live confirm window naming every node that closes, and a
  receipt polled until the engine's tick answers.
- **Groups** — the discussion tree: each group by code and charter, its
  Programme, the round it is arguing right now, and the bricks it handed
  back. One renderer, live or archived. A sub-group can be handed back
  to its parent from here, with a reason, through the same window. The
  task's OWN argument has no parent to hand back to, so what it offers
  instead is the bench — stop this task without stopping the run:
  dispatch skips it until it is put back, nothing in flight is killed,
  and everything it has is kept. Its own window, because a bench is not
  a queued command; the shelf marks a benched row, since the status chip
  reads "paused" either way.
- **Engine room** — observation: slots (one lane per agent, its unit,
  its statement, the tail it is writing, plus `cold-building sN` rows
  for promotion builds `in_flight` cannot see), each provider's quota
  bars, this Project's ledger, and the engine log. The one thing it can
  do rather than watch is stop ONE running Formalizer — the three
  signals of §3.7, through the same confirm window, aimed at the
  `pipelines.id` the lane now carries. A lane no running pipeline
  answers to says so instead of offering a button: a kill names one
  worker, never a kind or a name. When the daemon status reports its
  schema `behind`, nothing on this page was counted — the room and the
  per-task run control both collapse to one line naming the action,
  rather than drawing instruments over a dial nobody turned.
- **Timeline** — what happened, newest first; every row names an object,
  and the name opens it on the Sky. With no task in the address it is
  the whole shelf's history, each row stamped with its task and paged by
  `load earlier`; naming a task scopes it to that one.
- **Documents** — two roots in one file column: `proofs` (what the
  engine wrote for a task, read-only, opening on its REPORT.md when the
  Ingest terminal wrote one) and `documents`, the Project's own `_docs/`
  shelf. That one is writable: `user/` takes an editor for `.md` /
  `.tex` / `.txt`, plus new file, new folder and delete; `agent/` is
  what the Assistant wrote and is marked read-only. `.lean` opens in the
  Lean viewer, images render inline, and a refused path shows the
  engine's own sentence about it. Papers live here too (§3.9): each is
  a `papers/<id>/` folder holding the original pdf (shown in the
  reader), the extracted `text.md` and its `map.md`. Dropping files
  anywhere on this page — or "paper" in the column header — shelves
  them under `user/papers/`, extraction and all.

### Outside a Project

- **Settings** (`#/settings`) — the one gear page, shared by the picker
  and every Project: the accounts the engine spends and what is left of
  them, the machine's parameters, appearance, and quit. Run parameters
  are deliberately NOT here.
- **New task** (`#/new`, or `#/new/<project>` from a shelf, which files
  it there) — a name and a natural-language description, paper bindings,
  and two advanced folds (pinned Defs/Root; axiom whitelist, forbidden
  lemmas, lemma hints). The description IS the goal.
- **Assistant** — the docked right panel, opened by the corner glyph or
  `Ctrl+/`; the glyph blinks while it is thinking and holds a mark when
  an answer landed unseen. One conversation per Project, and every
  question carries the focus: the star that is open, the group being
  read, the document under the cursor. When an answer carries a prepared
  command it offers to review it — in the same window a command from a
  star opens. The panel prepares; the window submits.
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

The UI never touches the engine database; every mutation goes through
the same HTTP chokepoints as the CLI — and a command against the proof
state is QUEUED there, applied by the daemon's own tick through the
appliers the Strategist's decisions go through.
