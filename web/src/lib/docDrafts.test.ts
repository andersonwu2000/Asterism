import { describe, expect, it } from 'vitest'
import {
  dirtyPaths,
  dropDraft,
  getDraft,
  isDirty,
  renameDraft,
  setDraft,
  unsavedGuard,
} from './docDrafts'

/*
 * Unsaved writing, and the guard that stands over it (docs_tab_spec.md
 * §B5). The store is module-level ON PURPOSE — a draft has to survive a
 * rail walk and a section switch — so each test works on a Project name
 * of its own rather than sharing one and clearing it.
 */

describe('setDraft / getDraft', () => {
  it('keeps what was typed, and the disk copy it was typed against', () => {
    setDraft('P1', 'user/a.md', 'hello', 'sha-1')
    expect(getDraft('P1', 'user/a.md')).toEqual({ text: 'hello', baseEtag: 'sha-1' })
  })

  it('knows nothing about a document nobody has typed in', () => {
    expect(getDraft('P2', 'user/a.md')).toBeUndefined()
  })

  it('keeps one Project`s writing out of another`s', () => {
    setDraft('P3', 'user/a.md', 'mine', null)
    expect(getDraft('P4', 'user/a.md')).toBeUndefined()
  })
})

describe('dropDraft', () => {
  it('forgets the draft — a saved document has nothing unsaved on it', () => {
    setDraft('P5', 'user/a.md', 'hello', null)
    dropDraft('P5', 'user/a.md')
    expect(getDraft('P5', 'user/a.md')).toBeUndefined()
  })
})

describe('dirtyPaths', () => {
  it('names every document with writing still in it, in a stable order', () => {
    setDraft('P6', 'user/z.md', 'z', null)
    setDraft('P6', 'user/a.md', 'a', null)
    expect(dirtyPaths('P6')).toEqual(['user/a.md', 'user/z.md'])
  })

  it('is empty for a Project nothing was typed in', () => {
    expect(dirtyPaths('P7')).toEqual([])
  })
})

describe('renameDraft', () => {
  it('follows the file — renaming must not throw the writing away', () => {
    setDraft('P8', 'user/a.md', 'hello', 'sha-1')
    renameDraft('P8', 'user/a.md', 'user/b.md')
    expect(getDraft('P8', 'user/a.md')).toBeUndefined()
    expect(getDraft('P8', 'user/b.md')).toEqual({ text: 'hello', baseEtag: 'sha-1' })
  })

  it('follows a whole folder — every draft under it is re-keyed', () => {
    setDraft('P9', 'user/n/a.md', 'a', null)
    setDraft('P9', 'user/n/deep/b.md', 'b', null)
    renameDraft('P9', 'user/n', 'user/m')
    expect(dirtyPaths('P9')).toEqual(['user/m/a.md', 'user/m/deep/b.md'])
  })

  it('does not re-key a sibling whose name merely starts the same', () => {
    setDraft('P10', 'user/notes.md', 'x', null)
    renameDraft('P10', 'user/note', 'user/moved')
    expect(dirtyPaths('P10')).toEqual(['user/notes.md'])
  })
})

describe('isDirty', () => {
  it('is false when nothing was typed', () => {
    expect(isDirty(undefined, 'on disk')).toBe(false)
  })

  it('is false when the draft is exactly what is on disk', () => {
    // typed and undone is not unsaved work
    expect(isDirty({ text: 'on disk', baseEtag: null }, 'on disk')).toBe(false)
  })

  it('is true when the draft differs from the disk copy', () => {
    expect(isDirty({ text: 'edited', baseEtag: null }, 'on disk')).toBe(true)
  })

  it('is true when the disk copy has not arrived — writing exists either way', () => {
    expect(isDirty({ text: 'edited', baseEtag: null }, undefined)).toBe(true)
  })
})

describe('unsavedGuard', () => {
  function fakeEvent() {
    let prevented = false
    return {
      get prevented() {
        return prevented
      },
      preventDefault() {
        prevented = true
      },
      returnValue: undefined as unknown,
    }
  }

  it('says nothing when there is nothing unsaved', () => {
    const e = fakeEvent()
    expect(unsavedGuard(0, e)).toBeUndefined()
    expect(e.prevented).toBe(false)
    expect(e.returnValue).toBeUndefined()
  })

  it('stops the unload when a document still holds writing', () => {
    const e = fakeEvent()
    expect(typeof unsavedGuard(1, e)).toBe('string')
    expect(e.prevented).toBe(true)
    // the legacy channel some browsers still read
    expect(typeof e.returnValue).toBe('string')
  })
})
