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
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    if (path === null) return
    let timer: ReturnType<typeof setTimeout> | undefined
    const run = async () => {
      try {
        const d = await apiGet<T>(path)
        if (!alive.current) return
        setData(d)
        setError(null)
      } catch (e) {
        if (!alive.current) return
        setError(e as Error)
      } finally {
        if (alive.current) {
          setLoading(false)
          timer = setTimeout(run, intervalMs)
        }
      }
    }
    setLoading(true)
    void run()
    return () => {
      alive.current = false
      if (timer !== undefined) clearTimeout(timer)
    }
  }, [path, intervalMs, tick])

  const refresh = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, refresh }
}
