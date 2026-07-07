import type { ReactNode } from 'react'

/*
 * Lean display highlighting — the owner-approved exception to the
 * achromatic rule: code carries hue, at low saturation (tinted greys,
 * see --color-syn-* in index.css). One real single-pass tokenizer,
 * shared by every surface that shows Lean (statements, signatures,
 * file viewer, inline `code`), replacing the old regex-replace chain
 * whose keyword pass could corrupt its own emitted markup.
 * Display only — nothing here feeds soundness.
 */

const KEYWORDS = new Set([
  'theorem', 'lemma', 'def', 'abbrev', 'example', 'instance', 'inductive',
  'structure', 'class', 'noncomputable', 'private', 'protected', 'partial',
  'unsafe', 'mutual', 'where', 'deriving', 'extends', 'import', 'open',
  'namespace', 'end', 'section', 'variable', 'variables', 'universe',
  'axiom', 'by', 'exact', 'intro', 'intros', 'apply', 'refine', 'obtain',
  'rcases', 'rintro', 'simp', 'rw', 'rfl', 'calc', 'have', 'show', 'from',
  'let', 'fun', 'match', 'with', 'do', 'if', 'then', 'else', 'at', 'sorry',
  'scoped', 'local', 'attribute', 'set_option', 'in',
])
const SORTS = new Set(['Type', 'Prop', 'Sort'])

/** keywords that BIND a name — the next word is the thing being
 * declared, the most load-bearing token on the line */
const DECL_KEYWORDS = new Set([
  'theorem', 'lemma', 'def', 'abbrev', 'example', 'instance', 'inductive',
  'structure', 'class', 'axiom', 'namespace',
])

type TokKind = 'kw' | 'decl' | 'sort' | 'str' | 'num' | 'cmt' | 'attr' | 'plain'
interface Tok {
  t: TokKind
  s: string
}

const WORD_RE = /[A-Za-z_][A-Za-z0-9_'!?]*/y
const QUALIFIED_RE = /[A-Za-z_][A-Za-z0-9_'!?]*(?:\.[A-Za-z_][A-Za-z0-9_'!?]*)*/y
const NUM_RE = /\d[\d.]*/y
// letterlike + mathematical-alphanumeric symbols (ℝ, ℕ, 𝓡, 𝔽…) — these
// are types/math objects, so they share the sort ink
const MATH_ALPHA_RE = /[ℂ-ℸ\u{1D400}-\u{1D7FF}]+/uy

export function tokenizeLean(src: string): Tok[] {
  const toks: Tok[] = []
  let plain = ''
  // armed after a declaring keyword: the next word is the decl name
  let expectDecl = false
  const flush = () => {
    if (plain !== '') {
      toks.push({ t: 'plain', s: plain })
      plain = ''
    }
  }
  let i = 0
  while (i < src.length) {
    const two = src.slice(i, i + 2)
    if (two === '/-') {
      // block comments nest in Lean
      flush()
      let depth = 1
      let j = i + 2
      while (j < src.length && depth > 0) {
        if (src.startsWith('/-', j)) {
          depth++
          j += 2
        } else if (src.startsWith('-/', j)) {
          depth--
          j += 2
        } else {
          j++
        }
      }
      toks.push({ t: 'cmt', s: src.slice(i, j) })
      i = j
      continue
    }
    if (two === '--') {
      flush()
      let j = src.indexOf('\n', i)
      if (j === -1) j = src.length
      toks.push({ t: 'cmt', s: src.slice(i, j) })
      i = j
      continue
    }
    if (src[i] === '"') {
      flush()
      let j = i + 1
      while (j < src.length && src[j] !== '"') {
        j += src[j] === '\\' ? 2 : 1
      }
      toks.push({ t: 'str', s: src.slice(i, Math.min(j + 1, src.length)) })
      i = Math.min(j + 1, src.length)
      continue
    }
    if (two === '@[') {
      flush()
      let j = src.indexOf(']', i)
      if (j === -1) j = src.length - 1
      toks.push({ t: 'attr', s: src.slice(i, j + 1) })
      i = j + 1
      continue
    }
    WORD_RE.lastIndex = i
    const w = WORD_RE.exec(src)
    if (w && w.index === i) {
      flush()
      const word = w[0]
      if (expectDecl && !KEYWORDS.has(word)) {
        // the declared name may be qualified (namespace Foo.Bar)
        QUALIFIED_RE.lastIndex = i
        const q = QUALIFIED_RE.exec(src)
        const name = q && q.index === i ? q[0] : word
        toks.push({ t: 'decl', s: name })
        i += name.length
        expectDecl = false
        continue
      }
      toks.push({
        t: KEYWORDS.has(word) ? 'kw' : SORTS.has(word) ? 'sort' : 'plain',
        s: word,
      })
      if (KEYWORDS.has(word)) expectDecl = DECL_KEYWORDS.has(word)
      i += word.length
      continue
    }
    NUM_RE.lastIndex = i
    const n = NUM_RE.exec(src)
    if (n && n.index === i) {
      flush()
      toks.push({ t: 'num', s: n[0] })
      i += n[0].length
      continue
    }
    MATH_ALPHA_RE.lastIndex = i
    const m = MATH_ALPHA_RE.exec(src)
    if (m && m.index === i) {
      flush()
      toks.push({ t: expectDecl ? 'decl' : 'sort', s: m[0] })
      expectDecl = false
      i += m[0].length
      continue
    }
    // any solid punctuation between a declaring keyword and a word
    // (anonymous `instance :`) disarms the decl expectation
    if (expectDecl && !/\s/.test(src[i])) expectDecl = false
    plain += src[i]
    i++
  }
  flush()
  // merge adjacent plain runs split by non-keyword words
  const merged: Tok[] = []
  for (const t of toks) {
    const last = merged[merged.length - 1]
    if (last && last.t === 'plain' && t.t === 'plain') last.s += t.s
    else merged.push({ ...t })
  }
  return merged
}

const TOK_CLS: Record<TokKind, string | null> = {
  kw: 'text-syn-kw',
  decl: 'text-syn-decl',
  sort: 'text-syn-sort',
  str: 'text-syn-str',
  num: 'text-syn-num',
  attr: 'text-syn-attr',
  cmt: 'text-ink-faint italic',
  plain: null,
}

// inside comments, `backticked refs` carry the amber ink — a
// docstring's cross-references are its most load-bearing words
const CMT_CODE_CLS = 'text-syn-num/90'
const CMT_CODE_RE = /(`[^`\n]+`)/

/** Inline-highlighted Lean: emits spans only where a token carries
 * ink, so it drops into any <pre>/<code>/table cell unchanged. */
export function Lean({ code }: { code: string }): ReactNode {
  return tokenizeLean(code).map((t, i) => {
    if (t.t === 'cmt') {
      return (
        <span key={i} className={TOK_CLS.cmt!}>
          {t.s.split(CMT_CODE_RE).map((p, j) =>
            p.startsWith('`') && p.endsWith('`') && p.length > 2 ? (
              <span key={j} className={CMT_CODE_CLS}>
                {p}
              </span>
            ) : (
              p
            ),
          )}
        </span>
      )
    }
    return TOK_CLS[t.t] ? (
      <span key={i} className={TOK_CLS[t.t]!}>
        {t.s}
      </span>
    ) : (
      t.s
    )
  })
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** Same highlighting as an HTML string — for the hand-rolled markdown
 * pipeline (FileViewer) that builds innerHTML. */
export function leanHtml(src: string): string {
  return tokenizeLean(src)
    .map((t) => {
      if (t.t === 'cmt') {
        const inner = t.s
          .split(CMT_CODE_RE)
          .map((p) =>
            p.startsWith('`') && p.endsWith('`') && p.length > 2
              ? `<span class="${CMT_CODE_CLS}">${escapeHtml(p)}</span>`
              : escapeHtml(p),
          )
          .join('')
        return `<span class="${TOK_CLS.cmt}">${inner}</span>`
      }
      const cls = TOK_CLS[t.t]
      const esc = escapeHtml(t.s)
      return cls ? `<span class="${cls}">${esc}</span>` : esc
    })
    .join('')
}
