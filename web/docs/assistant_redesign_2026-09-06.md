# Assistant redesign — 2026-09-06

Owner's five complaints, in order: the drawer is cramped; HID §1.1's
session system was never built; the model picker is a hand-typed list;
a turn shows nothing while tools run and then times out; Settings
navigates away. What follows is the contract an implementer needs —
layout, session model, streaming events, backend changes. Visual law is
`web/DESIGN.md` and nothing here overrides it.

## 1. Layout — a conversation surface, still docked

HID §1.4 stands: the Assistant is the docked right panel ("左讀右問"),
never a floating window. What changes is that it is now sized and
furnished for reading a conversation, not for a one-line question.

```
┌──────────────────────────────────────────────────────────────┐
│ ▾ why is p1 stalled?            about Erdos.p1   [model ▾] ⤢ × │  header
├──────────────────────────────────────────────────────────────┤
│ (sessions fold — only while open)                             │
│   + new conversation                                          │
│   ● why is p1 stalled?              3 turns · 2 min ago       │
│     rename · delete                                           │  ← act strip under the SELECTED row
│     what does sign-off endorse?     1 turn · yesterday        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌ user turn (quiet card) ─────────────────────────────────┐  │
│  │ why is p1 stalled?                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│    edit & re-ask                       ← act strip, selected turn only
│                                                               │
│  ● inspect   Problems/Erdos/p1/TREE.md              1.2s      │  activity rows
│  ● loogle    "Nat.Prime ?p → …"                     3.4s      │  (live: pulsing dot)
│  ◌ compute   "sum of first 40 primes"               running   │
│  thinking…                                                    │  stage line
│                                                               │
│  The task is waiting on the strategist because …             │  prose, streams in
│                                                               │
│  ─ read 3 files · searched Mathlib once · 12.4s ▸ ─           │  collapsed timeline
│                                                               │  after `done`
├──────────────────────────────────────────────────────────────┤
│ ( ask anything…                                          ↑ )  │  composer pill
└──────────────────────────────────────────────────────────────┘
```

- **Width**: default 460px; drag 360…min(70vw, 960). `⤢` toggles between
  the remembered narrow width and a reading width (min(55vw, 800)).
  Width is now persisted (`asterism.chat.width`) — the July ruling
  "clamp, don't persist" predates the complaint that the panel is
  cramped; a reading posture is remembered like `railOpen` is.
- **Header**: session title (first user turn, clipped; `▾` opens the
  fold) · `about <page>` (existing) · model picker · `⤢` · `×`. Nothing
  else. `clear` is gone — deleting the session is the act on its row.
- **Sessions fold**: opens IN PLACE under the header (DESIGN: do not
  float what the page can say). Rows newest-first; the current one
  carries the dot; the act strip `rename · delete` sits under the
  selected row only (DESIGN 2026-09-04, the Documents rail's grammar).
  Keys: ↑↓ walk, Enter opens, F2 rename, Delete deletes (two-step in
  place: `confirm — forget this conversation`). `+ new conversation` is
  the first row.
- **Transcript**: a user turn is the quiet card it was; clicking it
  selects it and the strip `edit & re-ask` appears under it. Edit turns
  the card into a textarea in place (`re-ask` / `cancel`, Esc cancels).
  Re-ask truncates the transcript at that turn — later turns are gone
  on both ends — and sends. Not offered while streaming.
- **Assistant turn** = activity rows + stage line + prose. One row per
  tool call: state dot (`◌` pulsing while running, `●` done, `!` on
  error — brightness/shape, never colour), tool name in mono, a one-line
  argument summary in faint ink, duration tnum right-aligned. Rows are
  live while the turn streams. On `done` they collapse to one summary
  line (`read 3 files · searched Mathlib once · 12.4s ▸`) that expands
  back. A turn with zero tool calls draws no timeline at all (the
  settled norm earns no ink).
- **Composer**: unchanged pill; send morphs to stop; failed sends roll
  the text back (the QPaper shapes stay).
- **Empty state**: the three suggestions, plus — when there are older
  sessions — `or continue: <title>` links for the two most recent.

## 2. Sessions — per Project, on disk, many

HID §1.1: sessions are bound to the Project; every Project gets its own
transcripts. "One transcript per Project" becomes "one CURRENT session
per Project among many".

**Store**: `<workspace>/.asterism/chat/<project_key>/<session_id>.json`
(`_global` for the picker page, as today). Runtime state, gitignored
with the rest of `.asterism/`, never the DB (the daemon's DB is live;
this is not proof state). One module owns reads and writes:
`Tooling/serve/chat_sessions.py`.

```jsonc
{
  "id": "c1f0…",            // uuid4 hex
  "project": "Erdos",        // or "_global"
  "title": "why is p1 stalled?",
  "title_custom": false,     // true once renamed; else re-derived from turn 0
  "created_at": "…Z", "updated_at": "…Z",
  "model": "claude-sonnet-5",
  "provider": "claude",
  "handle": "uuid…" | null,  // the provider's resume handle (was _ChatState.sessions)
  "page_key": "problem:Erdos.p1|project=Erdos" | null,   // was _ChatState.page_keys
  "turns": [
    {"role": "user", "text": "…", "at": "…Z"},
    {"role": "assistant", "text": "…", "at": "…Z", "ok": true,
     "note": null,
     "tools": [{"id": "toolu_…", "name": "inspect",
                "input": {"path": "…"}, "ok": true, "ms": 1210,
                "result": "first 200 chars…"}]}
  ]
}
```

Rules:
- `title` = first line of turn 0, whitespace-collapsed, ≤ 60 chars, until
  renamed. Renaming to empty restores derivation.
- Listing sorts by `updated_at` desc. A session with zero turns is
  legal (just created) and is reused by the next `POST /api/chat/sessions`
  for the same Project instead of minting a second empty one.
- The assistant turn is written when the stream ends (done / error /
  client abort) with whatever text streamed — partial answers are
  first-class. A user turn whose answer never started (spawn failure)
  is not persisted.
- The browser no longer persists transcripts (`sessionStorage` copy
  goes); it holds only `asterism.chat.session:<project>` = current id,
  `asterism.chat.model`, `asterism.chat.width`.

**Endpoints** (all under the single chat lock for writes):

| method | path | body / query | returns |
|---|---|---|---|
| GET | `/api/chat/sessions?project=` | | `{sessions:[{id,title,updated_at,created_at,turns:int,model}]}` |
| POST | `/api/chat/sessions` | `{project}` | the new (or reused empty) session summary |
| GET | `/api/chat/sessions/{id}` | | the full record above |
| PATCH | `/api/chat/sessions/{id}` | `{title}` | summary |
| DELETE | `/api/chat/sessions/{id}` | | `{deleted:true}` (409 while busy) |
| POST | `/api/chat` | `{message, session_id, page, project, focus, model, truncate_to?}` | SSE |

- `session_id` is required; an unknown id is 404. `project` must match
  the session's Project (422 otherwise — a question cannot be filed on
  another shelf's transcript).
- `truncate_to: n` (edit & re-ask) drops `turns[n:]` before appending
  the new user turn. Turn `n` must be a user turn (422 otherwise).
- `/api/chat/clear` is retired; DELETE is the act.
- `/api/chat/state` keeps its seat facts (`provider`, `available`,
  `conversation_memory`, `read_scope`, `read_note`, `busy`) and gains
  `groups` (§4) and `model_default`; it loses `has_session`,
  `session_key` and `models`.

**Continuity after truncation or a dead handle.** Neither claude nor agy
can rewind a session, so after `truncate_to` the record's `handle` is
cleared and the turn is planned cold. A cold turn on a session that has
prior turns prepends a bounded replay block to the prompt:

```
[Earlier in this conversation — replayed because the engine's session
was reset; answer as a continuation.]
user: …
assistant: …
```

Most recent turns first to fit `_MAX_REPLAY = 12_000` chars, each turn
clipped to 2 000; tool rows are not replayed. The same block serves the
serve-restart case (the handle survives on disk now, but a swept
provider session still hits the existing cold retry) — so the panel's
"the engine reads your next question fresh" caveat is retired: the
engine does read the transcript.

## 3. Streaming — the event contract

SSE frames, `data: <json>`. The browser reduces them into the turn
(`lib/chatStream.ts`, pure, tested). The stream is also the liveness
signal: the backend sends an SSE comment `: keepalive` every 15 s while
it is waiting on the CLI, so a proxy or the browser never sees a silent
socket.

| type | fields | meaning |
|---|---|---|
| `session` | `id` | first frame; the session this turn was filed on |
| `status` | `stage: context\|thinking\|reading\|retry` | stage line (existing) |
| `tool_start` | `id, name, input` (strings clipped to 200 chars) | a tool call began |
| `tool_end` | `id, ok, ms, result` (≤ 200 chars) | it returned |
| `delta` | `text` | prose fragment |
| `done` | `ok, subtype, turns, output_tokens` | the answer ended |
| `error` | `detail` | the turn failed; whatever streamed stays |

Frontend reduction: `tool_start` appends a running row; `tool_end`
settles it (an end without a start still appends a settled row — never
drop what the engine said); `delta` clears the stage line and appends
text; `done`/`error` collapse the rows. Duration on a running row is the
browser's clock since `tool_start`; on a settled row it is `ms`.

**Tool names** arrive with the MCP server prefix
(`mcp__asterism_tools__inspect`, measured 2026-09-06). The record keeps
the raw name; every rendered name and every family match goes through
`bareToolName`, which strips a leading `mcp__<server>__`.

**Argument summary** (`lib/chatStream.ts` `toolLine(name, input)`, pure):
inputs nest (`inspect` sends `{"queries": [{"read": "…"}, …]}`), so the
walk is depth-first over dicts and arrays (depth ≤ 3) collecting string
leaves — priority keys anywhere first (`path`, `file`, `read`, `query`,
`pattern`, `expr`, `command`, `code`, `name`, `problem`, `goal`, `text`),
else in order — joined up to three with ` · `, whitespace trimmed before
newlines become `⏎`, clipped to 80 chars, quotes stripped.

**Collapsed line** (`summarizeTools(rows)`): counts by verb family
(`inspect`/`read_project_doc`/`Read` → "read N files", `loogle` →
"searched Mathlib N×", `paper_search`/`paper_fetch` → "papers", `compute`
→ "computed N×", `daemon_status` → "asked the engine", `Grep`/`Glob` →
"searched the workspace", other → the tool name) plus the total wall
time from the first start to the last end.

### Backend: where the events come from

`ClaudeExplainer.reader` already walks `stream-json`. It gains:

- `content_block_start` with `tool_use` → remember `{index → id, name,
  json: ''}`; still emit `status reading`.
- `content_block_delta` with `input_json_delta` → append `partial_json`.
- `content_block_stop` on a remembered index → parse the JSON (`{}` on
  failure), clip strings, emit `tool_start {id, name, input}`, stamp
  the start time.
- top-level `{"type": "user", "message": {"content": [{"type":
  "tool_result", "tool_use_id", "content", "is_error"}]}}` → emit
  `tool_end {id, ok: !is_error, ms, result}`; `content` may be a string
  or a list of `{type:text,text}` blocks — flatten, clip to 200.

The implementer must capture a REAL stream first (`claude -p … --output-
format stream-json --verbose --include-partial-messages` with one tool
allowed) and build the reader fixture from it — a hand-written fixture
freezes a guessed contract (`frontend_state.md`, 2026-07-29).

`AntigravityExplainer.reader` emits no tool events (it has no stream);
nothing is invented.

### Backend: the idle deadline

`chat.py`'s wall clock (`_TIMEOUT_SEC` over the whole answer) becomes an
idle deadline on the event stream: every item from the reader queue
resets `last_event`; on `queue.Empty` the generator checks `now -
last_event > idle_sec` and only then emits `error: "no word from the
explainer for N s"` and kills the process. `idle_sec` =
`config.get("explainer.idle_sec", env_var="ASTERISM_EXPLAINER_IDLE_SEC",
default=600)`. `_TIMEOUT_SEC` remains only as agy's `--print-timeout`
(its whole-answer clock IS its idle clock, having no stream) and is set
from the same knob. The keepalive comment is written on every
`queue.Empty` wake after 15 s of silence.

## 4. Model picker — the seat source

`serve/app._model_groups` is the one place that knows which providers
are installed on this machine and what each offers (declared list from
`config.MODEL_CHOICES_BY_PROVIDER`, or the live `agy models` probe on
`/api/models/refresh`). It moves, unchanged, to
`Tooling/serve/model_catalog.py` (with its memo and `_MODELS_ARGV`) so
`chat.py` can import it without importing `app`.

- `/api/chat/state` returns `groups: ModelGroup[]` = `_model_groups`
  filtered to providers that have an explainer backend
  (`explainer.BACKENDS`), and `model_default`.
- The panel renders ONE `<Select>` with an `<optgroup>` per provider,
  exactly as `RunParameters.modelPicker` does (`(not installed)`,
  `— list not live` suffixes). It POSTs `/api/models/refresh` once per
  mount, like RunParameters, and swaps in the live groups.
- One picker decides both (`lib/models.providerForModel`): choosing a
  model from another provider's group seats the explainer on that
  provider FOR THIS SESSION. `ChatBody.model` is validated server-side
  against `groups ∪ {model_default}` → 422 naming the offer; the
  backend is the group's provider (`explainer.backend_for`). The
  session record stores `model` and `provider`; a session's provider
  cannot change mid-conversation (the handle belongs to one CLI): a
  pick from another provider on a session with turns is refused by the
  panel with `start a new conversation to switch backends` under the
  picker.
- `explainer._Backend.models` tuples are deleted; `default_model` stays
  and must be a member of the declared list (`claude-sonnet-5`,
  `gemini-3.6-flash-high`). The stored `asterism.chat.model` that is not
  in the offer resets to the default (existing behaviour, keeps
  working for the retired aliases `haiku/sonnet/opus`).

## 5. Settings — a floating overlay, a gear

- `#/settings` stops being a page. The corner control opens
  `<SettingsWindow>` — the existing `Settings` body inside
  `ConfirmWindow` (the console's only floating surface; the
  `createPortal` / `fixed inset-0` ratchets stay at one hit each).
  `ConfirmWindow` gains `width: 'lg'` (`w-[44rem]`) and a scrolling body
  (`max-h-[85vh] overflow-y-auto`). Backdrop click and Escape close it;
  the two-step Quit and the account actions work as they did.
- Open state lives in `App` (`settingsOpen`), not in the address: the
  reader stays where they were. `#/settings` remains a legal address for
  old links: it opens the overlay over the picker and rewrites the
  address to `#/` (`replace`).
- Both corners (`ProjectShell`, `Projects`) call `onOpenSettings` instead
  of `to="/settings"`; `[data-corner] > *` stays exactly two.
- `glyphs.GEAR` becomes a gear — a ring with eight teeth and a hub, in
  the vocabulary's stroke (1.1, `currentColor`, 15px, hub filled with
  `var(--color-surface)` like the sliders' knobs were):

```tsx
export const GEAR = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path
      d="M8 1.6l1 1.9 2.1-.5.6 2.1 2 .8-.8 2 1.4 1.7-1.7 1.3.2 2.2-2.2.2-1.3 1.7-1.7-1.4-2 .8-.8-2L2.5 8.9l1.4-1.7-.5-2.1 2-.8.6-2.1 2.1.5z"
      stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" opacity="0.7"
    />
    <circle cx="8" cy="8" r="2.1" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
  </svg>
)
```

(The implementer may redraw the tooth path for symmetry; the contract is
ring + teeth + hub, stroke only, no fill but the hub.)

## 6. Tests (red first)

Backend (`tests/test_serve_chat.py`, `tests/test_explainer_backend.py`,
new `tests/test_chat_sessions.py`):
- session CRUD per Project; title derivation and custom rename;
  reuse of an empty session; DELETE is 409 while busy; a question on a
  session of another Project is 422.
- `truncate_to` drops later turns, clears the handle, and the next
  prompt carries the replay block (clipped).
- reader: fixture from a real stream → `tool_start` (with parsed input)
  and `tool_end` (with `ms`, `ok`) in order; string clipping.
- idle deadline: a fake queue that emits a `tool_start` every 2 s for
  longer than the old wall would have allowed does NOT time out; a
  silent queue does, after `idle_sec`, with the named error.
- `/api/chat/state` `groups` come from `model_catalog` and contain only
  explainer-backed providers; an off-list model is 422 naming the offer.

Frontend (`web/src/lib/*.test.ts`, node vitest — pure laws):
- `chatStream.ts`: reduce(events) → rows/text; `toolLine`;
  `summarizeTools`; end-without-start still renders.
- `chatSessions.ts`: `deriveTitle`, sort order, `truncateAt`.
- `models.ts`: unchanged, reused.
- Smoke (`web/tests/smoke.spec.ts`): the Settings test opens the overlay
  from the corner and asserts the same four sections; `[data-corner]`
  count stays 2; Assistant panel opens with Ctrl+/ and shows the sessions
  fold.
