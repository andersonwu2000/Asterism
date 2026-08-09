import { useCallback, useEffect, useRef, useState } from 'react'
import { isStopped } from './shutdown'

/*
 * API client + polling hook. All engine communication is plain HTTP to
 * the FastAPI serve process (charter §1: UI never knows where the
 * engine lives beyond the base URL).
 */

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

/** POST a file's raw bytes as the whole body (the server reads it
 * verbatim — no multipart, so no parser dependency server-side). */
export function apiUpload<T>(path: string, file: Blob): Promise<T> {
  return request<T>(path, { method: 'POST', body: file })
}

export interface PollState<T> {
  data: T | null
  error: ApiError | Error | null
  /** True only before the first response arrives. */
  loading: boolean
  /** `keepPrevious` only: `data` is the PREVIOUS resource's, and the
   * one asked for is still in flight. Surfaces must say so. */
  stale: boolean
  refresh: () => void
}

export interface PollOpts {
  /** Keep showing the previous resource while the next one loads.
   * OFF by default and deliberately so — a screen that swaps its
   * subject must not show the old subject's data as if it were the
   * new one. Opt in where the surrounding page is unchanged and only
   * a panel swaps (the Programme's group switch), and render `stale`
   * visibly: the alternative there is the whole panel unmounting,
   * which reads as a flash (owner, 2026-08-07). */
  keepPrevious?: boolean
}

/**
 * Poll a GET endpoint on an interval (default 2s). Keeps the last good
 * data on transient errors so the UI doesn't flicker; `error` reflects
 * the most recent attempt.
 */
export function usePoll<T>(
  path: string | null,
  intervalMs = 2000,
  opts: PollOpts = {},
): PollState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)
  const [tick, setTick] = useState(0)
  const lastPath = useRef(path)

  useEffect(() => {
    if (path === null) return
    // Navigating to a different resource must not show the previous one's
    // data while the first response is in flight (refreshes of the same
    // path keep old data so the UI doesn't flicker) — unless the caller
    // opts into keeping it and SAYS it is stale.
    if (lastPath.current !== path) {
      lastPath.current = path
      setError(null)
      if (opts.keepPrevious) setStale(true)
      else setData(null)
    }
    // Cancellation is per effect run — a shared ref would be resurrected
    // by the next run, leaving the old poll loop alive and racing.
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const run = async () => {
      // the server was quit on purpose — stop, and do not dress a
      // deliberate shutdown as a failed update
      if (isStopped()) return
      try {
        const d = await apiGet<T>(path)
        if (cancelled) return
        setData(d)
        setStale(false)
        setError(null)
      } catch (e) {
        if (cancelled || isStopped()) return
        setError(e as Error)
      } finally {
        if (!cancelled && !isStopped()) {
          setLoading(false)
          timer = setTimeout(run, intervalMs)
        }
      }
    }
    setLoading(true)
    void run()
    return () => {
      cancelled = true
      if (timer !== undefined) clearTimeout(timer)
    }
    // opts.keepPrevious is read on the path-change branch only; a
    // caller flipping it mid-life is not a case worth re-running for
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, intervalMs, tick])

  const refresh = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, stale, refresh }
}
