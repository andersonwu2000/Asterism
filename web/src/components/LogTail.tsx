import { useEffect, useRef, useState } from 'react'
import { frameClass } from '../lib/textFrame'

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
      <div className={frameClass({ frame: true, mono: false, tone: 'faint' })}>
        No log output yet — the tail picks up when a daemon run starts.
      </div>
    )
  }
  return (
    // ONE template for every block of text (DESIGN.md, 2026-08-27):
    // this file hand-wrote its own chrome — an opaque `bg-bg` slab that
    // assumes a host — while every other block recedes on `bg-wash`.
    <div
      ref={boxRef}
      className={frameClass({ frame: true, cap: 'lg', wrap: false, mono: false })}
      onScroll={(e) => {
        const el = e.currentTarget
        stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 30
      }}
    >
      <pre className={frameClass({ frame: false, wrap: false })}>
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
