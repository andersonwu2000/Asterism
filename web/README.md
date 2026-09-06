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
  tasks and Run (an explicit list, never a pattern — every Run in the
  console, the shelf's and a task page's, reads the engine's preview
  and confirms in the one floating window); Stop, with its force step,
  the same control on both pages; and the run parameters folded beside
  them — models per
  seat, time budget, shelve threshold, quota behaviour. What waits on
  you rides at the top of the shelf: amend requests with word-level
  diffs, ingest sign-offs with every vouchable statement in full; a row
  a person has benched says so, and Groups is where it goes back.
  The shelf, the task column beside every other section and the task a
  section opens on all read one order (`shelfOrder`: what waits on you,
  then what is stalled, then what is in motion, then by recency).
  A task name opens that task's own page: Run, the parameters, then
  **the goal** and **your standing word** (the engine may propose a
  change to the first and can never touch the second), settings and
  paper bindings, and the delete confirm.
- **Sky** — the task's constellation: what grew from the root above the
  horizon, other forward work below, citation threads crossing. While
  anything is live the unproved stars carry the light and the proved
  mass recedes. `map` / `list` is the same data read two ways, not two
  pages; clicking a star opens its panel (routes, subgoals, dead
  attempts) and writes the star into the address (`…/g/<id>`, replaced
  rather than pushed, so a reload or a mailed link opens the same star
  and Back still leaves the section); a route's file link lands in
  Documents. The panel is
  also where a person ACTS on a goal — park it, mark it delivered, hand
  it a proof, hand it to a new group — through the command queue: a
  preview, a live confirm window naming every node that closes, and a
  receipt polled until the engine's tick answers.
- **Groups** — the discussion tree: each group by code and charter, its
  Programme, the round it is arguing right now, and the bricks it handed
  back. One renderer, live or archived. ONE reading, too: the claim it
  was handed, the Programme body expanded, and the decided chain folded
  into a `revision history` list under it. An address that names a
  revision (`…/groups/<task>/rev/<id>`, which is where a Timeline row
  sends you) reads THAT revision in the same place and the same shape —
  the judge's ruling above the body it ruled on, and a way back to the
  argument as it stands. A sub-group can be handed back
  to its parent from here, with a reason, through the same window. The
  task's OWN argument has no parent to hand back to, so what it offers
  instead is the bench — stop this task without stopping the run:
  dispatch skips it until it is put back, nothing in flight is killed,
  and everything it has is kept. Its own window, because a bench is not
  a queued command; the shelf marks a benched row, since the status chip
  reads "paused" either way.
- **Engine** — observation: slots (one lane per agent, its unit,
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
  and the name OPENS that object: a goal on the Sky, a Programme row on
  the revision it is about, and any theory row that landed a file on the
  file — the accepted document, the refused one, and the wake's own
  return alike. A row that landed nothing offers no link rather than one
  into a 404. With no task in the address it is the whole shelf's
  history, each row stamped with its task and paged by `load earlier`;
  naming a task scopes it to that one.
- **Documents** — one rail, one shell. The rail reads in five groups:
  `yours` (the Project's `_docs/user/`, primary, always open), then
  `papers`, `agent` (what the theory layer wrote, newest first — the
  Assistant writes into `yours` instead, where you can revise it),
  `engine` (one task's REPORT / PROGRAMME / BRIEF / TREE /
  Root / Defs, task chosen on the header) and `proofs` — the last four
  folded by default, with a name filter over all of them. Every file
  opens in the same shell: source on the left, a panel on the right —
  `.md` renders, `.tex` compiles to a pdf preview (or says there is no
  engine), `.lean` gets the Info panel on the reserved slot, pdf and
  images view — behind a `source | split | render` control. Editing is
  exactly on `yours`: Save (Ctrl+S) with dirty marks, drafts that survive
  walking the rail, a conflict line when the disk moved on, and the
  selected row's own strip for `rename · move · delete` (keys: F2, m,
  Delete; `+ file` / `+ folder` inline, n / N). Rows outside `yours` say
  read-only in that same strip. "ask the Assistant" hands the open file
  to the panel. Dropping files anywhere — or `+ paper` — shelves papers
  under `user/papers/`, extraction and all.

  **The two writing formats operate alike.** `.md` and `.tex` are two
  rows of ONE mode table (`lib/docShell::modeFor`), not two branches of
  the shell — the only differences left are differences in the medium,
  and this is the whole list:

  | | `.md` | `.tex` | `.lean` | `.txt` |
  |---|---|---|---|---|
  | tabs | `source · split · render` | `source · split · render` | `source · split · info` | source only |
  | opens on | split (yours) / render | split (yours) / render | split | source |
  | source painter | the markdown painter | plain (a `#` opens no heading in TeX) | the Lean tokenizer | plain |
  | right pane | the console's render | the server's compiled pdf | goal at the caret + diagnostics | — |
  | check | `Check` — what the painter could not read (an unclosed fence, math the typesetter refuses) | `Render` — the engine's compile, or its log tail | live, on the reserved slot | — |
  | render follows the source's scroll | yes, proportional | no — the pane is the browser's own pdf viewer, which takes no instruction from the page | no — the Info panel follows the CARET instead | — |
  | save | Ctrl+S, dirty mark, `base_etag` conflict line | same | same | same |
  | undo | the textarea's own | same | same | same |

### Outside a Project

- **Settings** — the gear, shared by the picker and every Project. It is
  a window, not a page: it opens over whatever you are reading and hands
  the page back when you close it, because reaching the accounts should
  not cost you your place. Inside: the accounts the engine spends and
  what is left of them, the machine's parameters, appearance, and quit.
  Run parameters are deliberately NOT here. `#/settings` still opens it,
  for links minted while it was an address, and then steps out of the
  address.
- **New task** (`#/new`, or `#/new/<project>` from a shelf, which files
  it there) — a name and a natural-language description, paper bindings,
  and two advanced folds (pinned Defs/Root; axiom whitelist, forbidden
  lemmas, lemma hints). The description IS the goal.
- **Assistant** — the docked right panel, opened by the corner glyph or
  `Ctrl+/`; the glyph blinks while it is thinking and holds a mark when
  an answer landed unseen. A Project keeps MANY conversations, on disk
  beside the workspace, and one of them is current: the header names it,
  and the fold under the header lists the rest newest-first, with
  `rename · delete` under the selected row and `+ new conversation` at
  the top (keys: ↑↓, Enter, F2, Delete). A question you asked can be
  edited in place and re-asked, which drops everything after it on both
  ends. Every question carries the focus: the star that is open, the
  group being read, the document under the cursor. While the answer is
  being written the panel shows what it is DOING — a row per tool call
  with its argument and its clock — and folds them into one line when
  the answer lands. The model picker offers every backend this machine
  has; a conversation that already has turns keeps the one it started
  on. When an answer carries a prepared command it offers to review it —
  in the same window a command from a star opens. The panel prepares;
  the window submits.
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
