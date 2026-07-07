import { useEffect, useRef, useState } from 'react'
import { apiPost } from '../lib/api'
import { Lean } from '../lib/lean'
import { LeanEditor } from './LeanEditor'

/*
 * The reader's Lean scratch pipeline, client side (POST /api/lean/eval).
 * Two consumers share it: the New page's authoring check (debounced
 * whole-buffer elaborate of Defs + Root) and the chapter's probe block
 * (a prefilled `#print axioms <decl>` the reader can edit and re-run).
 * `#check` / `#print` output arrives as severity-"information"
 * diagnostics — rendered as results, not as problems.
 */

export type EvalDiag = {
  line: number | null
  col: number | null
  severity: string
  message: string
}

export type EvalResult =
  | { status: 'warming'; phase?: string }
  | {
      status: 'ok'
      ok: boolean
      wall_sec: number
      parts: Record<string, EvalDiag[]>
      preamble: EvalDiag[]
    }

export function evalLean(
  parts: { id: string; code: string }[],
  imports: string[],
): Promise<EvalResult> {
  return apiPost<EvalResult>('/api/lean/eval', { parts, imports })
}

const isProblem = (d: EvalDiag) => d.severity === 'error' || d.severity === 'warning'

export function countErrors(diags: EvalDiag[] | undefined): number {
  return (diags ?? []).filter((d) => d.severity === 'error').length
}

/** Diagnostics under a code buffer: errors and warnings lead with a
 * glyph + line anchor; info output (the whole point of a probe) reads
 * as plain result text. Monochrome — severity is weight, not hue. */
export function DiagList({ diags }: { diags: EvalDiag[] }) {
  if (diags.length === 0) return null
  return (
    <div className="mt-1.5 flex flex-col gap-1">
      {diags.map((d, i) =>
        isProblem(d) ? (
          <div key={i} className="flex gap-2 font-mono text-[11px] leading-relaxed">
            <span
              className={d.severity === 'error' ? 'shrink-0 text-ink' : 'shrink-0 text-ink-faint'}
            >
              {d.severity === 'error' ? '✕' : '△'}
              {d.line != null ? ` L${d.line}` : ''}
            </span>
            <span
              className={
                'whitespace-pre-wrap ' + (d.severity === 'error' ? 'text-ink-dim' : 'text-ink-faint')
              }
            >
              {d.message}
            </span>
          </div>
        ) : (
          <pre
            key={i}
            className="overflow-x-auto rounded-md border border-edge bg-white/[0.02] px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink"
          >
            <Lean code={d.message} />
          </pre>
        ),
      )}
    </div>
  )
}

/** One probe block under a chapter declaration: prefilled
 * `#print axioms <fq>`, editable, ctrl/cmd-enter or Run. Runs once on
 * open — one click answers "which axioms does this stand on". */
export function LeanProbe({ fq, module }: { fq: string; module?: string }) {
  const [code, setCode] = useState(`#print axioms ${fq}`)
  const [phase, setPhase] = useState<'idle' | 'running' | 'warming'>('idle')
  const [out, setOut] = useState<{ diags: EvalDiag[]; wall: number } | null>(null)
  const seq = useRef(0)
  const retry = useRef<number | null>(null)
  const codeRef = useRef(code)
  codeRef.current = code

  const run = async () => {
    const my = ++seq.current
    if (retry.current != null) window.clearTimeout(retry.current)
    setPhase('running')
    try {
      const r = await evalLean(
        [{ id: 'probe', code: codeRef.current }],
        module ? [module] : [],
      )
      if (my !== seq.current) return
      if (r.status === 'warming') {
        setPhase('warming')
        retry.current = window.setTimeout(() => void run(), 5000)
        return
      }
      setOut({ diags: [...r.preamble, ...(r.parts.probe ?? [])], wall: r.wall_sec })
      setPhase('idle')
    } catch (e) {
      if (my !== seq.current) return
      setOut({
        diags: [
          {
            line: null,
            col: null,
            severity: 'error',
            message: String((e as Error).message),
          },
        ],
        wall: 0,
      })
      setPhase('idle')
    }
  }

  useEffect(() => {
    void run()
    return () => {
      seq.current++ // orphan any in-flight response
      if (retry.current != null) window.clearTimeout(retry.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="mt-2 ml-[22px] max-w-4xl">
      <div className="rounded-md border border-edge bg-white/[0.02]">
        <LeanEditor
          value={code}
          onChange={setCode}
          heightClass="min-h-16 h-auto field-sizing-content"
          frameless
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault()
              void run()
            }
          }}
        />
        <div className="flex items-center gap-3 border-t border-edge px-3 py-1.5">
          <span className="text-[10px] text-ink-faint">
            {phase === 'warming'
              ? 'engine warming — retries on its own (can take a minute)'
              : phase === 'running'
                ? 'running…'
                : out
                  ? `${out.wall.toFixed(1)}s`
                  : ''}
          </span>
          <button
            className="ml-auto cursor-pointer rounded border border-edge px-2.5 py-0.5 font-mono text-[11px] text-ink-dim transition-colors hover:border-edge-strong hover:text-ink disabled:cursor-default disabled:text-ink-faint"
            disabled={phase !== 'idle'}
            onClick={() => void run()}
            title="ctrl+enter"
          >
            ▸ run
          </button>
        </div>
      </div>
      {out && <DiagList diags={out.diags} />}
    </div>
  )
}
