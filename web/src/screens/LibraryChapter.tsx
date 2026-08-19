import { useMemo, useState } from 'react'
import { usePoll } from '../lib/api'
import { leafOf, moduleOf, relTime } from '../lib/format'
import { Link } from '../lib/router'
import { ErrorState, TabNav } from '../components/ui'
import { Lean } from '../lib/lean'
import { renderInline } from '../lib/prose'
import { LeanProbe } from '../components/LeanProbe'
import { CameraControls, useSkyCamera } from '../lib/camera'
import { citePath } from '../lib/sky'
import { DEF_KINDS } from '../lib/vocab'
import { layoutConstellation } from '../lib/layout'
import type { Goal, LibraryChapter, LibraryChapterDecl, LibraryChapterFile } from '../lib/types'

/*
 * Library chapter — one harvested problem, read for humans. Nobody
 * needs all N declarations at once (owner): the landing view is the
 * short list worth reading — claims where the flag survives, plus the
 * keystones the other modules demonstrably reach for, plus the
 * vocabulary. The full text stays browsable one module at a time, and
 * a small sky draws the modules' import structure. The engine record
 * (goals, attempts) lives on the problem page — one link away.
 */

type Tab = 'highlights' | 'map' | 'modules'


/** Docstring markdown-lite: paragraphs, `code` spans, # headings,
 * `- ` bullets, *emphasis*. Lean's unicode IS the math — no TeX pass. */
function Prose({ text, className = '' }: { text: string; className?: string }) {
  const blocks = text
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter(Boolean)
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {blocks.map((b, i) => {
        const heading = b.match(/^(#{1,4})\s+(.*)$/)
        if (heading && !heading[2].includes('\n')) {
          return (
            <div
              key={i}
              className="mt-1 text-[11px] font-medium tracking-[0.14em] text-ink-dim uppercase"
            >
              {renderSpans(heading[2])}
            </div>
          )
        }
        if (/^[-*]\s/.test(b)) {
          const items = b.split(/\n(?=[-*]\s)/).map((li) => li.replace(/^[-*]\s+/, ''))
          return (
            <ul key={i} className="flex list-disc flex-col gap-1 pl-5">
              {items.map((li, j) => (
                <li key={j}>{renderSpans(li.replace(/\n\s*/g, ' '))}</li>
              ))}
            </ul>
          )
        }
        return <p key={i}>{renderSpans(b.replace(/\n\s*/g, ' '))}</p>
      })}
    </div>
  )
}

// inline layer = the ONE shared pipeline (lib/prose.tsx): lean-coloured
// `code` spans, $math$ via KaTeX (raw dollar-LaTeX read as broken to
// the professor audience — cold-eye + owner, 2026-07-13), **bold** and
// *emphasis*. Only the compact block shell above stays local — a
// docstring card is not a reading page.
function renderSpans(s: string) {
  return renderInline(s, 's')
}

/** The resting statement, for humans: short name + explicit `(...)`
 * binders + conclusion. Universe annotations, `{implicit}` and
 * `[instance]` binder walls drop (licensed to be non-Lean); the run
 * state's `#check @fq` shows the full kernel truth on demand. */
function conciseSignature(sig: string, short: string): string {
  const OPEN = '({[⦃⟨'
  const CLOSE = ')}]⦄⟩'
  let depth = 0
  let k = 0
  // skip the head token (fq name, possibly `.{u_1, u_2}`-annotated)
  while (k < sig.length) {
    const ch = sig[k]
    if (OPEN.includes(ch)) depth++
    else if (CLOSE.includes(ch)) depth--
    else if (depth === 0 && /\s/.test(ch)) break
    k++
  }
  const parts: string[] = [short]
  let seg = ''
  let dropping = false
  for (let i = k; i < sig.length; i++) {
    const ch = sig[i]
    if (depth === 0) {
      if (ch === ':' && sig[i + 1] !== '=') {
        parts.push(sig.slice(i).replace(/\s+/g, ' ').trim())
        return shortenLibraryNames(parts.join(' '))
      }
      if ('{[⦃'.includes(ch)) {
        dropping = true
        depth++
        continue
      }
      if (ch === '(') {
        depth++
        seg = '('
        continue
      }
      continue // stray depth-0 text (keywords, source-form names)
    }
    if (OPEN.includes(ch)) depth++
    else if (CLOSE.includes(ch)) depth--
    if (!dropping) seg += ch
    if (depth === 0) {
      if (!dropping && seg) {
        parts.push(seg.replace(/\s+/g, ' '))
        seg = ''
      }
      dropping = false
    }
  }
  return shortenLibraryNames(parts.join(' '))
}

/** `Library.….lastComponent` → `lastComponent` inside the concise
 * rendering — chapter-local names cite themselves short. */
function shortenLibraryNames(s: string): string {
  return s.replace(/\bLibrary(?:\.[A-Za-z0-9_'₀-₉]+)*\.([A-Za-z0-9_'₀-₉]+)/g, '$1')
}

/** The run state's editor content: the decl's REAL source (proof
 * included — rewrite it, the axioms check below answers for YOUR
 * version), opened in its namespace so sibling references resolve.
 * Decls whose source the scan missed fall back to a #check probe. */
function probeSeed(d: LibraryChapterDecl & { file?: string }, short: string): string {
  const fq = d.name ?? d.slug
  if (d.source) {
    const ns = fq.includes('.') ? fq.slice(0, fq.lastIndexOf('.')) : null
    // `_root_.` pins the axioms check to the buffer's own top-level
    // redefinition — with the namespace open, the bare name is
    // ambiguous against the Library original and #print answers BOTH.
    // The module context (opens + the variable block carrying the
    // instance hypotheses) comes along: without it the source is not
    // self-contained — autoImplicit rebinds the variables as naked
    // Types and the probe drowns in "failed to synthesize" (owner
    // report, 2026-07-18)
    return (
      (ns ? `open ${ns}\n\n` : '') +
      (d.context ? d.context + '\n\n' : '') +
      d.source +
      `\n\n#print axioms ${ns ? '_root_.' : ''}${short}`
    )
  }
  return `#check @${fq}\n\n#print axioms ${fq}`
}

function DeclEntry({
  d,
  module,
  onOpenModule,
}: {
  d: LibraryChapterDecl & { file?: string }
  module: string
  /** highlights entries carry a "where it lives" jump */
  onOpenModule?: (path: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const [probing, setProbing] = useState(false)
  const short = (d.name ?? d.slug).split('.').pop() ?? d.slug
  const isDef = DEF_KINDS.has(d.decl_kind ?? '')
  const copy = (withImport: boolean) => {
    const name = d.name ?? d.slug
    void navigator.clipboard
      .writeText(withImport ? `import ${module}\n-- ${name}` : name)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
  }
  return (
    <div className="group">
      <div className="flex items-baseline gap-2.5">
        {/* the sky's glyphs carry over: diamond = meaning-bearer (def),
            round = proposition */}
        <svg width="10" height="10" viewBox="-5 -5 10 10" className="shrink-0 self-center">
          <title>{isDef ? 'definition — carries meaning' : 'proposition'}{d.decl_kind ? ` (${d.decl_kind})` : ''}</title>
          {isDef ? (
            <rect
              x="-3"
              y="-3"
              width="6"
              height="6"
              transform="rotate(45)"
              fill="var(--color-starlight)"
              opacity="0.9"
            />
          ) : (
            <circle r="3" fill="var(--color-starlight)" opacity="0.85" />
          )}
        </svg>
        <button
          className="cursor-pointer font-mono text-[13px] text-ink transition-colors hover:text-starlight"
          onClick={(e) => copy(e.shiftKey)}
          title={`${d.name ?? d.slug}\nclick: copy name · shift-click: copy with import`}
        >
          {short}
        </button>

        {d.is_deliverable && (
          <span
            className="text-[10px] tracking-wide text-star"
            title="a result the problem's goal asked for — accepted at sign-off"
          >
            main result
          </span>
        )}
        {d.used_by > 0 && (
          <span
            className="tnum text-[10px] text-ink-faint"
            title={`referenced in ${d.used_by} other module${d.used_by === 1 ? '' : 's'} of this chapter`}
          >
            used in {d.used_by}
          </span>
        )}
        {copied && <span className="text-[10px] text-ink-faint">copied</span>}
        {onOpenModule && d.file && (
          <button
            className="ml-auto cursor-pointer font-mono text-[10px] text-ink-faint transition-colors hover:text-ink"
            onClick={() => onOpenModule(d.file!)}
            title="read it in its module"
          >
            {leafOf(d.file)} →
          </button>
        )}
      </div>
      {d.doc && (
        <Prose
          text={d.doc}
          className="mt-1.5 ml-[22px] max-w-[76ch] text-[13px] leading-relaxed text-ink-dim"
        />
      )}
      {d.signature && !probing && (
        <div className="group/sig relative mt-2 ml-[22px] max-w-4xl">
          <pre
            className="overflow-x-auto rounded-lg border border-edge bg-wash px-3.5 py-2.5 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink"
            title={d.signature}
          >
            <Lean code={conciseSignature(d.signature, short)} declHead />
          </pre>
          <button
            className="absolute right-2 bottom-2 cursor-pointer rounded-md border border-edge bg-surface px-2.5 py-0.5 font-mono text-[11px] text-ink-dim opacity-0 transition-opacity group-hover/sig:opacity-100 hover:border-edge-strong hover:text-ink"
            onClick={() => setProbing(true)}
            title="expand into runnable Lean — full type via #check, axioms below, edit freely"
          >
            ▸ run
          </button>
        </div>
      )}
      {probing && (
        <LeanProbe
          fq={d.name ?? d.slug}
          module={module}
          seed={probeSeed(d, short)}
          onClose={() => setProbing(false)}
        />
      )}
    </div>
  )
}

/** One module, fully read: docstring prose + every decl in source
 * order. The only place the whole text unrolls — one file at a time. */
function ModuleReading({ f }: { f: LibraryChapterFile }) {
  const mod = moduleOf(f.path)
  return (
    <div>
      <div className="flex items-baseline gap-3 border-b border-edge pb-2">
        <h2 className="font-display text-[18px] text-ink">{leafOf(f.path)}</h2>
        <span className="truncate font-mono text-[11px] text-ink-faint" title={f.path}>
          {mod}
        </span>
        <span className="tnum ml-auto text-[11px] text-ink-faint">{f.decls.length}</span>
      </div>
      {f.module_doc && (
        <Prose
          text={f.module_doc}
          className="mt-3 max-w-[76ch] text-[13px] leading-relaxed text-ink-dim"
        />
      )}
      <div className="mt-5 flex flex-col gap-7">
        {f.decls.map((d) => (
          <DeclEntry key={d.slug} d={d} module={mod} />
        ))}
      </div>
    </div>
  )
}

/** The file-level sky: modules as stars, import edges as lines —
 * structure the decl scatter never had (owner's redirection). */
function ModuleMap({
  files,
  onOpen,
}: {
  files: LibraryChapterFile[]
  onOpen: (path: string) => void
}) {
  const layout = useMemo(() => {
    // The problem sky's engine, borrowed whole (its barycenter-lite
    // predecessor read visibly weaker — owner, 2026-07-09): modules
    // pose as goals, imports as anchor edges, and layoutConstellation
    // brings the full treatment — tidy trees, the crossing/length
    // objective, plate + occupancy laws. Orientation follows the
    // problem sky's convention: the importer (the result) sits on
    // top, what it imports (its vocabulary) supports from below.
    const idOf = new Map(files.map((f, i) => [f.path, i + 1]))
    const pathOf = new Map(files.map((f, i) => [i + 1, f.path]))
    const goals = files.map(
      (f, i) =>
        ({
          id: i + 1,
          slug: f.path,
          status: 'proved',
          kind: '',
          origin: 'forward',
          depth: 0,
          detached: false,
          alias_target_id: null,
          is_deliverable: f.decls.some((d) => d.is_deliverable),
          statement: '',
          lean_path: f.path,
          created_at: '',
          attempts: 0,
          dead_attempts: 0,
          in_flight: false,
        }) as Goal,
    )
    // anchor edge = {from: dependency, to: claim}; the engine flips it
    // so the claim is the parent — importer above, imported beneath
    const anchors = files.flatMap((f) =>
      f.imports_within
        .filter((p) => idOf.has(p))
        .map((imp) => ({ from: idOf.get(imp)!, to: idOf.get(f.path)! })),
    )
    const v = layoutConstellation(goals, [], [], anchors, [])
    // native engine coordinates — the shared camera owns all scaling
    // (the old static x-squish distorted the geometry the engine had
    // just optimised, and scaled nothing else the way the problem sky
    // does)
    const pos = new Map<string, { x: number; y: number }>()
    for (const n of v.nodes) {
      const path = pathOf.get(n.goal.id)
      if (path) pos.set(path, { x: n.x, y: n.y })
    }
    return { pos, width: v.width, height: v.height }
  }, [files])

  // small maps magnify generously, like the problem sky (10 stars in
  // a void read as a failed page load)
  const cam = useSkyCamera(layout.width, layout.height, {
    kMax: files.length <= 10 ? 2.6 : 2.0,
  })
  const k = cam.view?.k ?? 1
  // label truncation + collision rows are sized at the FIT zoom and
  // held there: labels render screen-constant, so what collides
  // depends on k — computing at fit keeps rows stable under the
  // user's wheel instead of reshuffling every frame
  const labelPlan = useMemo(() => {
    const fk = Math.max(cam.fitK, 0.05)
    const cap = Math.max(12, Math.floor((110 * fk * 1.9) / 6.6))
    const labelW = (p: string) => (Math.min(leafOf(p).length, cap) * 6.6) / fk
    // collision-driven label rows: walk each pixel row in x order and
    // drop a label to the lower row only when the upper row's last
    // label would actually touch it (parity alone missed near-misses
    // in narrow layers)
    const rows = new Map<number, string[]>()
    for (const [p, q] of layout.pos) rows.set(q.y, [...(rows.get(q.y) ?? []), p])
    const stagger = new Map<string, number>()
    for (const l of rows.values()) {
      l.sort((a, b) => layout.pos.get(a)!.x - layout.pos.get(b)!.x)
      const rightEdge = [-Infinity, -Infinity]
      for (const p of l) {
        const cx = layout.pos.get(p)!.x
        const w = labelW(p)
        const row = cx - w / 2 > rightEdge[0] + 26 / fk ? 0 : 1
        stagger.set(p, row)
        rightEdge[row] = Math.max(rightEdge[row], cx + w / 2)
      }
    }
    return { cap, stagger }
  }, [layout, cam.fitK])

  const [hover, setHover] = useState<string | null>(null)
  return (
    <div
      ref={cam.containerRef}
      className="relative h-[calc(100vh-240px)] min-h-[420px] touch-none overflow-hidden"
      onPointerDown={cam.onPointerDown}
      onPointerMove={cam.onPointerMove}
      onPointerUp={cam.onPointerUp}
    >
      <svg className="block h-full w-full cursor-grab active:cursor-grabbing">
        <g transform={`translate(${cam.view?.tx ?? 0},${cam.view?.ty ?? 0}) scale(${k})`}>
        {files.flatMap((f) =>
          f.imports_within.map((imp, ei) => {
            const a = layout.pos.get(imp)
            const b = layout.pos.get(f.path)
            if (!a || !b) return null
            const lit = hover === f.path || hover === imp
            const opacity = hover === null ? 0.3 : lit ? 0.65 : 0.08
            const span = Math.abs(b.y - a.y)
            // an edge that skips layers bows around the rows between,
            // instead of drawing through their stars
            if (span > 130) {
              // the problem sky's bow, verbatim (index parity
              // separates parallel threads)
              return (
                <path
                  key={`${f.path}<${imp}`}
                  d={citePath(a, b, ei, 0).d}
                  fill="none"
                  stroke="var(--color-starlight)"
                  strokeWidth={1 / k}
                  strokeOpacity={opacity}
                />
              )
            }
            return (
              <line
                key={`${f.path}<${imp}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="var(--color-starlight)"
                strokeWidth={1 / k}
                strokeOpacity={opacity}
              />
            )
          }),
        )}
        {files.map((f) => {
          const p = layout.pos.get(f.path)
          if (!p) return null
          const r = 5 + Math.sqrt(f.decls.length) * 1.6
          const mains = f.decls.filter((d) => d.is_deliverable).length
          // labels are screen-constant (the problem sky's rule): gaps
          // and font divide by k so text neither balloons at fit nor
          // vanishes zoomed out
          return (
            <g
              key={f.path}
              transform={`translate(${p.x},${p.y})`}
              className="cursor-pointer"
              onMouseEnter={() => setHover(f.path)}
              onMouseLeave={() => setHover(null)}
              onClick={() => {
                if (!cam.dragMovedRef.current) onOpen(f.path)
              }}
            >
              <circle
                r={r}
                fill="var(--color-star)"
                stroke="var(--color-starlight)"
                strokeWidth={1.2}
                opacity={hover === null || hover === f.path ? 1 : 0.55}
              />
              {mains > 0 && (
                <circle
                  r={r + 4}
                  fill="none"
                  stroke="var(--color-star)"
                  strokeWidth={1}
                  opacity={0.9}
                />
              )}
              <title>{`${moduleOf(f.path)} — ${f.decls.length} declarations${mains > 0 ? `, ${mains} main` : ''}`}</title>
              <text
                y={r + (16 + (labelPlan.stagger.get(f.path) ?? 0) * 15) / k}
                textAnchor="middle"
                className="pointer-events-none select-none"
                fill={hover === f.path ? 'var(--color-ink)' : 'var(--color-ink-dim)'}
                fontSize={11 / k}
                fontFamily="var(--font-mono)"
              >
                {(() => {
                  const s = leafOf(f.path)
                  const cap = labelPlan.cap
                  return s.length > cap
                    ? `${s.slice(0, Math.floor(cap / 2) - 1)}…${s.slice(-(Math.floor(cap / 2) - 1))}`
                    : s
                })()}
              </text>
              <text
                y={r + (29 + (labelPlan.stagger.get(f.path) ?? 0) * 15) / k}
                textAnchor="middle"
                className="tnum pointer-events-none select-none"
                fill="var(--color-ink-faint)"
                fontSize={9 / k}
              >
                {f.decls.length}
              </text>
            </g>
          )
        })}
        </g>
      </svg>
      <p className="pointer-events-none absolute inset-x-0 bottom-2 text-center text-[11px] text-ink-faint">
        modules and their imports — ringed stars hold main results; click one to read it
      </p>
      <CameraControls zoomBy={cam.zoomBy} refit={cam.refit} />
    </div>
  )
}

function HighlightSection({
  title,
  hint,
  hintTitle,
  decls,
  onOpenModule,
}: {
  title: string
  hint?: string
  /** tooltip on the hint — where the engine vocabulary lives */
  hintTitle?: string
  decls: (LibraryChapterDecl & { file: string })[]
  onOpenModule: (path: string) => void
}) {
  if (decls.length === 0) return null
  return (
    <section className="mt-8">
      <div className="mb-4 border-b border-edge pb-2 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
        {title}
        {hint && (
          <span
            className="ml-3 font-normal tracking-normal normal-case text-ink-faint/80"
            title={hintTitle}
          >
            {hint}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-7">
        {decls.map((d) => (
          <DeclEntry key={d.slug} d={d} module={moduleOf(d.file)} onOpenModule={onOpenModule} />
        ))}
      </div>
    </section>
  )
}

export default function LibraryChapterScreen({ problem }: { problem: string }) {
  const { data, error, loading } = usePoll<LibraryChapter>(
    `/api/library/${encodeURIComponent(problem)}`,
    30000,
  )
  const [tab, setTab] = useState<Tab>('highlights')
  const [activeFile, setActiveFile] = useState<string | null>(null)

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const ns = problem.includes('.') ? problem.slice(0, problem.indexOf('.')) : null
  const leaf = ns ? problem.slice(ns.length + 1) : problem
  const declCount = data.files.reduce((s, f) => s + f.decls.length, 0)

  const all = data.files.flatMap((f) => f.decls.map((d) => ({ ...d, file: f.path })))
  const mains = all.filter((d) => d.is_deliverable)
  // ingest weakens the claim flags (old harvests never had them):
  // when none survive, the results other modules reach for stand in
  const leadIsVouched = mains.length > 0
  const lead = leadIsVouched
    ? mains
    : all
        .filter((d) => !DEF_KINDS.has(d.decl_kind ?? '') && d.used_by >= 1)
        .sort((a, b) => b.used_by - a.used_by)
        .slice(0, 6)
  const leadSet = new Set(lead.map((d) => d.slug))
  const vocab = all
    .filter((d) => DEF_KINDS.has(d.decl_kind ?? '') && !leadSet.has(d.slug))
    .sort((a, b) => b.used_by - a.used_by)
    .slice(0, 12)
  const vocabTotal = all.filter(
    (d) => DEF_KINDS.has(d.decl_kind ?? '') && !leadSet.has(d.slug),
  ).length
  const keystones = all
    .filter(
      (d) => !leadSet.has(d.slug) && !DEF_KINDS.has(d.decl_kind ?? '') && d.used_by >= 1,
    )
    .sort((a, b) => b.used_by - a.used_by)
    .slice(0, 8)

  const openModule = (path: string) => {
    setActiveFile(path)
    setTab('modules')
  }
  const active = data.files.find((f) => f.path === activeFile) ?? data.files[0]

  const tabs: { id: Tab; label: string }[] = [
    { id: 'highlights', label: 'Highlights' },
    { id: 'map', label: 'Map' },
    { id: 'modules', label: `Modules (${data.files.length})` },
  ]

  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <Link to="/library" className="text-xs text-ink-faint transition-colors hover:text-ink">
        ‹ library
      </Link>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        {ns && <span className="font-mono text-xs text-ink-faint">{ns}.</span>}
        <h1 className="font-display text-[26px] font-medium text-ink">{leaf}</h1>
        <span className="tnum text-xs text-ink-faint">
          {declCount} declarations · {data.files.length} module
          {data.files.length === 1 ? '' : 's'}
          {data.bridged_at && <> · entered the Library {relTime(data.bridged_at)}</>}
        </span>
        {/* THE signature — the one human act in a machine-built
            chapter deserves the ink of a visible seal, not a clause
            buried in the counts line (owner, 2026-07-14) */}
        {data.signoff?.name && (
          <span
            className={`ml-auto rounded-lg border px-3 py-1 text-right ${
              data.signoff.seal_ok ? 'border-edge' : 'border-warn/50'
            }`}
            title={`signed ${data.signoff.at}${
              data.signoff.evidence?.claude_email
                ? ` while logged in as ${data.signoff.evidence.claude_email}`
                : ''
            } on ${data.signoff.evidence?.host ?? '?'} (${
              data.signoff.evidence?.os_user ?? '?'
            })${
              data.signoff.seal_ok
                ? ' — seal intact: the reviewed content is exactly what was signed'
                : ' — the content changed AFTER the human signed; re-review and re-sign'
            }`}
          >
            <span className="block text-[9px] tracking-[0.18em] text-ink-faint uppercase">
              signed
            </span>
            <span className="font-display block text-sm leading-tight text-ink">
              {data.signoff.name}
            </span>
            <span className="tnum block text-[10px] text-ink-faint">
              {String(data.signoff.at).slice(0, 10)}
              {data.signoff.seal_ok ? (
                ' · seal intact'
              ) : (
                <span className="text-warn"> · changed since signing</span>
              )}
            </span>
          </span>
        )}
        {/* trust colophon (design round): what a mathematician asks a
            machine-built chapter first — which axioms, any sorry —
            answered from the gates' recorded guarantees. Per-decl
            live proof stays one click away (▸ run → #print axioms). */}
        {/* policy + a live check, NOT a stored historical claim: some
            chapters predate the universal axiom gate, and a colophon
            must never assert a passage it can't point to (self-audit,
            2026-07-14) */}
        {data.colophon && data.colophon.axioms.length > 0 && (
          <span
            className="w-full font-mono text-[11px] text-ink-faint"
            title="sorry is rejected at every gate; this axiom whitelist is enforced at proving and harvest. For the kernel's own word on any declaration: hover its statement and press ▸ run — a live re-check (#print axioms), not a stored claim."
          >
            axiom whitelist {'{'}{data.colophon.axioms.join(', ')}{'}'} · sorry rejected at every gate
          </span>
        )}
        <Link
          to={`/problems/${encodeURIComponent(problem)}`}
          className="ml-auto text-xs text-ink-faint underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
          title="the working record: goals, attempts, timeline"
        >
          engine record →
        </Link>
      </div>

      <TabNav className="mt-4" tabs={tabs} active={tab} onSelect={setTab} />

      {tab === 'highlights' && (
        <div>
          {/* the chapter's arc in one line — you can't open with the
              main theorem (its statement needs the definitions), but
              you can promise where the reading leads (owner,
              2026-07-14) */}
          {lead.length > 0 && (
            <p className="mt-4 text-xs text-ink-faint">
              {vocabTotal > 0
                ? `${vocabTotal} definition${vocabTotal === 1 ? '' : 's'} build toward `
                : 'this chapter builds toward '}
              {lead.slice(0, 3).map((d, i) => (
                <span key={d.slug}>
                  {i > 0 && ', '}
                  <button
                    className="cursor-pointer font-mono text-ink-dim underline decoration-edge-strong decoration-dotted underline-offset-2 hover:text-ink"
                    onClick={() => openModule(d.file)}
                  >
                    {d.slug}
                  </button>
                </span>
              ))}
              {lead.length > 3 && ` and ${lead.length - 3} more`}
              {' — definitions first, then what they carry.'}
            </p>
          )}
          {/* the chapter OPENS with its theorem (first-time QA: a
              mathematician searched this chapter and never met the
              main statement — old harvests lost their claim flags and
              Highlights was all vocabulary + plumbing) */}
          {data.root && (
            <div className="mt-5">
              <div className="flex items-baseline gap-2 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
                the theorem
                <span
                  className="font-normal tracking-normal normal-case"
                  title="the problem's root statement — the bridge gate re-proves exactly this from the chapter's modules alone before anything enters the Library"
                >
                  what this chapter proves
                </span>
              </div>
              <div className="mt-2 overflow-x-auto rounded-xl border border-edge-strong bg-wash px-3.5 py-2.5 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink">
                <Lean code={data.root.statement} />
              </div>
            </div>
          )}
          <HighlightSection
            title="vocabulary"
            hint={
              vocabTotal > vocab.length
                ? `the definitions everything speaks in — ${vocabTotal - vocab.length} quieter ones stay in their modules`
                : 'the definitions everything speaks in'
            }
            decls={vocab}
            onOpenModule={openModule}
          />
          <HighlightSection
            title={leadIsVouched ? 'main results' : 'keystones'}
            hint={
              leadIsVouched
                ? 'the results a human vouched for at sign-off'
                : 'the supporting lemmas the other modules reach for most'
            }
            hintTitle={
              leadIsVouched
                ? undefined
                : 'engine terms: no claim flags survived this harvest (older harvests never recorded them), so the most-cited keystones stand in'
            }
            decls={lead}
            onOpenModule={openModule}
          />
          {leadIsVouched && (
            <HighlightSection
              title="workhorses"
              hint="lemmas the other modules keep reaching for"
              decls={keystones}
              onOpenModule={openModule}
            />
          )}
          {lead.length === 0 && vocab.length === 0 && keystones.length === 0 && (
            <p className="mt-8 text-sm text-ink-faint">
              Nothing stands out yet — browse the modules directly.
            </p>
          )}
        </div>
      )}

      {tab === 'map' && (
        <div className="mt-6">
          <ModuleMap files={data.files} onOpen={openModule} />
        </div>
      )}

      {tab === 'modules' && (
        <div className="mt-5 flex gap-6">
          <div className="w-56 shrink-0">
            {/* the rail IS the table of contents: server order is the
                import order (Kahn), so definitions come before what
                uses them — readable front to back (owner: 先讀定義) */}
            <div
              className="px-2 pb-1.5 text-[10px] text-ink-faint"
              title="a module comes after the modules it imports — reading top to bottom never meets a name before its definition"
            >
              in reading order
            </div>
            <div className="flex flex-col gap-0.5">
              {data.files.map((f) => (
                <button
                  key={f.path}
                  className={`flex cursor-pointer items-baseline justify-between rounded-md px-2 py-1.5 text-left font-mono text-xs transition-colors ${
                    f.path === active?.path
                      ? 'bg-surface-2 text-ink'
                      : 'text-ink-dim hover:bg-surface-2 hover:text-ink'
                  }`}
                  onClick={() => setActiveFile(f.path)}
                  title={f.path}
                >
                  <span className="truncate">
                    {leafOf(f.path)}
                    {f.decls.some((d) => d.is_deliverable) && (
                      <span className="ml-1 text-star" title="holds a signed-off result">
                        ◈
                      </span>
                    )}
                  </span>
                  <span className="tnum ml-2 text-[10px] text-ink-faint">{f.decls.length}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="min-w-0 flex-1">{active && <ModuleReading f={active} />}</div>
        </div>
      )}
    </div>
  )
}
