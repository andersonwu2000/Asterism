import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { refKey } from './docShell'
import type { DocRef } from './docShell'
import {
  NO_TABS,
  activateTab,
  activeRef,
  closeTab,
  closeTabsWhere,
  mapTabs,
  movedRef,
  openTab,
  readTabs,
  tabAt,
  tabLabel,
  tabStep,
  tabTitle,
  tabsKey,
  writeTabs,
} from './docTabs'
import type { TabState } from './docTabs'

/*
 * The Workspace's tab strip (owner, 2026-09-08): which tab a close
 * lands on, what a rename does to one, and what survives a reload.
 */

const doc = (path: string): DocRef => ({ kind: 'doc', path })
const task = (t: string, path: string): DocRef => ({ kind: 'task', task: t, path })

/** The strip built the way the screen builds it: one open at a time. */
function strip(...refs: DocRef[]): TabState {
  return refs.reduce(openTab, NO_TABS)
}
const names = (s: TabState) => s.tabs.map(tabLabel)
const reading = (s: TabState) => {
  const r = activeRef(s)
  return r === null ? null : tabLabel(r)
}

describe('openTab', () => {
  it('opens a document at the end of the strip and reads it', () => {
    const s = strip(doc('user/a.md'), doc('user/b.md'))
    expect(names(s)).toEqual(['a.md', 'b.md'])
    expect(reading(s)).toBe('b.md')
  })

  it('brings an open document forward rather than minting a second tab', () => {
    const s = openTab(strip(doc('user/a.md'), doc('user/b.md')), doc('user/a.md'))
    expect(names(s)).toEqual(['a.md', 'b.md'])
    expect(reading(s)).toBe('a.md')
  })

  it('leaves the state identical when the reading is already that tab', () => {
    // identity matters: this runs on every address change, and a new
    // object each time is a render each time
    const s = strip(doc('user/a.md'))
    expect(openTab(s, doc('user/a.md'))).toBe(s)
  })

  it('tells two tasks` files of one name apart', () => {
    const s = strip(task('Erdos.p1', 'REPORT.md'), task('Erdos.p2', 'REPORT.md'))
    expect(s.tabs).toHaveLength(2)
    expect(activeRef(s)).toEqual(task('Erdos.p2', 'REPORT.md'))
  })
})

describe('activateTab', () => {
  it('reads a tab the strip holds', () => {
    const s = activateTab(strip(doc('user/a.md'), doc('user/b.md')), refKey(doc('user/a.md')))
    expect(reading(s)).toBe('a.md')
  })

  it('ignores a tab that has already been closed', () => {
    const s = strip(doc('user/a.md'))
    expect(activateTab(s, 'doc:user/gone.md')).toBe(s)
  })
})

describe('closeTab', () => {
  it('lands on the tab to the RIGHT of the one that was being read', () => {
    let s = strip(doc('user/a.md'), doc('user/b.md'), doc('user/c.md'))
    s = activateTab(s, refKey(doc('user/b.md')))
    s = closeTab(s, refKey(doc('user/b.md')))
    expect(names(s)).toEqual(['a.md', 'c.md'])
    expect(reading(s)).toBe('c.md')
  })

  it('lands on the left one when the last tab closes', () => {
    const s = closeTab(strip(doc('user/a.md'), doc('user/b.md')), refKey(doc('user/b.md')))
    expect(reading(s)).toBe('a.md')
  })

  it('leaves the reading alone when some OTHER tab closes', () => {
    const s = closeTab(strip(doc('user/a.md'), doc('user/b.md')), refKey(doc('user/a.md')))
    expect(names(s)).toEqual(['b.md'])
    expect(reading(s)).toBe('b.md')
  })

  it('closes to nothing open, which the shell says in words', () => {
    const s = closeTab(strip(doc('user/a.md')), refKey(doc('user/a.md')))
    expect(s).toEqual(NO_TABS)
    expect(activeRef(s)).toBeNull()
  })

  it('ignores a key the strip does not hold', () => {
    const s = strip(doc('user/a.md'))
    expect(closeTab(s, 'doc:user/gone.md')).toBe(s)
  })
})

describe('closeTabsWhere', () => {
  it('closes one task`s files when the engine group is pointed elsewhere', () => {
    const s = closeTabsWhere(
      strip(doc('user/a.md'), task('Erdos.p1', 'TREE.md'), task('Erdos.p1', 'Root.lean')),
      (r) => r.kind === 'task',
    )
    expect(names(s)).toEqual(['a.md'])
    expect(reading(s)).toBe('a.md')
  })
})

describe('mapTabs and movedRef — a file that moved', () => {
  it('follows a rename, keeping the reading on the same document', () => {
    let s = strip(doc('user/a.md'), doc('user/b.md'))
    s = activateTab(s, refKey(doc('user/a.md')))
    s = mapTabs(s, (r) => movedRef(r, 'user/a.md', 'user/renamed.md'))
    expect(names(s)).toEqual(['renamed.md', 'b.md'])
    expect(reading(s)).toBe('renamed.md')
  })

  it('follows a whole folder, and only what is under it', () => {
    const s = mapTabs(strip(doc('user/note/a.md'), doc('user/notes.md')), (r) =>
      movedRef(r, 'user/note', 'user/kept'),
    )
    expect(s.tabs).toEqual([doc('user/kept/a.md'), doc('user/notes.md')])
  })

  it('leaves the engine`s writing alone — a rename is a `user/` act', () => {
    const s = mapTabs(strip(task('Erdos.p1', 'TREE.md')), (r) =>
      movedRef(r, 'TREE.md', 'x.md'),
    )
    expect(s.tabs).toEqual([task('Erdos.p1', 'TREE.md')])
  })

  it('collapses two tabs a rename lands on one name', () => {
    const s = mapTabs(strip(doc('user/a.md'), doc('user/b.md')), (r) =>
      movedRef(r, 'user/a.md', 'user/b.md'),
    )
    expect(s.tabs).toEqual([doc('user/b.md')])
    expect(reading(s)).toBe('b.md')
  })

  it('resolves the legacy address whose task the screen just worked out', () => {
    const s = mapTabs(strip({ kind: 'task', task: null, path: 'REPORT.md' }), (r) =>
      r.kind === 'task' && r.task === null ? task('Erdos.p1', r.path) : r,
    )
    expect(s.tabs).toEqual([task('Erdos.p1', 'REPORT.md')])
    expect(s.active).toBe(refKey(task('Erdos.p1', 'REPORT.md')))
  })
})

describe('what a tab says', () => {
  it('is the file`s own name — a strip of full paths reads as nothing', () => {
    expect(tabLabel(doc('user/notes/a.md'))).toBe('a.md')
    expect(tabLabel(task('Erdos.p1', 'proofs/L_x.lean'))).toBe('L_x.lean')
  })

  it('carries the whole path in the title, task and all', () => {
    expect(tabTitle(doc('user/notes/a.md'))).toBe('user/notes/a.md')
    expect(tabTitle(task('Erdos.p1', 'REPORT.md'))).toBe('Erdos.p1/REPORT.md')
  })
})

/* This suite runs in node (the charter freezes the dependencies, so
 * there is no DOM to borrow one from), and the module reads the same
 * four methods a browser store has. Stubbing it here keeps the LAW
 * under test — what is stored, what is refused, what a corrupt blob
 * comes back as — rather than testing a DOM. */
class MemoryStore {
  private held = new Map<string, string>()
  /** the browser that refuses storage: private mode, cleared site data,
   * a setting. It throws on the ACCESSOR, which is the case every
   * guard in this module exists for. */
  refuse = false
  getItem(k: string): string | null {
    if (this.refuse) throw new Error('storage is not available')
    return this.held.get(k) ?? null
  }
  setItem(k: string, v: string): void {
    if (this.refuse) throw new Error('storage is not available')
    this.held.set(k, v)
  }
  removeItem(k: string): void {
    this.held.delete(k)
  }
  clear(): void {
    this.held.clear()
    this.refuse = false
  }
}

const store = new MemoryStore()
const g = globalThis as { localStorage?: unknown }
const before = g.localStorage

describe('the strip, remembered per Project', () => {
  beforeAll(() => {
    g.localStorage = store
  })
  afterAll(() => {
    g.localStorage = before
  })
  beforeEach(() => store.clear())

  it('is its own key per Project, beside the rail`s fold keys', () => {
    expect(tabsKey('Erdos')).toBe('asterism.workspace.tabs.Erdos')
  })

  it('comes back exactly as it was left', () => {
    const s = activateTab(
      strip(doc('user/a.md'), task('Erdos.p1', 'TREE.md')),
      refKey(doc('user/a.md')),
    )
    writeTabs('Erdos', s)
    expect(readTabs('Erdos')).toEqual(s)
  })

  it('does not read one Project`s strip on another`s shelf', () => {
    writeTabs('Erdos', strip(doc('user/a.md')))
    expect(readTabs('Putnam')).toEqual(NO_TABS)
  })

  it('opens nothing rather than something unreadable', () => {
    localStorage.setItem(tabsKey('Erdos'), 'not json at all')
    expect(readTabs('Erdos')).toEqual(NO_TABS)
    localStorage.setItem(tabsKey('Erdos'), JSON.stringify({ tabs: 'x' }))
    expect(readTabs('Erdos')).toEqual(NO_TABS)
  })

  it('drops the entries of a stored strip that are not documents', () => {
    localStorage.setItem(
      tabsKey('Erdos'),
      JSON.stringify({
        tabs: [doc('user/a.md'), { kind: 'doc' }, null, 7, { kind: 'task', path: 'x' }],
        active: refKey(doc('user/a.md')),
      }),
    )
    expect(readTabs('Erdos').tabs).toEqual([doc('user/a.md')])
  })

  it('reads the leftmost tab when the stored reading names none of them', () => {
    localStorage.setItem(
      tabsKey('Erdos'),
      JSON.stringify({ tabs: [doc('user/a.md'), doc('user/b.md')], active: 'doc:gone' }),
    )
    expect(reading(readTabs('Erdos'))).toBe('a.md')
  })

  it('opens, and refuses to remember, on a browser that refuses storage', () => {
    // a page that failed to lay out because it could not remember would
    // be a worse answer than forgetting (`docShell::readSplit`)
    store.refuse = true
    expect(readTabs('Erdos')).toEqual(NO_TABS)
    expect(() => writeTabs('Erdos', strip(doc('user/a.md')))).not.toThrow()
  })
})

describe('tabStep — the roving focus', () => {
  it('walks the strip and wraps, like the rail`s rows', () => {
    expect(tabStep(0, 'ArrowRight', 3)).toBe(1)
    expect(tabStep(2, 'ArrowRight', 3)).toBe(0)
    expect(tabStep(0, 'ArrowLeft', 3)).toBe(2)
    expect(tabStep(1, 'Home', 3)).toBe(0)
    expect(tabStep(1, 'End', 3)).toBe(2)
  })

  it('owns nothing else — the handler leaves those events alone', () => {
    expect(tabStep(0, 'Enter', 3)).toBeNull()
    expect(tabStep(0, 'Delete', 3)).toBeNull()
    expect(tabStep(0, 'ArrowDown', 3)).toBeNull()
    expect(tabStep(0, 'ArrowRight', 0)).toBeNull()
  })
})

describe('tabAt', () => {
  it('finds a tab by its key, and says -1 for one that is gone', () => {
    const s = strip(doc('user/a.md'), doc('user/b.md'))
    expect(tabAt(s, refKey(doc('user/b.md')))).toBe(1)
    expect(tabAt(s, 'doc:user/gone.md')).toBe(-1)
  })
})
