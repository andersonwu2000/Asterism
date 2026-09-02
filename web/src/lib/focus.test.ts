import { describe, expect, it } from 'vitest'
import { focusBody } from './focus'

/*
 * What the Assistant is told about the screen (human_interface_design.md
 * §1.4-2: "面板收到當前畫面的上下文（點開的星、正在讀的小組、游標所在的
 * 檔案）——這是它勝過 Ask 的關鍵"). `Tooling/serve/chat.py`'s ChatBody
 * docstring is the contract: one or more of problem / group_id /
 * goal_id / doc_path, each contributing its own section.
 */

describe('focusBody', () => {
  it('is null when nothing is open — the picker page has no focus', () => {
    expect(focusBody(null, {})).toBeNull()
  })

  it('carries the task alone when that is all the screen shows', () => {
    expect(focusBody('Erdos.p1', {})).toEqual({ problem: 'Erdos.p1' })
  })

  it('carries the star the reader clicked, alongside its task', () => {
    expect(focusBody('Erdos.p1', { goal_id: 4211 })).toEqual({
      problem: 'Erdos.p1',
      goal_id: 4211,
    })
  })

  it('carries a group and a document', () => {
    expect(focusBody('Erdos.p1', { group_id: 380 })).toEqual({
      problem: 'Erdos.p1',
      group_id: 380,
    })
    expect(focusBody(null, { doc_path: 'user/notes.md' })).toEqual({
      doc_path: 'user/notes.md',
    })
  })

  it('drops the keys the screen has nothing to say about', () => {
    // null is "not open", not "open and empty" — a null goal_id in the
    // body would prime the session on a star nobody is looking at
    expect(focusBody('Erdos.p1', { goal_id: null, group_id: undefined })).toEqual({
      problem: 'Erdos.p1',
    })
  })

  it('a screen may name its own task — the address is not always the answer', () => {
    // the engine room pins one task while lanes run on several
    expect(focusBody('Erdos.p1', { problem: 'Erdos.p10' })).toEqual({
      problem: 'Erdos.p10',
    })
  })
})
