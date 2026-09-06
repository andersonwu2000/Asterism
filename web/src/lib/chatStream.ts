import type { ChatToolRow } from './types'

/*
 * One assistant turn, reduced from the wire (assistant_redesign
 * _2026-09-06.md §3). Pure, so the grammar of a turn can be held still
 * and tested — a stream is the one thing a rendering test cannot.
 *
 * The panel owns the socket and the scroll; everything about WHAT a
 * turn is — which rows exist, what settled them, what the collapsed
 * line says — lives here.
 */

/** One tool call, as the turn shows it. `running` is the live state;
 * `startedAt` is the browser's clock, because a row's duration while
 * it runs is ours to count and only its END carries the engine's `ms`. */
export interface ToolRow {
  id: string
  name: string
  input: Record<string, unknown>
  startedAt: number
  /** the engine's own measure, once the call returned */
  ms: number | null
  /** null while running, and on a turn that ended before this row did */
  ok: boolean | null
  result: string | null
  running: boolean
}

export interface StreamTurn {
  text: string
  rows: ToolRow[]
  /** the one-line stage, until prose starts */
  stage: string | null
  done: boolean
  ok: boolean
  /** what to say under the answer: an abnormal end, or the error */
  note: string | null
}

export function emptyTurn(): StreamTurn {
  return { text: '', rows: [], stage: null, done: false, ok: true, note: null }
}

// -- the wire ----------------------------------------------------------------

export interface SseChunk {
  events: Record<string, unknown>[]
  /** the tail that is not a complete frame yet */
  rest: string
}

/** Complete `data:` frames out of a buffer, and whatever is left over.
 *
 * Comment lines (`: keepalive`, written every 15 s while the CLI is
 * thinking) are the liveness signal and not events: they carry no JSON,
 * and a parser that fed them to `JSON.parse` would throw on every wake
 * of an idle stream. A malformed frame is skipped rather than fatal —
 * the frames after it are still the engine talking. */
export function parseSseFrames(buf: string): SseChunk {
  const events: Record<string, unknown>[] = []
  let rest = buf
  for (;;) {
    const nl = rest.indexOf('\n\n')
    if (nl < 0) break
    const frame = rest.slice(0, nl)
    rest = rest.slice(nl + 2)
    for (const raw of frame.split('\n')) {
      const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw
      if (!line.startsWith('data:')) continue
      try {
        const v = JSON.parse(line.slice(line.startsWith('data: ') ? 6 : 5))
        if (v && typeof v === 'object') events.push(v as Record<string, unknown>)
      } catch {
        /* a partial or malformed frame — the next one still counts */
      }
    }
  }
  return { events, rest }
}

// -- the reduction -----------------------------------------------------------

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const num = (v: unknown): number | null => (typeof v === 'number' ? v : null)

/** A tool call is a boundary in the prose.
 *
 * The model says what it is about to look for, calls something, and
 * then says what it found — two thoughts, minutes apart on the wire.
 * The deltas around them are separate text blocks in the stream, so
 * neither carries the newline that separates them, and appending them
 * to one string glues the second sentence onto the first: the reader
 * gets a paragraph nobody wrote (owner, 2026-09-06). The break is
 * written where the interruption happened, not guessed at render time
 * — `lib/prose` joins single newlines as spaces, so it takes a blank
 * line to open a paragraph. Nothing is opened before the first word,
 * and a run of calls with no prose between them breaks only once. */
function breakAtTool(text: string): string {
  if (text.trim() === '' || /\n[ \t]*\n[ \t]*$/.test(text)) return text
  return text.replace(/[ \t\r\n]+$/, '') + '\n\n'
}

/** Fold one event into the turn. Never mutates: the panel holds the
 * turn in state and React needs a new object to paint. */
export function reduceEvent(
  turn: StreamTurn,
  ev: Record<string, unknown>,
  now: number = Date.now(),
): StreamTurn {
  const type = str(ev.type)
  if (type === 'status') {
    const stage = str(ev.stage)
    return stage === null ? turn : { ...turn, stage }
  }
  if (type === 'delta') {
    const text = str(ev.text)
    if (text === null) return turn
    // prose has started; the stage line has said all it can
    return { ...turn, stage: null, text: turn.text + text }
  }
  if (type === 'tool_start') {
    const id = str(ev.id) ?? `tool-${turn.rows.length}`
    if (turn.rows.some((r) => r.id === id && r.running)) return turn
    const input = ev.input && typeof ev.input === 'object' ? (ev.input as Record<string, unknown>) : {}
    const row: ToolRow = {
      id,
      name: str(ev.name) ?? 'tool',
      input,
      startedAt: now,
      ms: null,
      ok: null,
      result: null,
      running: true,
    }
    return { ...turn, text: breakAtTool(turn.text), rows: [...turn.rows, row] }
  }
  if (type === 'tool_end') {
    const id = str(ev.id) ?? ''
    const ms = num(ev.ms)
    const ok = ev.ok !== false
    const result = str(ev.result)
    const at = turn.rows.findIndex((r) => r.id === id && r.running)
    if (at < 0) {
      // an end whose start never arrived: never drop what the engine
      // said. The row spans backwards from now, so the wall clock the
      // collapsed line reports stays honest.
      const row: ToolRow = {
        id: id === '' ? `end-${turn.rows.length}` : id,
        name: str(ev.name) ?? 'tool',
        input: {},
        startedAt: now - (ms ?? 0),
        ms,
        ok,
        result,
        running: false,
      }
      return { ...turn, text: breakAtTool(turn.text), rows: [...turn.rows, row] }
    }
    const rows = turn.rows.slice()
    rows[at] = { ...rows[at], ms, ok, result, running: false }
    return { ...turn, rows }
  }
  if (type === 'done') {
    const ok = ev.ok !== false
    return {
      ...turn,
      rows: settle(turn.rows),
      stage: null,
      done: true,
      ok,
      note: ok ? turn.note : `the answer ended abnormally (${str(ev.subtype) ?? ''})`,
    }
  }
  if (type === 'error') {
    return {
      ...turn,
      rows: settle(turn.rows),
      stage: null,
      done: true,
      ok: false,
      note: str(ev.detail) ?? 'unknown error',
    }
  }
  return turn
}

/** A turn that ended leaves nothing pulsing. A row we never heard the
 * end of keeps `ok: null` — it is not a failure, it is a silence. */
function settle(rows: ToolRow[]): ToolRow[] {
  if (!rows.some((r) => r.running)) return rows
  return rows.map((r) => (r.running ? { ...r, running: false } : r))
}

// -- what a row says ---------------------------------------------------------

/** The name the engine calls a tool by, minus the plumbing.
 *
 * Every tool the Assistant is given arrives as `mcp__<server>__<verb>`
 * — the transport's business, not the reader's. The prefix is the same
 * on every row, so it says nothing while pushing the verb out of a
 * narrow panel. The RECORD keeps the raw name; the screen and the verb
 * families read this one. */
export function bareToolName(name: string): string {
  return name.replace(/^mcp__.+?__/, '')
}

/** The keys worth showing, in the order the design fixed. A tool's
 * arguments are a JSON object of unknown shape; this picks the ones a
 * mathematician reads as "what it went to look at". `read` and `code`
 * joined the list from the live tools: inspect asks in `queries`, and
 * compute sends a `code` block. */
const ARG_KEYS: string[] = [
  'path',
  'file',
  'read',
  'query',
  'pattern',
  'expr',
  'code',
  'command',
  'name',
  'problem',
  'goal',
  'text',
]

const MAX_ARG = 80
/** How deep an argument may hide. inspect's is two containers down
 * (`{queries: [{read: ...}]}`); nothing useful has been further, and an
 * unbounded walk over a tool's whole input is a different feature. */
const MAX_DEPTH = 3
const MAX_LEAVES = 12
/** Three names is a line; the fourth is a paragraph. */
const MAX_SHOWN = 3

interface Leaf {
  key: string
  value: string
}

/** Every string an input names, depth-first, each already trimmed —
 * the trim comes BEFORE the newline mark, or a code block that starts
 * on line 2 reads as a leading return. */
function walk(node: unknown, depth: number, key: string, out: Leaf[]): void {
  if (out.length >= MAX_LEAVES) return
  if (typeof node === 'string') {
    const t = node.trim()
    if (t !== '') out.push({ key, value: t })
    return
  }
  if (typeof node === 'number') {
    if (ARG_KEYS.includes(key)) out.push({ key, value: String(node) })
    return
  }
  if (depth >= MAX_DEPTH) return
  // an array inherits its key: `{read: ['a', 'b']}` is still two reads
  if (Array.isArray(node)) {
    for (const v of node) walk(v, depth + 1, key, out)
    return
  }
  if (node !== null && typeof node === 'object')
    for (const [k, v] of Object.entries(node as Record<string, unknown>))
      walk(v, depth + 1, k, out)
}

/** One line of argument, in faint ink beside the tool's name.
 *
 * `_name` is the tool it belongs to: part of the contract because the
 * summary is per-tool by design, though the fixed key order answers
 * every tool the engine currently offers without branching on it. */
export function toolLine(_name: string, input: Record<string, unknown> | null | undefined): string {
  const found: Leaf[] = []
  walk(input ?? {}, 0, '', found)
  const ordered = [
    ...ARG_KEYS.flatMap((k) => found.filter((l) => l.key === k).map((l) => l.value)),
    ...found.filter((l) => !ARG_KEYS.includes(l.key)).map((l) => l.value),
  ]
  const shown = [...new Set(ordered)].slice(0, MAX_SHOWN)
  if (shown.length === 0) return ''
  const one = shown
    .map((v) => v.replace(/\r?\n/g, '⏎').replace(/["'`]/g, ''))
    .join(' · ')
  return one.length > MAX_ARG ? one.slice(0, MAX_ARG - 1) + '…' : one
}

// -- the collapsed line ------------------------------------------------------

/** Verb families: what a reader would say happened, not which function
 * ran. An unlisted tool keeps its own name — inventing a family for it
 * would describe the wrong act. */
const FAMILY: Record<string, string> = {
  inspect: 'read',
  read_project_doc: 'read',
  Read: 'read',
  loogle: 'loogle',
  paper_search: 'papers',
  paper_fetch: 'papers',
  compute: 'compute',
  daemon_status: 'engine',
  Grep: 'workspace',
  Glob: 'workspace',
}

function phrase(family: string, n: number): string {
  const times = n > 1 ? ` ×${n}` : ''
  switch (family) {
    case 'read':
      return `read ${n} file${n === 1 ? '' : 's'}`
    case 'loogle':
      return n === 1 ? 'searched Mathlib once' : `searched Mathlib ${n}×`
    case 'compute':
      return n === 1 ? 'computed once' : `computed ${n}×`
    case 'papers':
      return `papers${times}`
    case 'engine':
      return `asked the engine${times}`
    case 'workspace':
      return `searched the workspace${times}`
    default:
      return `${family}${times}`
  }
}

function wall(ms: number): string {
  const sec = ms / 1000
  if (sec < 60) return `${sec.toFixed(1)}s`
  return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`
}

/** The one line a finished turn's timeline folds into: what happened,
 * in the order it happened, and how long the whole of it took. */
export function summarizeTools(rows: ToolRow[]): string {
  if (rows.length === 0) return ''
  const order: string[] = []
  const count = new Map<string, number>()
  let first = Infinity
  let last = -Infinity
  for (const r of rows) {
    // the family is the VERB, not the transport's name for it
    const bare = bareToolName(r.name)
    const fam = FAMILY[bare] ?? bare
    if (!count.has(fam)) order.push(fam)
    count.set(fam, (count.get(fam) ?? 0) + 1)
    first = Math.min(first, r.startedAt)
    last = Math.max(last, r.startedAt + (r.ms ?? 0))
  }
  const parts = order.map((f) => phrase(f, count.get(f) ?? 0))
  if (last > first) parts.push(wall(last - first))
  return parts.join(' · ')
}

/** The rows of a turn read back from disk.
 *
 * The record keeps each call's DURATION, never the clock it ran on, so
 * the timeline is rebuilt sequentially — which is what the CLI makes:
 * one tool at a time, each starting where the last one ended. The fold
 * then reports the sum, and says the same thing it said live. */
export function rowsFromRecord(tools: ChatToolRow[] | null | undefined): ToolRow[] {
  let at = 0
  return (tools ?? []).map((t, i) => {
    const row: ToolRow = {
      id: t.id || `row-${i}`,
      name: t.name,
      input: t.input ?? {},
      startedAt: at,
      ms: t.ms ?? null,
      ok: t.ok,
      result: t.result ?? null,
      running: false,
    }
    at += t.ms ?? 0
    return row
  })
}
