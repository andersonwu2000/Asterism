import { describe, expect, it } from 'vitest'
import { serverIsStale } from './freshness'
import type { Meta } from './types'

const meta = (over: Partial<Meta>): Meta => ({
  workspace: '/ws',
  version: null,
  disk_version: null,
  code: { loaded: 'aaa', disk: 'aaa' },
  db: 'ok',
  daemon: null as never,
  inbox_count: 0,
  claude: { installed: true, logged_in: true, subscription: null },
  antigravity: null as never,
  providers: [],
  lean_ready: { lake: true, mathlib: true },
  ...over,
}) as Meta

describe('serverIsStale', () => {
  it('is silent while the process runs what is on disk', () => {
    expect(serverIsStale(meta({}))).toBe(false)
    expect(serverIsStale(null)).toBe(false)
  })

  it('fires on a release update unzipped under a live console', () => {
    expect(serverIsStale(meta({ version: '1.0.0', disk_version: '1.1.0' }))).toBe(true)
  })

  it('fires in a dev workspace, where there is no VERSION file at all', () => {
    // the case the old banner could never see: both versions null, so
    // it compared null to null and stayed quiet while the process
    // answered with code nobody was running any more
    expect(serverIsStale(meta({ code: { loaded: 'aaa', disk: 'bbb' } }))).toBe(true)
  })

  it('says nothing when the process cannot know its own code', () => {
    expect(serverIsStale(meta({ code: null }))).toBe(false)
  })
})
