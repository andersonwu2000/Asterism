import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearPollCache, etagOf, peek, put, shared, touch } from './pollCache'

beforeEach(() => clearPollCache())

describe('a reading is shared by whoever asks for the same URL', () => {
  it('serves a cached reading younger than the asker s own interval', () => {
    put('/api/daemon', { running: true }, null, 1_000)
    // a 3s poller asks 1s later: a 1s-old reading is fresher than
    // anything its own loop would have produced
    expect(peek('/api/daemon', 3000, 2_000)).toEqual({ running: true })
    // a 2s poller asking 2s later would be serving itself something
    // older than its own cadence — that is a re-read, not a hit
    expect(peek('/api/daemon', 2000, 3_000)).toBeUndefined()
  })

  it('gives two simultaneous askers one request, not two', async () => {
    let calls = 0
    const run = () => {
      calls += 1
      return Promise.resolve({ n: calls })
    }
    const [a, b] = await Promise.all([
      shared('/api/daemon', run),
      shared('/api/daemon', run),
    ])
    expect(calls).toBe(1)
    expect(a).toEqual({ n: 1 })
    expect(b).toEqual({ n: 1 })
    // and the flight is over: the next asker really asks
    await shared('/api/daemon', run)
    expect(calls).toBe(2)
  })

  it('lets a failed flight be retried rather than remembered', async () => {
    const boom = () => Promise.reject(new Error('down'))
    await expect(shared('/api/daemon', boom)).rejects.toThrow('down')
    await expect(shared('/api/daemon', () => Promise.resolve('ok'))).resolves.toBe('ok')
  })

  it('remembers the etag a response carried, and ages a 304 forward', () => {
    put('/api/problems/p', { big: true }, 'W/"abc"', 1_000)
    expect(etagOf('/api/problems/p')).toBe('W/"abc"')
    // 304: the body did not move, but the reading is current again
    expect(peek('/api/problems/p', 2000, 4_000)).toBeUndefined()
    touch('/api/problems/p', 4_000)
    expect(peek('/api/problems/p', 2000, 5_000)).toEqual({ big: true })
  })
})

describe('the 1MB detail moves only when it changed', () => {
  it('re-uses the kept body when the server answers 304', async () => {
    const { pollGet } = await import('./api')
    const bodies = [{ v: 1 }]
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const inm = (init?.headers as Record<string, string> | undefined)?.[
        'If-None-Match'
      ]
      if (inm === 'W/"1"') {
        return { ok: false, status: 304, headers: new Headers() } as Response
      }
      return {
        ok: true,
        status: 200,
        headers: new Headers({ ETag: 'W/"1"' }),
        json: async () => bodies[0],
      } as unknown as Response
    })
    vi.stubGlobal('fetch', fetchMock)
    try {
      expect(await pollGet('/api/problems/p')).toEqual({ v: 1 })
      // second pass sends the etag and gets 304 — same data, no body
      expect(await pollGet('/api/problems/p')).toEqual({ v: 1 })
      expect(fetchMock).toHaveBeenCalledTimes(2)
      const second = fetchMock.mock.calls[1][1] as RequestInit
      expect((second.headers as Record<string, string>)['If-None-Match']).toBe('W/"1"')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
