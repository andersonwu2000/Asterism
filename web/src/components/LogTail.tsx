import { useEffect, useRef, useState } from 'react'

/** Live tail of the engine's event stream — the "what actually
 * happened" window when a run misbehaves. Collapsed by default where
 * it's mounted; the stream connects only while mounted+open. */
export default function LogTail() {
  const [lines, setLines] = useState<string[]>([])
  const boxRef = useRef<HTMLDivElement>(null)
  const stickBottom = useRef(true)

  useEffect(() => {
    const es = new EventSource('/api/events/stream')
    es.onmessage = (e) => {
      setLines((prev) => {
        const next = [...prev, e.data as string]
        return next.length > 500 ? next.slice(next.length - 500) : next
      })
    }
    return () => es.close()
  }, [])

  useEffect(() => {
    const el = boxRef.current
    if (el && stickBottom.current) el.scrollTop = el.scrollHeight
  }, [lines])

  // Empty panels collapse to one line — a 260px empty box conveys one
  // sentence (design review).
  if (lines.length === 0) {
    return (
      <div className="rounded-lg border border-edge bg-surface px-3 py-2 text-xs text-ink-faint">
        No log output yet — the tail picks up when a daemon run starts.
      </div>
    )
  }
  return (
    <div
      ref={boxRef}
      className="h-64 overflow-y-auto rounded-lg border border-edge bg-bg p-3"
      onScroll={(e) => {
        const el = e.currentTarget
        stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 30
      }}
    >
      <pre className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim">
        {/* an error line in routine gray is invisible (cold-eye: a
            swallowed-error line hid in plain sight) — failures carry
            the warn ink, line by line */}
        {lines.map((l, i) => {
          const bad = /\berror\b|\bfatal\b|traceback|swallowed|exception/i.test(l)
          return (
            <span key={i} className={bad ? 'text-warn' : undefined}>
              {l}
              {'\n'}
            </span>
          )
        })}
      </pre>
    </div>
  )
}
