import { useState } from 'react'
import { usePoll } from '../lib/api'
import { relTime } from '../lib/format'
import { Link } from '../lib/router'
import { ErrorState } from '../components/ui'
import type { LibraryChapter, LibraryChapterDecl } from '../lib/types'

/*
 * Library chapter — the harvested modules of one problem, read as a
 * textbook (blueprint spirit, in-app). The Library exists so finished
 * work reads at near-Mathlib standard; this page shows THAT text:
 * module docstrings as prose, each declaration with its docstring and
 * kernel-true signature, in source order. Main results (the claims a
 * human vouched for) lead. The engine record (goals, attempts, files)
 * stays on the problem page — one link, not a tab bar.
 */

const DEF_KINDS = new Set(['def', 'induct', 'inductive', 'structure', 'class', 'instance', 'abbrev'])

function moduleOf(path: string): string {
  return path.replace(/\.lean$/, '').split('/').join('.')
}

function anchorId(name: string | null, slug: string): string {
  return `decl-${(name ?? slug).replace(/[^\w.']/g, '_')}`
}

/** Docstring markdown-lite: paragraphs, `code` spans, # headings,
 * `- ` bullets. Lean's unicode IS the math notation — no TeX pass. */
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
          {p.slice(1, -1)}
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

function DeclEntry({ d, module }: { d: LibraryChapterDecl; module: string }) {
  const [copied, setCopied] = useState(false)
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
    <div id={anchorId(d.name, d.slug)} className="group scroll-mt-20">
      <div className="flex items-baseline gap-2.5">
        {/* the sky's glyphs carry over: diamond = meaning-bearer (def),
            round = proposition */}
        <svg width="10" height="10" viewBox="-5 -5 10 10" className="shrink-0 self-center">
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
        <span className="text-[10px] text-ink-faint">{d.decl_kind ?? ''}</span>
        {d.is_deliverable && (
          <span className="text-[10px] tracking-wide text-star" title="a result the Manifest asked for — accepted at sign-off">
            main result
          </span>
        )}
        {copied && <span className="text-[10px] text-ink-faint">copied</span>}
      </div>
      {d.doc && (
        <Prose
          text={d.doc}
          className="mt-1.5 ml-[22px] max-w-[76ch] text-[13px] leading-relaxed text-ink-dim"
        />
      )}
      {d.signature && (
        <pre className="mt-2 ml-[22px] max-w-4xl overflow-x-auto rounded-md border border-edge bg-white/[0.02] px-3.5 py-2.5 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink">
          {d.signature}
        </pre>
      )}
    </div>
  )
}

export default function LibraryChapterScreen({ problem }: { problem: string }) {
  const { data, error, loading } = usePoll<LibraryChapter>(
    `/api/library/${encodeURIComponent(problem)}`,
    30000,
  )

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const ns = problem.includes('.') ? problem.slice(0, problem.indexOf('.')) : null
  const leaf = ns ? problem.slice(ns.length + 1) : problem
  const declCount = data.files.reduce((s, f) => s + f.decls.length, 0)
  const mains = data.files.flatMap((f) => f.decls.filter((d) => d.is_deliverable))

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

      {mains.length > 0 && (
        <div className="mt-5 rounded-lg border border-edge bg-white/[0.015] px-4 py-3">
          <div className="mb-2 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
            main results
          </div>
          <div className="flex flex-col gap-1">
            {mains.map((d) => (
              <a
                key={d.slug}
                href={`#library-jump`}
                onClick={(e) => {
                  e.preventDefault()
                  document
                    .getElementById(anchorId(d.name, d.slug))
                    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }}
                className="w-fit font-mono text-xs text-ink-dim transition-colors hover:text-starlight"
              >
                {(d.name ?? d.slug).split('.').pop()}
              </a>
            ))}
          </div>
        </div>
      )}

      {data.files.map((f) => {
        const mod = moduleOf(f.path)
        const modLeaf = mod.split('.').pop() ?? mod
        return (
          <section key={f.path} className="mt-10">
            <div className="flex items-baseline gap-3 border-b border-edge pb-2">
              <h2 className="font-display text-[18px] text-ink">{modLeaf}</h2>
              <span className="truncate font-mono text-[11px] text-ink-faint" title={f.path}>
                {mod}
              </span>
              <span className="tnum ml-auto text-[11px] text-ink-faint">
                {f.decls.length}
              </span>
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
          </section>
        )
      })}
    </div>
  )
}
