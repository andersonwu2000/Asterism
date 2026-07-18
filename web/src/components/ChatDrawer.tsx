import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
}

type Page = { kind: string; name?: string }

/** What the user is looking at, from the route — frozen per send. */
function pageFromRoute(segments: string[]): Page {
  const s0 = segments[0] ?? ''
  if (s0 === 'problems' && segments[1]) return { kind: 'problem', name: segments[1] }
  if (s0 === 'library' && segments[1]) return { kind: 'library', name: segments[1] }
  if (s0 === 'library') return { kind: 'board' }
  if (s0 === 'engine' || s0 === 'run' || s0 === 'settings' || s0 === 'telemetry')
    return { kind: 'engine' }
  if (s0 === 'papers') return { kind: 'papers' }
  return { kind: 'board' }
}

function pageLabel(p: Page): string {
  if (p.kind === 'problem') return p.name ?? 'problem'
  if (p.kind === 'library') return `library · ${p.name ?? ''}`
  return p.kind
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
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [stage, setStage] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [model, setModel] = useState<string | null>(null)
  const [meta, setMeta] = useState<ChatState | null>(null)
  const [width, setWidth] = useState(380)
  const [confirmClear, setConfirmClear] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const streamingRef = useRef(false)

  useEffect(() => {
    apiGet<ChatState>('/api/chat/state')
      .then(setMeta)
      .catch(() => undefined)
  }, [])
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

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
      const page = pageFromRoute(route.segments) // frozen at send
      setNote(null)
      setConfirmClear(false)
      setInput('')
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
          body: JSON.stringify({ message: text, page, model }),
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

  const page = useMemo(() => pageFromRoute(route.segments), [route.segments])

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
        <span className="text-[13px] font-medium text-ink">ask</span>
        <span
          className="truncate text-[11px] text-ink-faint"
          title="questions are answered about this page; it can read the whole workspace — read-only, it explains, it never acts"
        >
          about {pageLabel(page)}
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
                <div key={i} className="mt-2.5 text-[13px] leading-relaxed text-ink-dim">
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
          </div>
        )}
      </div>

      {/* composer — one pill, send lives inside it (QPaper shape) */}
      <div className="border-t border-edge px-3 py-2.5">
        {note && <div className="mb-1.5 text-[11px] text-warn">{note}</div>}
        <div className="flex items-end gap-1.5 rounded-2xl border border-edge bg-bg px-1.5 py-1 transition-colors focus-within:border-ink-faint">
          <textarea
            ref={inputRef}
            value={input}
            rows={Math.min(6, Math.max(1, input.split('\n').length))}
            placeholder="ask anything…"
            className="min-w-0 flex-1 resize-none bg-transparent px-1.5 py-1 text-[13px] text-ink placeholder:text-ink-faint focus:outline-none"
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
              disabled={input.trim() === ''}
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
