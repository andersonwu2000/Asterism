/** `Library/Foo/Bar.lean` → `Library.Foo.Bar` — the import-line name
 * of a repo file (Library and LibraryChapter each grew a private
 * copy of this expression). */
export function moduleOf(path: string): string {
  return path.replace(/\.lean$/, '').split('/').join('.')
}

/** the module's last name component — labels, captions */
export function leafOf(path: string): string {
  return moduleOf(path).split('.').pop() ?? path
}

/** Stable machine identities, written exactly as agents cite them. */
export function goalCode(id: number): string {
  return `g${id}`
}

export function groupCode(id: number): string {
  return `G${id}`
}

/** A stable code stays visible beside the human-readable name. */
export function goalLabel(id: number, slug: string): string {
  return `${goalCode(id)} · ${slug}`
}

export function groupLabel(id: number, title: string): string {
  return `${groupCode(id)} · ${title}`
}

/** Fit a sky label without ever clipping the stable goal code. */
export function compactGoalLabel(id: number, slug: string, maxChars: number): string {
  const code = goalCode(id)
  if (maxChars <= code.length) return code
  const prefix = `${code} · `
  const room = maxChars - prefix.length
  if (room <= 0) return code
  if (slug.length <= room) return prefix + slug
  if (room === 1) return prefix + '…'
  const left = Math.ceil((room - 1) / 2)
  const right = Math.floor((room - 1) / 2)
  return `${prefix}${slug.slice(0, left)}…${slug.slice(-right)}`
}

/** "3m ago" style relative time from an ISO timestamp. */
export function relTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const sec = Math.max(0, (Date.now() - t) / 1000)
  if (sec < 60) return 'just now'
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  return `${Math.floor(sec / 86400)}d ago`
}

/** 1234567 → "1.2M", 45300 → "45.3k". */
export function compactNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

/** Seconds → "2h 05m" / "3m 12s" / "45s". */
export function duration(sec: number): string {
  if (sec >= 3600) {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    return `${h}h ${String(m).padStart(2, '0')}m`
  }
  if (sec >= 60) return `${Math.floor(sec / 60)}m ${Math.floor(sec % 60)}s`
  return `${Math.floor(sec)}s`
}
