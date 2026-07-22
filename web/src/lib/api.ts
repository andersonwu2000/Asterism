import { useCallback, useEffect, useRef, useState } from 'react'

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
  refresh: () => void
}

/**
 * Poll a GET endpoint on an interval (default 2s). Keeps the last good
 * data on transient errors so the UI doesn't flicker; `error` reflects
 * the most recent attempt.
 */
export function usePoll<T>(path: string | null, intervalMs = 2000): PollState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const lastPath = useRef(path)

  useEffect(() => {
    if (path === null) return
    // Navigating to a different resource must not show the previous one's
    // data while the first response is in flight (refreshes of the same
    // path keep old data so the UI doesn't flicker).
    if (lastPath.current !== path) {
      lastPath.current = path
      setData(null)
      setError(null)
    }
    // Cancellation is per effect run — a shared ref would be resurrected
    // by the next run, leaving the old poll loop alive and racing.
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const run = async () => {
      try {
        const d = await apiGet<T>(path)
        if (cancelled) return
        setData(d)
        setError(null)
      } catch (e) {
        if (cancelled) return
        setError(e as Error)
      } finally {
        if (!cancelled) {
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
  }, [path, intervalMs, tick])

  const refresh = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, refresh }
}
