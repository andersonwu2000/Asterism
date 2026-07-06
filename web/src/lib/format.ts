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
