import { useMemo, useState } from 'react'
import { usePoll } from '../lib/api'
import { relTime } from '../lib/format'
import { Link } from '../lib/router'
import { ErrorState } from '../components/ui'
import { Lean } from '../lib/lean'
import { LeanProbe } from '../components/LeanProbe'
import type { LibraryChapter, LibraryChapterDecl, LibraryChapterFile } from '../lib/types'

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

const DEF_KINDS = new Set(['def', 'induct', 'inductive', 'structure', 'class', 'instance', 'abbrev'])

function moduleOf(path: string): string {
  return path.replace(/\.lean$/, '').split('/').join('.')
}

function leafOf(path: string): string {
  return moduleOf(path).split('.').pop() ?? path
}

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

function renderSpans(s: string) {
  // split on `code` spans; plain prose gets *emphasis* (docstring
  // markdown); bare math stays untouched (code spans split first)
  const parts = s.split(/(`[^`]+`)/)
  return parts.map((p, i) => {
    if (p.startsWith('`') && p.endsWith('`')) {
      return (
        <code key={i} className="rounded bg-white/[0.06] px-1 font-mono text-[0.92em] text-ink">
          <Lean code={p.slice(1, -1)} />
        </code>
      )
    }
    const em = p.replace(/\*\*/g, '').split(/(\*[^*\s][^*]*\*)/)
    return (
      <span key={i}>
        {em.map((e, j) =>
          e.startsWith('*') && e.endsWith('*') && e.length > 2 ? (
            <em key={j}>{e.slice(1, -1)}</em>
          ) : (
            e
          ),
        )}
      </span>
    )
  })
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
    // ambiguous against the Library original and #print answers BOTH
    return (
      (ns ? `open ${ns}\n\n` : '') +
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
            title="a result the Manifest asked for — accepted at sign-off"
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
            className="overflow-x-auto rounded-md border border-edge bg-white/[0.02] px-3.5 py-2.5 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink"
            title={d.signature}
          >
            <Lean code={conciseSignature(d.signature, short)} declHead />
          </pre>
          <button
            className="absolute right-2 bottom-2 cursor-pointer rounded border border-edge bg-surface px-2.5 py-0.5 font-mono text-[11px] text-ink-dim opacity-0 transition-opacity group-hover/sig:opacity-100 hover:border-edge-strong hover:text-ink"
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
    // Layered drawing done properly (the naive version — alphabetical
    // order, uniform spread — ignored the edges entirely and BT read
    // as spaghetti): longest-path layering, then barycenter sweeps to
    // untangle crossings, then x relaxes toward the mean of each
    // node's neighbours with per-layer collision resolution.
    const byPath = new Map(files.map((f) => [f.path, f]))
    const parentsOf = new Map<string, string[]>()
    const childrenOf = new Map<string, string[]>()
    for (const f of files) {
      parentsOf.set(f.path, f.imports_within.filter((p) => byPath.has(p)))
      for (const imp of f.imports_within) {
        if (!byPath.has(imp)) continue
        childrenOf.set(imp, [...(childrenOf.get(imp) ?? []), f.path])
      }
    }
    const depth = new Map<string, number>()
    const layerOf = (path: string, guard: number): number => {
      const memo = depth.get(path)
      if (memo !== undefined) return memo
      if (guard > files.length + 1) return 0
      const ps = parentsOf.get(path) ?? []
      const d = ps.length === 0 ? 0 : Math.max(...ps.map((i) => layerOf(i, guard + 1))) + 1
      depth.set(path, d)
      return d
    }
    for (const f of files) layerOf(f.path, 0)
    const layers: string[][] = []
    for (const f of files) {
      const l = depth.get(f.path) ?? 0
      ;(layers[l] ??= []).push(f.path)
    }
    for (const l of layers) l.sort()

    const orderIdx = new Map<string, number>()
    const reindex = () => layers.forEach((l) => l.forEach((p, i) => orderIdx.set(p, i)))
    reindex()
    const bary = (p: string, nbrs: string[]): number => {
      const xs = nbrs
        .map((n) => orderIdx.get(n))
        .filter((v): v is number => v !== undefined)
      return xs.length > 0 ? xs.reduce((a, b) => a + b, 0) / xs.length : orderIdx.get(p)!
    }
    for (let it = 0; it < 4; it++) {
      for (let l = 1; l < layers.length; l++) {
        layers[l].sort(
          (a, b) =>
            bary(a, parentsOf.get(a) ?? []) - bary(b, parentsOf.get(b) ?? []) ||
            a.localeCompare(b),
        )
        reindex()
      }
      for (let l = layers.length - 2; l >= 0; l--) {
        layers[l].sort(
          (a, b) =>
            bary(a, childrenOf.get(a) ?? []) - bary(b, childrenOf.get(b) ?? []) ||
            a.localeCompare(b),
        )
        reindex()
      }
    }

    // continuous x: pull toward neighbour mean, keep ≥1 slot apart
    const x = new Map<string, number>()
    layers.forEach((l) => l.forEach((p, i) => x.set(p, i - (l.length - 1) / 2)))
    for (let it = 0; it < 12; it++) {
      for (const f of files) {
        const nbrs = [...(parentsOf.get(f.path) ?? []), ...(childrenOf.get(f.path) ?? [])]
        if (nbrs.length === 0) continue
        const m = nbrs.reduce((a, n) => a + (x.get(n) ?? 0), 0) / nbrs.length
        x.set(f.path, (x.get(f.path)! + m) / 2)
      }
      for (const l of layers) {
        l.sort((a, b) => x.get(a)! - x.get(b)!)
        for (let i = 1; i < l.length; i++) {
          x.set(l[i], Math.max(x.get(l[i])!, x.get(l[i - 1])! + 1))
        }
      }
    }

    const xs = [...x.values()]
    const minX = Math.min(...xs)
    const spread = Math.max(Math.max(...xs) - minX, 1)
    // fit the page when possible; wide skies shrink toward 95px slots
    const XG = Math.max(95, Math.min(155, 880 / spread))
    const YG = 108
    const width = spread * XG + 170
    const pos = new Map<string, { x: number; y: number }>()
    // collision-driven label rows: walk each layer in x order and
    // drop a label to the lower row only when the upper row's last
    // label would actually touch it (parity alone missed near-misses
    // in narrow layers)
    const stagger = new Map<string, number>()
    const cap = Math.max(12, Math.floor((XG * 1.9) / 6.6))
    const labelW = (p: string) => Math.min(leafOf(p).length, cap) * 6.6
    for (const l of layers) {
      l.sort((a, b) => x.get(a)! - x.get(b)!)
      const rightEdge = [-Infinity, -Infinity]
      for (const p of l) {
        const cx = (x.get(p)! - minX) * XG
        const w = labelW(p)
        const row = cx - w / 2 > rightEdge[0] + 26 ? 0 : 1
        stagger.set(p, row)
        rightEdge[row] = Math.max(rightEdge[row], cx + w / 2)
      }
    }
    for (const f of files) {
      pos.set(f.path, {
        x: 85 + (x.get(f.path)! - minX) * XG,
        y: 55 + (depth.get(f.path) ?? 0) * YG,
      })
    }
    return { pos, width, height: 70 + layers.length * YG, XG, stagger }
  }, [files])

  const [hover, setHover] = useState<string | null>(null)
  return (
    <div className="overflow-x-auto">
      <svg width={layout.width} height={layout.height} className="mx-auto block">
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
              const dx = b.x - a.x
              const dy = b.y - a.y
              const len = Math.hypot(dx, dy) || 1
              const bow = Math.min(60, span * 0.16) * (ei % 2 === 0 ? 1 : -1)
              const mx = (a.x + b.x) / 2 + (-dy / len) * bow
              const my = (a.y + b.y) / 2 + (dx / len) * bow
              return (
                <path
                  key={`${f.path}<${imp}`}
                  d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
                  fill="none"
                  stroke="var(--color-starlight)"
                  strokeWidth={1}
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
                strokeWidth={1}
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
          const drop = (layout.stagger.get(f.path) ?? 0) * 15
          return (
            <g
              key={f.path}
              transform={`translate(${p.x},${p.y})`}
              className="cursor-pointer"
              onMouseEnter={() => setHover(f.path)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onOpen(f.path)}
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
                y={r + 16 + drop}
                textAnchor="middle"
                className="pointer-events-none select-none"
                fill={hover === f.path ? 'var(--color-ink)' : 'var(--color-ink-dim)'}
                fontSize={11}
                fontFamily="var(--font-mono)"
              >
                {(() => {
                  const s = leafOf(f.path)
                  const cap = Math.max(12, Math.floor((layout.XG * 1.9) / 6.6))
                  return s.length > cap
                    ? `${s.slice(0, Math.floor(cap / 2) - 1)}…${s.slice(-(Math.floor(cap / 2) - 1))}`
                    : s
                })()}
              </text>
              <text
                y={r + 29 + drop}
                textAnchor="middle"
                className="tnum pointer-events-none select-none"
                fill="var(--color-ink-faint)"
                fontSize={9}
              >
                {f.decls.length}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="pb-2 text-center text-[11px] text-ink-faint">
        modules and their imports — ringed stars hold main results; click one to read it
      </p>
    </div>
  )
}

function HighlightSection({
  title,
  hint,
  decls,
  onOpenModule,
}: {
  title: string
  hint?: string
  decls: (LibraryChapterDecl & { file: string })[]
  onOpenModule: (path: string) => void
}) {
  if (decls.length === 0) return null
  return (
    <section className="mt-8">
      <div className="mb-4 border-b border-edge pb-2 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
        {title}
        {hint && (
          <span className="ml-3 font-normal tracking-normal normal-case text-ink-faint/80">
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
        <Link
          to={`/problems/${encodeURIComponent(problem)}`}
          className="ml-auto text-xs text-ink-faint underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
          title="the working record: goals, attempts, timeline"
        >
          engine record →
        </Link>
      </div>

      <nav className="mt-4 flex gap-5 border-b border-edge">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`relative cursor-pointer pb-2 text-xs transition-colors duration-150 ${
              tab === t.id ? 'text-ink' : 'text-ink-dim hover:text-ink'
            }`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {tab === t.id && (
              <span className="absolute inset-x-0 -bottom-px h-px bg-ink" aria-hidden />
            )}
          </button>
        ))}
      </nav>

      {tab === 'highlights' && (
        <div>
          <HighlightSection
            title={leadIsVouched ? 'main results' : 'keystones'}
            hint={
              leadIsVouched
                ? 'the results a human vouched for at sign-off'
                : 'no claim flags survive this harvest — these are the results the other modules reach for'
            }
            decls={lead}
            onOpenModule={openModule}
          />
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
            <div className="flex flex-col gap-0.5">
              {data.files.map((f) => (
                <button
                  key={f.path}
                  className={`flex cursor-pointer items-baseline justify-between rounded px-2 py-1.5 text-left font-mono text-xs transition-colors ${
                    f.path === active?.path
                      ? 'bg-surface-2 text-ink'
                      : 'text-ink-dim hover:bg-surface-2 hover:text-ink'
                  }`}
                  onClick={() => setActiveFile(f.path)}
                  title={f.path}
                >
                  <span className="truncate">{leafOf(f.path)}</span>
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
