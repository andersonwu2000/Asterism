import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { parseProjectRoute } from '../lib/projectRoute'
import { useRoute } from '../lib/router'
import { apiGet, apiPost } from '../lib/api'
import { renderProse } from '../lib/prose'
import { Select } from './ui'

/*
 * The explainer drawer — ask the engine to explain progress, code and
 * mechanics. Docked flex sibling (content reflows; nothing floats,
 * per the visual charter). READ-ONLY by construction: the backend
 * spawn has no write tools, and this panel never offers an action.
 *
 * Field-tested shapes borrowed from QPaper's chat panel (design SoT
 * docs/internal/chat_explainer_design.md "借鑑" section): page context
 * frozen at send, partial answers kept as first-class messages, send
 * button morphs to stop, failed sends roll the text back into the
 * input, citations are model-emitted tokens that ONLY the client
 * turns into navigation.
 */

interface ChatMsg {
  role: 'user' | 'assistant'
  text: string
  /** assistant-only trailing note: 'stopped' | error detail */
  note?: string
}

interface ChatState {
  busy: boolean
  has_session: boolean
  model_default: string
  models: string[]
  /* which backend answers, and the two ways one can be honestly worse
   * than another (engine SoT: Tooling/llm/explainer.py). Optional so an
   * older serve still renders. */
  provider?: string
  conversation_memory?: boolean
  read_scope?: 'workspace' | 'process'
  read_note?: string
  available?: boolean
  unavailable_detail?: string
}

type Page = { kind: string; name?: string }

/** What the reader is looking at, from the address — frozen per send.
 * Alongside it the drawer sends the Project (which binds the
 * conversation, §1.1-2) and the focus (the task open on that screen),
 * because a shell whose every page lives inside a Project would
 * otherwise hand every question the same workspace-wide overview. */
interface Where {
  page: Page
  project: string | null
  focus: { problem?: string } | null
}

function whereFromRoute(segments: string[]): Where {
  const r = parseProjectRoute(segments)
  if (r) {
    const focus = r.problem ? { problem: r.problem } : null
    if (r.section === 'engine')
      return { page: { kind: 'engine' }, project: r.project, focus }
    if (r.problem)
      return { page: { kind: 'problem', name: r.problem }, project: r.project, focus }
    return { page: { kind: 'board' }, project: r.project, focus: null }
  }
  const s0 = segments[0] ?? ''
  // the addresses that are not inside a Project
  if (s0 === 'problems' && segments[1])
    return { page: { kind: 'problem', name: segments[1] }, project: null, focus: null }
  if (s0 === 'papers') return { page: { kind: 'papers' }, project: null, focus: null }
  if (s0 === 'settings') return { page: { kind: 'engine' }, project: null, focus: null }
  return { page: { kind: 'board' }, project: null, focus: null }
}

function pageLabel(w: Where): string {
  if (w.page.kind === 'problem') return w.page.name ?? 'task'
  if (w.page.kind === 'board') return w.project ? `project · ${w.project}` : 'projects'
  return w.page.kind
}

// -- stream plumbing ---------------------------------------------------------
// (citations + markdown-lite live in lib/prose.tsx — shared with the
// Programme page)

const STAGE_LABEL: Record<string, string> = {
  context: 'gathering context…',
  thinking: 'thinking…',
  reading: 'reading the workspace…',
  retry: 'reconnecting…',
}

async function readSse(
  res: Response,
  onEvent: (ev: Record<string, unknown>) => void,
): Promise<void> {
  const reader = res.body?.getReader()
  if (!reader) throw new Error('no stream')
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    for (;;) {
      const nl = buf.indexOf('\n\n')
      if (nl < 0) break
      const frame = buf.slice(0, nl)
      buf = buf.slice(nl + 2)
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data: ')) continue
        try {
          onEvent(JSON.parse(line.slice(6)))
        } catch {
          /* partial or malformed frame — skip */
        }
      }
    }
  }
}

const SUGGESTIONS = [
  'Why is this problem stalled?',
  'What happened in the last few decisions?',
  'What exactly am I endorsing when I sign off?',
]

// -- the drawer --------------------------------------------------------------

// Transcript survives a refresh (QPaper lesson: they shipped storage
// persistence + restore after refresh bugs bit real users). Session-
// storage: per-tab, survives F5, dies with the tab — matching the
// design's "browser session survival" scope. Capped like QPaper's 50.
const STORE_KEY = 'asterism.chat.transcript'
const STORE_MAX = 50

function loadTranscript(): ChatMsg[] {
  try {
    const raw = sessionStorage.getItem(STORE_KEY)
    if (!raw) return []
    const v = JSON.parse(raw)
    return Array.isArray(v)
      ? v.filter((m) => m && typeof m.text === 'string' && (m.role === 'user' || m.role === 'assistant'))
      : []
  } catch {
    return []
  }
}

function saveTranscript(messages: ChatMsg[]): void {
  try {
    sessionStorage.setItem(STORE_KEY, JSON.stringify(messages.slice(-STORE_MAX)))
  } catch {
    /* quota / private mode — the transcript just won't survive */
  }
}

export default function ChatDrawer({
  open,
  onClose,
  onStreamingChange,
}: {
  open: boolean
  onClose: () => void
  onStreamingChange: (v: boolean) => void
}) {
  const route = useRoute()
  const [messages, setMessages] = useState<ChatMsg[]>(loadTranscript)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [stage, setStage] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  // the model choice persists (QA, 2026-07-20): it silently reverted
  // to the costlier default on every reload — a user who parked it on
  // haiku kept paying sonnet
  const [model, setModelState] = useState<string | null>(() => {
    try {
      return localStorage.getItem('asterism.chat.model')
    } catch {
      return null
    }
  })
  const setModel = (m: string) => {
    setModelState(m)
    try {
      localStorage.setItem('asterism.chat.model', m)
    } catch {
      /* private mode */
    }
  }
  const [meta, setMeta] = useState<ChatState | null>(null)
  const [width, setWidth] = useState(380)
  const [confirmClear, setConfirmClear] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const streamingRef = useRef(false)

  // restored transcript + a backend that forgot the session (serve
  // restart) = the display remembers, the engine doesn't; say so once
  const [engineForgot, setEngineForgot] = useState(false)
  useEffect(() => {
    apiGet<ChatState>('/api/chat/state')
      .then((s) => {
        setMeta(s)
        // a model stored while another provider was seated is not a
        // choice here — claude aliases and agy slugs share no
        // vocabulary, and sending one to the other is a hard error
        setModelState((m) => (m && !(s.models ?? []).includes(m) ? null : m))
        // "the engine forgot" is only news where the engine remembers
        if (s.conversation_memory !== false && !s.has_session && loadTranscript().length > 0)
          setEngineForgot(true)
      })
      .catch(() => undefined)
  }, [])
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  // persist: settled states normally, plus beforeunload so a refresh
  // mid-stream keeps the partial answer (first-class, like stop)
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  useEffect(() => {
    if (!streaming) saveTranscript(messages)
  }, [messages, streaming])
  useEffect(() => {
    const flush = () => saveTranscript(messagesRef.current)
    window.addEventListener('beforeunload', flush)
    return () => window.removeEventListener('beforeunload', flush)
  }, [])

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

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (text === '' || streamingRef.current) return
      const { page, project, focus } = whereFromRoute(route.segments) // frozen at send
      setNote(null)
      setConfirmClear(false)
      setInput('')
      if (inputRef.current) inputRef.current.style.height = 'auto'
      setMessages((m) => [...m, { role: 'user', text }, { role: 'assistant', text: '' }])
      setStage('context')
      setStreamingBoth(true)
      const ac = new AbortController()
      abortRef.current = ac
      const appendDelta = (t: string) =>
        setMessages((m) => {
          const out = m.slice()
          const last = out[out.length - 1]
          out[out.length - 1] = { ...last, text: last.text + t }
          return out
        })
      const rollback = (detail: string) => {
        // failed send → the question returns to the input box, no
        // orphan bubble pair
        setMessages((m) => m.slice(0, -2))
        setInput(text)
        setNote(detail)
      }
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, page, project, focus, model }),
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
        let sawDelta = false
        let finished = false
        await readSse(res, (ev) => {
          const t = ev.type
          if (t === 'delta' && typeof ev.text === 'string') {
            sawDelta = true
            setStage(null)
            appendDelta(ev.text)
          } else if (t === 'status' && typeof ev.stage === 'string') {
            setStage(ev.stage)
          } else if (t === 'done') {
            finished = true
            if (ev.ok !== false) setEngineForgot(false)
            if (ev.ok === false)
              setMessages((m) => {
                const out = m.slice()
                out[out.length - 1] = {
                  ...out[out.length - 1],
                  note: `the answer ended abnormally (${String(ev.subtype ?? '')})`,
                }
                return out
              })
          } else if (t === 'error') {
            finished = true
            const detail = String(ev.detail ?? 'unknown error')
            if (sawDelta) {
              setMessages((m) => {
                const out = m.slice()
                out[out.length - 1] = { ...out[out.length - 1], note: detail }
                return out
              })
            } else {
              rollback(detail)
            }
          }
        })
        if (!finished && !sawDelta) rollback('the stream ended before an answer arrived')
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          // partial answers are first-class: keep what streamed
          setMessages((m) => {
            const out = m.slice()
            const last = out[out.length - 1]
            if (last.text === '') return m.slice(0, -2)
            out[out.length - 1] = { ...last, note: 'stopped' }
            return out
          })
          setMessages((m) => (m.length > 0 && m[m.length - 1].text === '' ? m.slice(0, -1) : m))
        } else {
          rollback(`could not reach the engine (${(e as Error).message})`)
        }
      } finally {
        setStage(null)
        setStreamingBoth(false)
        abortRef.current = null
      }
    },
    [model, route.segments, setStreamingBoth],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const clear = useCallback(async () => {
    if (streamingRef.current) return
    try {
      await apiPost('/api/chat/clear')
      setMessages([])
      setNote(null)
      setEngineForgot(false)
      try {
        sessionStorage.removeItem(STORE_KEY)
      } catch {
        /* ignore */
      }
    } catch (e) {
      setNote(String((e as Error).message))
    }
    setConfirmClear(false)
  }, [])

  // width drag — clamped, not persisted
  const dragRef = useRef<{ startX: number; startW: number } | null>(null)
  useEffect(() => {
    const move = (e: MouseEvent) => {
      const d = dragRef.current
      if (!d) return
      const w = d.startW + (d.startX - e.clientX)
      setWidth(Math.min(Math.max(w, 300), Math.min(window.innerWidth * 0.6, 640)))
    }
    const up = () => {
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

  const where = useMemo(() => whereFromRoute(route.segments), [route.segments])

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

  // closed = hidden, not unmounted — the transcript survives the
  // close/open cycle (and a stream keeps writing into it)
  return (
    <aside
      className={`relative shrink-0 flex-col border-l border-edge bg-surface ${open ? 'flex' : 'hidden'}`}
      style={{ width }}
      aria-label="explainer chat"
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
      {/* header: what this is + model + clear (QPaper shape: the model
          picker is a first-class header control, not footer fine print) */}
      <div className="flex items-center gap-2 border-b border-edge px-4 py-2.5">
        {/* the Assistant's word (§1.1): the drawer keeps Ask's mark and
            its behaviour, and loses its name */}
        <span className="text-[13px] font-medium text-ink">assistant</span>
        <span
          className="truncate text-[11px] text-ink-faint"
          // the backend states its own reach — a fixed sentence here
          // described claude's fence on every provider
          title={
            meta?.read_note ??
            'questions are answered about this page; read-only, it explains, it never acts'
          }
        >
          about {pageLabel(where)}
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <Select
            // fixed width: a base-select trigger hugs its current
            // value, so an unsized one makes the header jiggle on
            // every model switch
            className="w-24 shrink-0"
            value={model ?? meta?.model_default ?? 'sonnet'}
            onChange={(e) => setModel(e.target.value)}
            title="stronger models cost more of the same subscription quota"
          >
            {(meta?.models ?? ['haiku', 'sonnet', 'opus']).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
          {messages.length > 0 &&
            (confirmClear ? (
              <button
                className="cursor-pointer rounded-lg border border-edge px-2 py-0.5 text-[11px] whitespace-nowrap text-warn transition-colors hover:bg-surface-2"
                onClick={() => void clear()}
                disabled={streaming}
              >
                confirm — forget this conversation
              </button>
            ) : (
              <button
                className="cursor-pointer rounded-lg px-2 py-0.5 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
                onClick={() => setConfirmClear(true)}
                disabled={streaming}
                title="forget the conversation, both here and on the engine side"
              >
                clear
              </button>
            ))}
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

      {/* transcript */}
      <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col justify-center gap-3 text-[12px] text-ink-faint">
            <p>
              ask about progress, a lemma, or how the machine works. it reads the workspace and
              answers with sources; it never acts.
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
          </div>
        ) : (
          <div>
            {/* QPaper shape: the question is a full-width quiet card, the
                answer is bare prose under it — a document, not a chat app */}
            {messages.map((m, i) =>
              m.role === 'user' ? (
                <div
                  key={i}
                  className="mt-5 rounded-xl bg-surface-2 px-3 py-2 text-[13px] whitespace-pre-wrap text-ink first:mt-0"
                >
                  {m.text}
                </div>
              ) : (
                <div key={i} className="mt-2.5 text-[13px] leading-relaxed text-ink">
                  {m.text === '' && streaming && i === messages.length - 1 ? (
                    <span className="text-[12px] text-ink-faint">
                      {STAGE_LABEL[stage ?? 'thinking'] ?? 'thinking…'}
                    </span>
                  ) : (
                    renderProse(m.text)
                  )}
                  {m.note && (
                    <div className="mt-1 text-[11px] text-ink-faint italic">— {m.note}</div>
                  )}
                </div>
              ),
            )}
            {/* one fact, one place: on a backend with no memory EVERY
                question is read fresh, which subsumes "the engine
                forgot this one conversation" */}
            {noMemory ? (
              <div className="mt-4 flex items-center gap-2 text-[10px] text-ink-faint">
                <span className="h-px flex-1 bg-edge" />
                this backend keeps no conversation — each question is read fresh
                <span className="h-px flex-1 bg-edge" />
              </div>
            ) : (
              engineForgot && (
                <div className="mt-4 flex items-center gap-2 text-[10px] text-ink-faint">
                  <span className="h-px flex-1 bg-edge" />
                  restored on this tab — the engine reads your next question fresh
                  <span className="h-px flex-1 bg-edge" />
                </div>
              )
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
              disabled={input.trim() === '' || unavailable !== null}
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
    </aside>
  )
}
