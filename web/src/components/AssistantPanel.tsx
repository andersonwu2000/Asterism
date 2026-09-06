import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { parseProjectRoute } from '../lib/projectRoute'
import { useRoute } from '../lib/router'
import { apiDelete, apiGet, apiPatch, apiPost } from '../lib/api'
import { affectedSummary, commandTitle, splitPrepared } from '../lib/commands'
import type { PreparedCommand } from '../lib/commands'
import { focusBody, useScreenFocus } from '../lib/focus'
import type { ScreenFocus } from '../lib/focus'
import { renderProse } from '../lib/prose'
import { canSwitchModel, deriveTitle, sortSessions, truncateAt } from '../lib/chatSessions'
import { explainerGroups } from '../lib/models'
import { emptyTurn, endStream, parseSseFrames, reduceEvent, rowsFromRecord } from '../lib/chatStream'
import type { StreamTurn } from '../lib/chatStream'
import type {
  ChatSession,
  ChatSessionSummary,
  ChatToolRow,
  ChatTurn,
  ModelGroup,
} from '../lib/types'
import CommandConfirm from './CommandConfirm'
import ModelPicker from './ModelPicker'
import { Button } from './ui'
import ActivityRows from './assistant/ActivityRows'
import SessionsFold from './assistant/SessionsFold'
import UserTurn from './assistant/UserTurn'

/*
 * The Assistant (human_interface_design.md §1.1, §1.4, §3.5, §3.8;
 * assistant_redesign_2026-09-06.md): a docked right panel, opened by
 * the corner glyph or Ctrl+/. Docked and not floating on the owner's
 * own reasoning — "左讀右問的姿勢不能被蓋住": reading on the left while
 * asking on the right is the posture, and a window over the page
 * destroys it.
 *
 * It is a CONVERSATION surface: a Project holds many transcripts and
 * one current one, they live on disk beside the workspace, and the
 * browser remembers only which one is open. What a turn DID is shown
 * while it does it — a row per tool call, folding into one line when
 * the answer lands.
 *
 * It PREPARES commands and never submits them (§3.8). When an answer
 * carries the `prepare_command` tool's JSON, the panel offers to review
 * it — and the review is the same confirmation window a person's own
 * command goes through. The panel never posts to `/api/commands`; the
 * button in that window does.
 *
 * Field-tested shapes borrowed from QPaper's chat panel (design SoT
 * docs/internal/chat_explainer_design.md "借鑑" section): page context
 * frozen at send, partial answers kept as first-class messages, send
 * button morphs to stop, failed sends roll the text back into the
 * input, citations are model-emitted tokens that ONLY the client
 * turns into navigation.
 */

interface ChatState {
  busy: boolean
  model_default: string
  /** every provider with an explainer backend, and what it offers */
  groups?: ModelGroup[]
  /* which backend answers, and the two ways one can be honestly worse
   * than another (engine SoT: Tooling/llm/explainer.py). Optional so an
   * older serve still renders. */
  provider?: string
  conversation_memory?: boolean
  read_scope?: 'workspace' | 'process'
  /** the seat's own sentence about its reach. The panel states the
   * EXCEPTION (`read_scope: 'process'`) above the composer rather than
   * hanging the settled case off a tooltip nobody hovers. */
  read_note?: string
  available?: boolean
  unavailable_detail?: string
}

type Page = { kind: string; name?: string }

/** What the reader is looking at — frozen per send. The PAGE and the
 * Project come from the address; the FOCUS is the address plus whatever
 * the mounted section published (`lib/focus`), because a selected star
 * and an open document are the screen's state, not the URL's. */
interface Where {
  page: Page
  project: string | null
  focus: Record<string, unknown> | null
}

function whereFromRoute(segments: string[], screen: ScreenFocus): Where {
  const r = parseProjectRoute(segments)
  if (r) {
    const focus = focusBody(r.problem, screen)
    if (r.section === 'engine')
      return { page: { kind: 'engine' }, project: r.project, focus }
    if (r.problem)
      return { page: { kind: 'problem', name: r.problem }, project: r.project, focus }
    return { page: { kind: 'board' }, project: r.project, focus }
  }
  const s0 = segments[0] ?? ''
  // the addresses that are not inside a Project
  if (s0 === 'problems' && segments[1])
    return { page: { kind: 'problem', name: segments[1] }, project: null, focus: null }
  if (s0 === 'settings') return { page: { kind: 'engine' }, project: null, focus: null }
  return { page: { kind: 'board' }, project: null, focus: null }
}

/** An answer, with whatever it PREPARED lifted out of the prose (§3.8).
 *
 * `prepare_command` returns JSON; the console reads that structured
 * block and never the sentences around it — a console that inferred a
 * command from prose would be inventing one. The block itself is
 * machine bookkeeping and does not belong on a mathematician's screen,
 * so it is replaced by the one thing it is for: a way to review it.
 * Submitting is the confirmation window's button, never this panel's. */
function Answer({
  text,
  onReview,
}: {
  text: string
  onReview: (c: PreparedCommand) => void
}) {
  const { text: prose, commands } = useMemo(() => splitPrepared(text), [text])
  return (
    <>
      {prose.trim() !== '' && renderProse(prose)}
      {commands.map((c, i) => (
        <div
          key={i}
          className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-edge bg-wash px-3 py-2"
        >
          <span className="text-[12px] text-ink">{commandTitle(c.kind)}</span>
          {c.preview && (
            <span className="tnum text-[11px] text-ink-faint">
              {affectedSummary(c.preview)}
            </span>
          )}
          <Button
            variant="outline"
            size="xs"
            className="ml-auto"
            onClick={() => onReview(c)}
            title="read what it would close, then decide — nothing is queued until you press Confirm"
          >
            Review &amp; submit…
          </Button>
        </div>
      ))}
    </>
  )
}

const SUGGESTIONS = [
  'Why is this problem stalled?',
  'What happened in the last few decisions?',
  'What exactly am I endorsing when I sign off?',
]

// -- the drawer --------------------------------------------------------------

// The browser keeps three keys and no transcript (§2): which
// conversation is open on each Project, the model, and the reading
// width. The transcripts are the engine's, on disk, and survive the
// tab that asked the questions.
const GLOBAL_SESSION = '_global'
const SESSION_KEY = 'asterism.chat.session'
const MODEL_KEY = 'asterism.chat.model'
const WIDTH_KEY = 'asterism.chat.width'
const DEFAULT_WIDTH = 460

function sessionKey(project: string | null): string {
  return `${SESSION_KEY}:${project ?? GLOBAL_SESSION}`
}

function local(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function keep(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* private mode — the posture just won't be remembered */
  }
}

const MIN_WIDTH = 360
const maxWidth = () => Math.min(window.innerWidth * 0.7, 960)
const readingWidth = () => Math.min(window.innerWidth * 0.55, 800)

/** The turn as the record keeps it — what streamed, and what it did. */
function recordTools(turn: StreamTurn): ChatToolRow[] {
  return turn.rows.map((r) => ({
    id: r.id,
    name: r.name,
    input: r.input,
    ok: r.ok !== false,
    ms: r.ms,
    result: r.result,
  }))
}

export default function AssistantPanel({
  open,
  onClose,
  onStreamingChange,
  onReplyWaiting,
}: {
  open: boolean
  onClose: () => void
  onStreamingChange: (v: boolean) => void
  /** an answer finished while the panel was closed — the corner glyph
   * carries that, and only the panel knows it happened */
  onReplyWaiting: (v: boolean) => void
}) {
  const route = useRoute()
  const screen = useScreenFocus()
  // the Project binds the conversations (§1.1-2) — it comes from the
  // address, and everything session-shaped keys off it
  const project = parseProjectRoute(route.segments)?.project ?? null

  const [meta, setMeta] = useState<ChatState | null>(null)
  const [liveGroups, setLiveGroups] = useState<ModelGroup[] | null>(null)
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [live, setLive] = useState<StreamTurn | null>(null)
  const [foldOpen, setFoldOpen] = useState(false)
  const [foldNote, setFoldNote] = useState<{ id: string | null; text: string } | null>(null)
  const [openTools, setOpenTools] = useState<Set<number>>(new Set())
  const [selTurn, setSelTurn] = useState<number | null>(null)
  const [editing, setEditing] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState('')
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  // the model choice persists (QA, 2026-07-20): it silently reverted
  // to the costlier default on every reload — a user who parked it on
  // the cheap seat kept paying for the strong one
  const [model, setModelState] = useState<string | null>(() => local(MODEL_KEY))
  const setModel = (m: string) => {
    setModelState(m)
    keep(MODEL_KEY, m)
  }
  /** the prepared command the reader asked to review — it opens THE
   * confirmation window, the same one a command from a star opens */
  const [review, setReview] = useState<PreparedCommand | null>(null)
  const [width, setWidthState] = useState(() => {
    const w = Number(local(WIDTH_KEY))
    return Number.isFinite(w) && w >= MIN_WIDTH ? w : DEFAULT_WIDTH
  })
  const [wide, setWide] = useState(false)
  const narrowRef = useRef(width)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const streamingRef = useRef(false)
  const liveRef = useRef<StreamTurn>(emptyTurn())
  const turnsRef = useRef<ChatTurn[]>(turns)
  turnsRef.current = turns
  const sessionRef = useRef<string | null>(sessionId)
  sessionRef.current = sessionId

  // the probe answers for every backend installed on this machine;
  // only the ones with an explainer can be seated on a question
  const groups = explainerGroups(meta?.groups ?? [], liveGroups)
  const currentSession = sessions.find((s) => s.id === sessionId) ?? null
  const picked = model ?? meta?.model_default ?? ''

  const listSessions = useCallback(async (proj: string | null) => {
    const q = proj ? `?project=${encodeURIComponent(proj)}` : ''
    const r = await apiGet<{ sessions: ChatSessionSummary[] }>(`/api/chat/sessions${q}`)
    return sortSessions(r.sessions ?? [])
  }, [])

  const loadRecord = useCallback(async (id: string) => {
    const r = await apiGet<ChatSession>(`/api/chat/sessions/${encodeURIComponent(id)}`)
    return r.turns ?? []
  }, [])

  // The seat facts, and this Project's conversations. Both are asked
  // about the same shelf, so the panel can never show one Project's
  // transcript under another's name.
  useEffect(() => {
    let gone = false
    setSessions([])
    setSessionId(null)
    setTurns([])
    setLive(null)
    setFoldOpen(false)
    setFoldNote(null)
    setOpenTools(new Set())
    setSelTurn(null)
    setEditing(null)
    setNote(null)
    apiGet<ChatState>(
      `/api/chat/state${project ? `?project=${encodeURIComponent(project)}` : ''}`,
    )
      .then((s) => {
        if (gone) return
        setMeta(s)
        // a model stored while another provider was seated is not a
        // choice here — a name no group offers dies at the spawn
        const offer = s.groups ?? []
        const offered = offer.some((g) => g.models.includes(model ?? ''))
        // an empty offer is a serve that cannot say, not a refusal
        if (model !== null && offer.length > 0 && !offered && model !== s.model_default)
          setModelState(null)
      })
      .catch(() => undefined)
    void (async () => {
      try {
        const rows = await listSessions(project)
        if (gone) return
        setSessions(rows)
        const remembered = local(sessionKey(project))
        const pick = rows.find((r) => r.id === remembered) ?? rows[0] ?? null
        if (!pick) return
        setSessionId(pick.id)
        const record = await loadRecord(pick.id)
        if (!gone) setTurns(record)
      } catch {
        /* an older serve, or none — the empty state says what to do */
      }
    })()
    return () => {
      gone = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, listSessions, loadRecord])

  // Which models exist is a question only the machine can answer, and a
  // kept list goes stale the day a vendor ships a tier — so it is asked,
  // but not on MOUNT. The probe spawns a subprocess per backend, and
  // this panel mounts on every project page: opening a task to read it
  // was making the console run `agy models` (the research-entry cases
  // caught exactly that, 2026-09-06 — a reading page must write and
  // spawn nothing). It is asked when someone opens the picker, which is
  // the moment the answer is wanted, and once per panel after that: the
  // menu is already open by then, and a list rearranging under an open
  // menu is worse than a list one click old.
  const askedModels = useRef(false)
  const refreshModels = useCallback(() => {
    if (askedModels.current) return
    askedModels.current = true
    apiPost<{ groups: ModelGroup[] }>('/api/models/refresh', {})
      .then((r) => setLiveGroups(r.groups))
      .catch(() => {
        /* keep the declared lists — never blank the picker */
      })
  }, [])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])
  // the glyph's two states are the panel's to report: it blinks while
  // the answer is being written (onStreamingChange) and holds a steady
  // mark once one has landed unseen
  const openRef = useRef(open)
  openRef.current = open

  const setStreamingBoth = useCallback(
    (v: boolean) => {
      streamingRef.current = v
      setStreaming(v)
      onStreamingChange(v)
    },
    [onStreamingChange],
  )

  // autoscroll only when the reader is already at the bottom
  const nearBottom = useRef(true)
  const onScroll = useCallback(() => {
    const el = scrollRef.current
    if (el) nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }, [])
  useEffect(() => {
    const el = scrollRef.current
    if (el && nearBottom.current) el.scrollTop = el.scrollHeight
  })

  // -- the conversations -----------------------------------------------------

  const openSession = useCallback(
    async (id: string) => {
      if (streamingRef.current) return
      setFoldNote(null)
      setSessionId(id)
      keep(sessionKey(project), id)
      setOpenTools(new Set())
      setSelTurn(null)
      setEditing(null)
      setLive(null)
      try {
        setTurns(await loadRecord(id))
      } catch (e) {
        setTurns([])
        setFoldNote({ id, text: String((e as Error).message) })
      }
    },
    [project, loadRecord],
  )

  const newSession = useCallback(async () => {
    if (streamingRef.current) return
    setFoldNote(null)
    try {
      const s = await apiPost<ChatSessionSummary>('/api/chat/sessions', { project })
      setSessions((prev) => sortSessions([s, ...prev.filter((p) => p.id !== s.id)]))
      setSessionId(s.id)
      keep(sessionKey(project), s.id)
      setTurns([])
      setLive(null)
      setOpenTools(new Set())
      setSelTurn(null)
      setEditing(null)
      setFoldOpen(false)
      inputRef.current?.focus()
    } catch (e) {
      setFoldNote({ id: null, text: String((e as Error).message) })
    }
  }, [project])

  const renameSession = useCallback(
    async (id: string, title: string) => {
      setFoldNote(null)
      try {
        await apiPatch<ChatSessionSummary>(
          `/api/chat/sessions/${encodeURIComponent(id)}`,
          { title },
        )
        setSessions(await listSessions(project))
      } catch (e) {
        setFoldNote({ id, text: String((e as Error).message) })
      }
    },
    [project, listSessions],
  )

  const deleteSession = useCallback(
    async (id: string) => {
      setFoldNote(null)
      try {
        await apiDelete(`/api/chat/sessions/${encodeURIComponent(id)}`)
      } catch (e) {
        setFoldNote({ id, text: String((e as Error).message) })
        return
      }
      const rows = await listSessions(project).catch(() => [])
      setSessions(rows)
      if (id === sessionRef.current) {
        const next = rows[0] ?? null
        setTurns([])
        setLive(null)
        setSessionId(next?.id ?? null)
        keep(sessionKey(project), next?.id ?? null)
        if (next) void openSession(next.id)
      }
    },
    [project, listSessions, openSession],
  )

  // -- asking ----------------------------------------------------------------

  const send = useCallback(
    async (raw: string, truncateTo?: number) => {
      const text = raw.trim()
      if (text === '' || streamingRef.current) return
      // frozen at send: the answer is about the screen the question was
      // asked from, not the one it arrives on
      const { page, project: proj, focus } = whereFromRoute(route.segments, screen)
      const reask = truncateTo !== undefined
      setNote(null)
      setFoldOpen(false)
      setSelTurn(null)
      setEditing(null)

      // the session a question is filed on is made when the first
      // question is asked, not when the panel opens: an empty
      // conversation per glance is a shelf of nothing
      let sid = sessionRef.current
      if (sid === null) {
        try {
          const s = await apiPost<ChatSessionSummary>('/api/chat/sessions', { project: proj })
          sid = s.id
          sessionRef.current = s.id
          setSessionId(s.id)
          keep(sessionKey(proj), s.id)
          setSessions((prev) => sortSessions([s, ...prev.filter((p) => p.id !== s.id)]))
        } catch (e) {
          setNote(String((e as Error).message))
          return
        }
      }

      const before = turnsRef.current
      const base = reask ? (truncateAt(before, truncateTo) ?? before) : before
      if (!reask) {
        setInput('')
        if (inputRef.current) inputRef.current.style.height = 'auto'
      }
      setTurns([...base, { role: 'user', text, at: new Date().toISOString() }])
      liveRef.current = { ...emptyTurn(), stage: 'context' }
      setLive(liveRef.current)
      setStreamingBoth(true)
      const ac = new AbortController()
      abortRef.current = ac

      const rollback = (detail: string) => {
        // failed send → the question returns to the input box, no
        // orphan turn left standing
        setTurns(before)
        if (!reask) setInput(text)
        setNote(detail)
      }
      const commit = (extra?: string) => {
        const l = liveRef.current
        if (l.text === '' && l.rows.length === 0) {
          setTurns(base)
          if (extra !== undefined) setNote(extra)
          return
        }
        setTurns([
          ...base,
          { role: 'user', text, at: new Date().toISOString() },
          {
            role: 'assistant',
            text: l.text,
            at: new Date().toISOString(),
            ok: l.ok,
            note: extra ?? l.note,
            tools: recordTools(l),
          },
        ])
      }

      let landed = false
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            session_id: sid,
            page,
            project: proj,
            focus,
            model: picked,
            ...(reask ? { truncate_to: truncateTo } : {}),
          }),
          signal: ac.signal,
        })
        if (!res.ok) {
          let detail = res.statusText
          try {
            detail = String((await res.json())?.detail ?? detail)
          } catch {
            /* non-JSON body */
          }
          rollback(res.status === 409 ? 'still answering the previous question' : detail)
          return
        }
        const reader = res.body?.getReader()
        if (!reader) throw new Error('no stream')
        const dec = new TextDecoder()
        let buf = ''
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const { events, rest } = parseSseFrames(buf)
          buf = rest
          for (const ev of events) {
            if (ev.type === 'session') {
              // the first frame names the session this turn was filed
              // on — the server's answer wins over ours
              const id = typeof ev.id === 'string' ? ev.id : null
              if (id !== null && id !== sessionRef.current) {
                sessionRef.current = id
                setSessionId(id)
                keep(sessionKey(proj), id)
              }
              continue
            }
            liveRef.current = reduceEvent(liveRef.current, ev)
            setLive(liveRef.current)
            if (ev.type === 'done' || ev.type === 'error') {
              landed = true
              if (ev.type === 'done' && !openRef.current) onReplyWaiting(true)
            }
          }
        }
        if (!landed) {
          // the body closed without a `done` or an `error`. With nothing
          // to show, the question goes back to the composer; with half
          // an answer that half is kept -- and it now says why it is
          // half, instead of leaving the call it stopped inside pulsing
          // under it forever (2026-09-06).
          const why = 'the stream ended before the answer did'
          if (liveRef.current.text === '' && liveRef.current.rows.length === 0) {
            rollback(why)
            return
          }
          liveRef.current = endStream(liveRef.current, why)
          setLive(liveRef.current)
        }
        commit()
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          // partial answers are first-class: keep what streamed
          commit('stopped')
        } else {
          rollback(`could not reach the engine (${(e as Error).message})`)
          return
        }
      } finally {
        setLive(null)
        liveRef.current = emptyTurn()
        setStreamingBoth(false)
        abortRef.current = null
        // titles, turn counts and the order all moved
        void listSessions(proj)
          .then(setSessions)
          .catch(() => undefined)
      }
    },
    [picked, route.segments, screen, onReplyWaiting, setStreamingBoth, listSessions],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  // width drag — clamped AND remembered: a reading posture is kept the
  // way `railOpen` is (the July "clamp, don't persist" ruling predates
  // the complaint that this panel is cramped)
  const dragRef = useRef<{ startX: number; startW: number } | null>(null)
  useEffect(() => {
    const move = (e: MouseEvent) => {
      const d = dragRef.current
      if (!d) return
      const w = Math.min(Math.max(d.startW + (d.startX - e.clientX), MIN_WIDTH), maxWidth())
      narrowRef.current = w
      setWide(false)
      setWidthState(w)
    }
    const up = () => {
      if (dragRef.current) keep(WIDTH_KEY, String(narrowRef.current))
      dragRef.current = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
  }, [])

  const toggleWide = () => {
    if (wide) {
      setWidthState(narrowRef.current)
      setWide(false)
    } else {
      narrowRef.current = width
      setWidthState(readingWidth())
      setWide(true)
    }
  }

  // What this backend can and cannot promise. Both notes are exceptions
  // — they appear only when the seated provider is weaker than the
  // fenced, remembering one, so the settled case earns no ink.
  const noMemory = meta ? meta.conversation_memory === false : false
  const unfencedReads = meta?.read_scope === 'process'
  // say it before the question is typed, not after it is thrown away
  const unavailable: string | null =
    meta?.available === false
      ? meta.unavailable_detail || 'the explainer has no usable backend on this machine'
      : null
  // a session's handle belongs to one CLI, so its backend cannot change
  // mid-conversation — and the way out is named
  const wrongBackend = !canSwitchModel(currentSession, groups, picked)

  const firstQuestion = turns.find((t) => t.role === 'user')?.text ?? ''
  const title =
    currentSession?.title || deriveTitle(firstQuestion) || 'new conversation'
  const older = sessions.filter((s) => s.id !== sessionId && s.turns > 0).slice(0, 2)

  const toggleTools = (i: number) =>
    setOpenTools((s) => {
      const next = new Set(s)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })

  // closed = hidden, not unmounted — a stream keeps writing into the
  // panel while it is shut, and the corner glyph says so
  return (
    <aside
      className={`relative shrink-0 flex-col border-l border-edge bg-surface ${open ? 'flex' : 'hidden'}`}
      style={{ width }}
      aria-label="assistant"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose()
      }}
    >
      <div
        className="absolute top-0 bottom-0 left-0 z-10 w-1 cursor-col-resize hover:bg-edge"
        onMouseDown={(e) => {
          dragRef.current = { startX: e.clientX, startW: width }
          document.body.style.cursor = 'col-resize'
          document.body.style.userSelect = 'none'
          e.preventDefault()
        }}
      />
      {/* header: which conversation, what it is about, which model, and
          the two shape controls. `clear` is gone — forgetting a
          conversation is the act on its own row. */}
      <div className="flex items-center gap-2 border-b border-edge px-3 py-2.5">
        {/* the console's own fold glyph (▸ closed, ▾ open — the shape
            every other fold on every other screen wears), one ink above
            the settled floor: a control the reader has to FIND is not
            chrome that has finished speaking (owner, 2026-09-06) */}
        <button
          className="cursor-pointer rounded-md px-1 text-[11px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
          onClick={() => setFoldOpen((o) => !o)}
          title="the conversations on this project"
          aria-expanded={foldOpen}
          aria-label="conversations"
        >
          {foldOpen ? '▾' : '▸'}
        </button>
        {/* the header names the CONVERSATION and nothing else. Which
            page the question is about is the address's job, and the
            panel already follows it — as a suffix here it was the same
            fact drawn twice, spending the title's room to do it. */}
        <span className="min-w-0 truncate text-[13px] font-medium text-ink" title={title}>
          {title}
        </span>
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          <ModelPicker
            // fixed width, and wide enough for the longest live name:
            // a trigger that hugs its current value makes the header
            // jiggle on every switch, and a narrow one wrapped
            // `claude-sonnet-5` onto two lines
            className="w-40 shrink-0"
            groups={groups}
            value={picked}
            onChange={setModel}
            onOpen={refreshModels}
            title="stronger models cost more of the same subscription quota"
          />
          <button
            className="cursor-pointer rounded-lg px-1.5 py-0.5 text-[12px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
            onClick={toggleWide}
            title={wide ? 'back to the narrow panel' : 'widen for reading'}
            aria-label="widen"
          >
            ⤢
          </button>
          <button
            className="cursor-pointer rounded-lg px-1.5 py-0.5 text-[13px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
            onClick={onClose}
            title="close (Esc; Ctrl+/ reopens)"
            aria-label="close chat"
          >
            ×
          </button>
        </div>
      </div>

      {wrongBackend && (
        <div className="border-b border-edge px-4 py-1.5 text-[11px] text-warn">
          start a new conversation to switch backends
        </div>
      )}

      {/* the conversations, IN PLACE under the header — do not float
          what the page can simply say (DESIGN.md) */}
      {foldOpen && (
        <SessionsFold
          sessions={sessions}
          currentId={sessionId}
          streaming={streaming}
          note={foldNote}
          onOpen={(id) => void openSession(id)}
          onNew={() => void newSession()}
          onRename={(id, t) => void renameSession(id, t)}
          onDelete={(id) => void deleteSession(id)}
          onClose={() => setFoldOpen(false)}
        />
      )}

      {/* transcript */}
      <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {turns.length === 0 && live === null ? (
          <div className="flex h-full flex-col justify-center gap-3 text-[12px] text-ink-faint">
            <p>
              ask about progress, a lemma, or how the machine works. it reads the workspace and
              answers with sources; when it prepares a command, nothing is queued until you
              confirm it.
            </p>
            {noMemory && <p>this backend keeps no conversation — each question is read fresh.</p>}
            <div className="space-y-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="block cursor-pointer rounded-lg border border-edge/60 px-2.5 py-1.5 text-left text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
                  onClick={() => {
                    setInput(s)
                    inputRef.current?.focus()
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            {older.length > 0 && (
              <div className="flex flex-wrap items-baseline gap-2">
                <span>or continue:</span>
                {older.map((s) => (
                  <button
                    key={s.id}
                    className="max-w-full cursor-pointer truncate text-ink-dim underline decoration-edge underline-offset-2 transition-colors hover:text-ink"
                    onClick={() => void openSession(s.id)}
                  >
                    {s.title || 'new conversation'}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div>
            {/* QPaper shape: the question is a full-width quiet card, the
                answer is bare prose under it — a document, not a chat app */}
            {turns.map((t, i) =>
              t.role === 'user' ? (
                <UserTurn
                  key={i}
                  text={t.text}
                  selected={selTurn === i}
                  editing={editing === i}
                  draft={editDraft}
                  canEdit={!streaming}
                  onSelect={() => setSelTurn(selTurn === i ? null : i)}
                  onEdit={() => {
                    setEditing(i)
                    setEditDraft(t.text)
                  }}
                  onDraft={setEditDraft}
                  onSubmit={() => {
                    const text = editDraft
                    setEditing(null)
                    void send(text, i)
                  }}
                  onCancel={() => setEditing(null)}
                />
              ) : (
                <div key={i} className="mt-2.5 text-[13px] leading-relaxed text-ink">
                  <Answer text={t.text} onReview={setReview} />
                  {/* what it did, folded into one line it can be opened
                      from — a turn with no tool calls draws nothing */}
                  <ActivityRows
                    rows={rowsFromRecord(t.tools)}
                    stage={null}
                    collapsed={!openTools.has(i)}
                    onToggle={() => toggleTools(i)}
                  />
                  {t.note && (
                    <div className="mt-1 text-[11px] text-ink-faint italic">— {t.note}</div>
                  )}
                </div>
              ),
            )}
            {live !== null && (
              <div className="mt-2.5 text-[13px] leading-relaxed text-ink">
                {/* live, the work reads top-down: what it is doing, then
                    what it has said so far */}
                <ActivityRows
                  rows={live.rows}
                  stage={live.stage}
                  collapsed={false}
                  onToggle={() => undefined}
                />
                {live.text !== '' && (
                  <div className="mt-1.5">
                    <Answer text={live.text} onReview={setReview} />
                  </div>
                )}
              </div>
            )}
            {noMemory && (
              <div className="mt-4 flex items-center gap-2 text-[10px] text-ink-faint">
                <span className="h-px flex-1 bg-edge" />
                this backend keeps no conversation — each question is read fresh
                <span className="h-px flex-1 bg-edge" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* composer — one pill, send lives inside it (QPaper shape) */}
      <div className="border-t border-edge px-3 py-2.5">
        {/* a standing condition, not an error: this backend's reads are
            bounded by your computer account, not by the workspace. it
            stays visible because it is true of every question asked
            here (engine: Tooling/llm/explainer.py read_scope) */}
        {unfencedReads && (
          <div className="mb-1.5 text-[11px] text-ink-faint italic">
            this backend cannot be scoped — it can read any file your computer account can read.
          </div>
        )}
        {unavailable && <div className="mb-1.5 text-[11px] text-warn">{unavailable}</div>}
        {note && <div className="mb-1.5 text-[11px] text-warn">{note}</div>}
        <div className="flex items-end gap-1.5 rounded-2xl border border-edge bg-bg px-1.5 py-1 transition-colors focus-within:border-ink-faint">
          <textarea
            ref={inputRef}
            value={input}
            rows={1}
            placeholder="ask anything…"
            className="max-h-40 min-w-0 flex-1 resize-none bg-transparent px-1.5 py-1 text-[13px] text-ink placeholder:text-ink-faint focus:outline-none"
            // grow with CONTENT, not just newlines — a long soft-wrapped
            // question scrolled invisibly inside a two-line box (QA)
            onInput={(e) => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = `${Math.min(el.scrollHeight, 160)}px`
            }}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                void send(input)
              }
            }}
          />
          {streaming ? (
            <button
              className="mb-0.5 flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded-full border border-edge text-ink transition-colors hover:bg-surface-2"
              onClick={stop}
              title="stop — whatever has streamed stays"
              aria-label="stop"
            >
              <span className="block h-2 w-2 rounded-[1px] bg-current" />
            </button>
          ) : (
            <button
              className="mb-0.5 flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-bg transition-colors enabled:bg-ink enabled:hover:bg-ink-dim disabled:cursor-default disabled:bg-surface-3 disabled:text-ink-faint"
              onClick={() => void send(input)}
              disabled={input.trim() === '' || unavailable !== null || wrongBackend}
              title="send (Enter)"
              aria-label="send"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                <path
                  d="M6 9.5v-7M3 5l3-2.7L9 5"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
      {review !== null && (
        <CommandConfirm
          problem={review.problem}
          kind={review.kind}
          payload={review.payload}
          label={review.problem}
          onClose={() => setReview(null)}
        />
      )}
    </aside>
  )
}
