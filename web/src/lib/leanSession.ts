import { useEffect, useRef, useState } from 'react'
import type { EvalDiag } from '../components/LeanProbe'

/*
 * The browser InfoView's transport: one WebSocket to
 * /api/lean/session = one interactive gateway session on the RESERVED
 * slot. Buffer changes debounce into "sync" (one elaborate; the
 * cursor's goal rides the response); caret moves debounce into
 * "cursor" (hot-slot goal query, no re-elaborate). Every message
 * carries seq; stale responses are dropped. Reconnects with backoff
 * while enabled — a gateway restart surfaces as one warming spell.
 */

export type LeanCursor = { part: string; line: number; col: number }

/**
 * What the engine is doing, in one sentence — ONE mapping, shared by
 * every surface that runs Lean (owner, 2026-08-27: the warm-up
 * produced different words in different boxes, because the probe and
 * the New page each kept their own copy of this ladder and had
 * drifted: "resumes on its own" vs "the check resumes on its own",
 * "connecting..." vs "connecting to the engine...", and the New page
 * had no `checking` case here at all, so a box went silent while a
 * separate verdict line spoke).
 *
 * Empty = the engine has nothing to say, which is the steady state.
 */
export function engineWord(s: {
  phase: LeanSessionState['phase']
  detail: string | null
}): string {
  switch (s.phase) {
    case 'dormant':
      return 'click into the editor to check — the Lean engine follows your cursor'
    case 'warming':
      return 'engine warming — the check resumes on its own (a cold start can take a minute)'
    case 'busy':
      return 'the engine editor slot is busy elsewhere — retrying'
    case 'connecting':
      return 'connecting to the engine…'
    case 'checking':
      return 'checking…'
    default:
      return s.detail ? `engine error: ${s.detail}` : ''
  }
}

export type LeanSessionState = {
  phase: 'idle' | 'connecting' | 'warming' | 'busy' | 'checking' | 'ready' | 'dormant'
  parts: Record<string, EvalDiag[]>
  preamble: EvalDiag[]
  goal: string | null
  note: string | null
  detail: string | null
}

/**
 * The diagnostics that belong to ONE box, and only those.
 *
 * `preamble` is the bin for output the engine could not place: serve's
 * `_map_diags` files anything with `line: null` there, and a `#check`
 * result arrives exactly that way (measured, 2026-08-27). Folding that
 * bin into a box makes the box claim the OTHER box's output — the New
 * page printed Root's `#check` above Defs before this was pinned down
 * (owner screenshot). Unplaceable output is the file's, and a surface
 * with more than one box renders it once, for the set.
 */
export function boxDiags(
  s: Pick<LeanSessionState, 'parts'>,
  part: string,
): EvalDiag[] {
  return s.parts[part] ?? []
}

const IDLE: LeanSessionState = {
  phase: 'idle', parts: {}, preamble: [], goal: null, note: null, detail: null,
}

export function useLeanSession(opts: {
  enabled: boolean
  /** whether this surface currently holds the single reserved slot;
   * enabled-but-inactive = paused (WS torn down, last result kept) */
  active?: boolean
  parts: { id: string; code: string }[]
  imports?: string[]
  cursor: LeanCursor | null
}): LeanSessionState {
  const { enabled, cursor, active = true } = opts
  const [state, setState] = useState<LeanSessionState>(IDLE)
  const ws = useRef<WebSocket | null>(null)
  const seq = useRef(0)
  const lastSyncSeq = useRef(0)
  const retry = useRef<number | null>(null)
  const optsRef = useRef(opts)
  optsRef.current = opts

  const partsKey = opts.parts.map((p) => p.id + ' ' + p.code).join('\n')
  const cursorKey = cursor ? `${cursor.part}:${cursor.line}:${cursor.col}` : ''

  const sendSync = () => {
    const sock = ws.current
    if (!sock || sock.readyState !== WebSocket.OPEN) return
    const o = optsRef.current
    const live = o.parts.filter((p) => p.code.trim() !== '')
    const my = ++seq.current
    lastSyncSeq.current = my
    if (live.length === 0) {
      setState((s) => ({ ...s, phase: 'ready', parts: {}, preamble: [], goal: null }))
      return
    }
    // a warming/busy spell re-syncs every few seconds to poll the
    // gateway; don't flash 'checking' each time — that made a long cold
    // start read as a broken checking<->warming flicker. Keep the steady
    // status until a real response (state / warming / busy) arrives.
    setState((s) => (s.phase === 'warming' || s.phase === 'busy' ? s : { ...s, phase: 'checking' }))
    sock.send(
      JSON.stringify({
        type: 'sync', seq: my, parts: live, imports: o.imports ?? [],
        cursor: o.cursor ?? undefined,
      }),
    )
  }

  // connection lifecycle — reconnect with backoff while enabled AND
  // active (this surface holds the reserved slot). Enabled-but-inactive
  // is a pause: the prior run's cleanup tears the WS down (releasing the
  // slot), and we keep the last result on screen marked 'dormant' until
  // the user comes back to this surface.
  useEffect(() => {
    if (!enabled) {
      setState(IDLE)
      return
    }
    if (!active) {
      setState((s) => ({ ...s, phase: 'dormant' }))
      return
    }
    let closed = false
    let backoff = 1000
    const connect = () => {
      if (closed) return
      setState((s) => ({ ...s, phase: 'connecting' }))
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const sock = new WebSocket(`${proto}://${location.host}/api/lean/session`)
      ws.current = sock
      sock.onopen = () => {
        backoff = 1000
        sendSync()
      }
      sock.onmessage = (ev) => {
        const m = JSON.parse(ev.data as string)
        if (typeof m.seq === 'number' && m.seq < lastSyncSeq.current && m.type !== 'goal') return
        if (m.type === 'state') {
          // a real result landed — cancel any pending warming/busy retry
          // so it can't fire a spurious re-sync (and re-flash) after ready
          if (retry.current != null) { window.clearTimeout(retry.current); retry.current = null }
          setState({
            phase: 'ready', parts: m.parts ?? {}, preamble: m.preamble ?? [],
            goal: m.goal ?? null, note: m.note ?? null, detail: null,
          })
        } else if (m.type === 'goal') {
          setState((s) => ({ ...s, goal: m.goal ?? null, note: m.note ?? null }))
        } else if (m.type === 'warming') {
          setState((s) => ({ ...s, phase: 'warming' }))
          if (retry.current != null) window.clearTimeout(retry.current)
          retry.current = window.setTimeout(sendSync, 5000)
        } else if (m.type === 'busy') {
          setState((s) => ({ ...s, phase: 'busy', detail: m.detail ?? null }))
          if (retry.current != null) window.clearTimeout(retry.current)
          retry.current = window.setTimeout(sendSync, 8000)
        } else if (m.type === 'error') {
          setState((s) => ({ ...s, phase: 'ready', detail: m.detail ?? null }))
        }
      }
      sock.onclose = () => {
        ws.current = null
        if (closed) return
        setState((s) => ({ ...s, phase: 'connecting' }))
        window.setTimeout(connect, backoff)
        backoff = Math.min(backoff * 2, 10000)
      }
      sock.onerror = () => sock.close()
    }
    connect()
    return () => {
      closed = true
      if (retry.current != null) window.clearTimeout(retry.current)
      ws.current?.close()
      ws.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, active])

  // buffer changes → debounced sync
  useEffect(() => {
    if (!enabled) return
    const t = window.setTimeout(sendSync, 800)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partsKey, enabled])

  // caret moves → debounced cursor-only goal query
  useEffect(() => {
    if (!enabled || !cursor) return
    const t = window.setTimeout(() => {
      const sock = ws.current
      if (!sock || sock.readyState !== WebSocket.OPEN) return
      sock.send(JSON.stringify({ type: 'cursor', seq: ++seq.current, cursor }))
    }, 250)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursorKey, enabled])

  return state
}

/** 1-indexed line / 0-indexed col of a textarea's caret. */
export function caretLineCol(el: HTMLTextAreaElement): { line: number; col: number } {
  const upto = el.value.slice(0, el.selectionStart ?? 0)
  const lines = upto.split('\n')
  return { line: lines.length, col: lines[lines.length - 1].length }
}
