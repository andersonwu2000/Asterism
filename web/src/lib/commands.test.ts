import { describe, expect, it } from 'vitest'
import {
  RECEIPT_SLOW_POLLS,
  affectedSummary,
  commandTitle,
  fieldFromDetail,
  laneSignal,
  newIdempotencyKey,
  payloadFor,
  receiptLine,
  receiptStart,
  receiptStep,
  splitPrepared,
} from './commands'
import type { CommandRow } from './commands'
import type { RunWorker } from './types'

/*
 * The command path's decidable parts (human_interface_design.md §1.3 /
 * §3.3). The engine owns what a command MEANS and what it requires;
 * these are the console's own obligations — build the payload the
 * appliers already read, never repeat a request as a second command,
 * put a refusal under the field it names, and say honestly which of
 * the three states a receipt is in.
 */

const row = (over: Partial<CommandRow> = {}): CommandRow => ({
  id: 7,
  problem: 'Erdos.p1',
  kind: 'ConfirmShelve',
  payload: {},
  idempotency_key: 'k',
  expected_revision: 3,
  status: 'queued',
  outcome: null,
  decision_id: null,
  created_at: '2026-09-03T00:00:00Z',
  applied_at: null,
  ...over,
})

describe('payloadFor', () => {
  it('writes the strategist decision own field names', () => {
    expect(payloadFor('ConfirmShelve', { targetGoalId: 12, reason: 'dead route' })).toEqual({
      target_goal_id: 12,
      reason: 'dead route',
    })
    expect(payloadFor('Inject', { targetGoalId: 12, proof: '## Proof\nby hand' })).toEqual({
      target_goal_id: 12,
      proof: '## Proof\nby hand',
    })
    expect(payloadFor('ReturnToParent', { groupId: 4, reason: 'exhausted' })).toEqual({
      group_id: 4,
      reason: 'exhausted',
    })
    expect(payloadFor('Signal', { pipelineId: 'p-9', signal: 'shelve' })).toEqual({
      pipeline_id: 'p-9',
      signal: 'shelve',
    })
  })

  it('omits a field the person left blank instead of sending an empty one', () => {
    // the engine reads present-but-empty as missing; sending '' would
    // make the console and the validator disagree about what is owed
    expect(payloadFor('MarkDeliverable', { targetGoalId: 12, reason: '  ' })).toEqual({
      target_goal_id: 12,
    })
    expect(payloadFor('Delegate', { targetGoalId: 12, charter: '', brief: '' })).toEqual({
      target_goal_id: 12,
    })
  })

  it('a Delegate may carry a charter with no goal', () => {
    expect(payloadFor('Delegate', { charter: 'settle the n=4 case' })).toEqual({
      charter: 'settle the n=4 case',
    })
  })
})

describe('newIdempotencyKey', () => {
  it('is fresh every time — a retry is the same command, a re-issue is not', () => {
    const keys = new Set(Array.from({ length: 50 }, () => newIdempotencyKey()))
    expect(keys.size).toBe(50)
    for (const k of keys) expect(k.length).toBeGreaterThan(15)
  })
})

describe('fieldFromDetail', () => {
  it('names the field the engine says is missing', () => {
    expect(
      fieldFromDetail(
        'ConfirmShelve requires `reason` — a park is TERMINAL, and the reason is the only record of why this line was stopped (§1.3)',
      ),
    ).toBe('reason')
    expect(
      fieldFromDetail('Inject requires `proof` — the `## Proof` the formalizer is to settle'),
    ).toBe('proof')
    expect(fieldFromDetail('MarkDeliverable requires target_goal_id')).toBe('target_goal_id')
    expect(fieldFromDetail('ReturnToParent requires group_id')).toBe('group_id')
    expect(
      fieldFromDetail(
        'Delegate needs either a `charter` (the claim the new group must settle) or a `target_goal_id` to take one from',
      ),
    ).toBe('charter')
    expect(
      fieldFromDetail('Signal requires `pipeline_id` — a kill names the one worker it stops (§3.7)'),
    ).toBe('pipeline_id')
  })

  it('is null when the refusal is about no field of the form', () => {
    expect(fieldFromDetail("no problem 'Erdos.p9'")).toBeNull()
    expect(fieldFromDetail("unknown command kind 'Frobnicate'")).toBeNull()
    // a backticked word that is not one of the form fields must not
    // light up an unrelated input
    expect(
      fieldFromDetail('FetchPaper is retired (2026-08-22): the `Scholar` pipeline is gone'),
    ).toBeNull()
  })
})

describe('the receipt state machine', () => {
  it('starts waiting and stays waiting while the row is queued', () => {
    let r = receiptStart(7)
    expect(r).toEqual({ phase: 'waiting', id: 7, polls: 0, slow: false })
    r = receiptStep(r, row())
    expect(r.phase).toBe('waiting')
    expect(receiptLine(r)).toMatch(/next tick/)
  })

  it('says the engine may be stopped once the wait is long', () => {
    let r = receiptStart(7)
    for (let i = 0; i <= RECEIPT_SLOW_POLLS; i++) r = receiptStep(r, row())
    expect(r).toMatchObject({ phase: 'waiting', slow: true })
    expect(receiptLine(r)).toMatch(/while the engine is stopped/)
  })

  it('an unreachable read is not an answer — it keeps waiting', () => {
    let r = receiptStart(7)
    r = receiptStep(r, null)
    expect(r.phase).toBe('waiting')
  })

  it('applied is terminal and carries the outcome', () => {
    const r = receiptStep(
      receiptStart(7),
      row({ status: 'applied', outcome: 'committed', decision_id: 91 }),
    )
    expect(r).toEqual({ phase: 'applied', id: 7, outcome: 'committed' })
    expect(receiptLine(r)).toMatch(/done/)
    // terminal: a later poll cannot walk it back
    expect(receiptStep(r, row())).toEqual(r)
  })

  it('a stale rejection says the record moved, not "stale"', () => {
    const r = receiptStep(receiptStart(7), row({ status: 'rejected', outcome: 'stale' }))
    expect(r).toMatchObject({ phase: 'rejected', stale: true })
    expect(receiptLine(r)).toMatch(/moved/)
    expect(receiptLine(r)).not.toBe('stale')
  })

  it('any other rejection is quoted verbatim — the engine wrote the reason', () => {
    const r = receiptStep(
      receiptStart(7),
      row({
        status: 'rejected',
        outcome: 'a signal stops an in-flight Formalizer; pipeline p-9 is a Strategist',
      }),
    )
    expect(r).toMatchObject({ phase: 'rejected', stale: false })
    expect(receiptLine(r)).toContain('in-flight Formalizer')
  })
})

describe('affectedSummary', () => {
  it('counts what closes, by kind', () => {
    expect(
      affectedSummary({
        cascade: true,
        revision: 3,
        affected: [
          { id: 1, kind: 'goal', slug: 'a', status: 'open', effect: 'shelved' },
          { id: 2, kind: 'goal', slug: 'b', status: 'open', effect: 'shelved' },
          { id: 4, kind: 'group', slug: 'c', status: 'active', effect: 'closed' },
        ],
      }),
    ).toBe('3 nodes — 2 goals and 1 group')
  })

  it('one node is not a cascade and says so in the singular', () => {
    expect(
      affectedSummary({
        cascade: false,
        revision: 0,
        affected: [{ id: 1, kind: 'goal', slug: 'a', status: 'open', effect: 'shelved' }],
      }),
    ).toBe('1 goal')
  })

  it('an empty preview says nothing would move', () => {
    expect(affectedSummary({ cascade: false, revision: 0, affected: [] })).toBe(
      'nothing would change',
    )
  })
})

describe('commandTitle', () => {
  it('speaks the reader language, not the enum', () => {
    expect(commandTitle('ConfirmShelve')).toBe('park this goal')
    expect(commandTitle('MarkDeliverable')).toBe('mark it delivered')
    expect(commandTitle('Inject')).toBe('hand it a proof')
    expect(commandTitle('Delegate')).toBe('hand it to a new group')
    expect(commandTitle('ReturnToParent')).toBe('return this group to its parent')
  })
})

describe('splitPrepared', () => {
  const block = JSON.stringify({
    preview: {
      affected: [
        { id: 12, kind: 'goal', slug: 'descent_step', status: 'open', effect: 'shelved' },
      ],
      cascade: false,
      revision: 4,
    },
    payload: { target_goal_id: 12, reason: 'the route is dead' },
    kind: 'ConfirmShelve',
    problem: 'Erdos.p1',
  })

  it('finds the prepared command in a fenced block and takes it out of the prose', () => {
    const out = splitPrepared(
      `I would park g12; here is the command.\n\n\`\`\`json\n${block}\n\`\`\`\n\nIt closes one goal.`,
    )
    expect(out.commands).toHaveLength(1)
    expect(out.commands[0]).toMatchObject({
      kind: 'ConfirmShelve',
      problem: 'Erdos.p1',
      payload: { target_goal_id: 12, reason: 'the route is dead' },
    })
    expect(out.commands[0].preview?.revision).toBe(4)
    // the JSON is machine bookkeeping — the reader gets the affordance
    expect(out.text).not.toContain('target_goal_id')
    expect(out.text).toContain('I would park g12')
    expect(out.text).toContain('It closes one goal.')
  })

  it('takes a whole answer that is only the JSON', () => {
    const out = splitPrepared(block)
    expect(out.commands).toHaveLength(1)
    expect(out.text.trim()).toBe('')
  })

  it('leaves ordinary fenced code alone', () => {
    const src = 'Try this:\n\n```lean\ntheorem x : True := trivial\n```\n'
    const out = splitPrepared(src)
    expect(out.commands).toHaveLength(0)
    expect(out.text).toBe(src)
  })

  it('a JSON block that is not a command is left in the prose', () => {
    const src = '```json\n{"hello": 1}\n```'
    const out = splitPrepared(src)
    expect(out.commands).toHaveLength(0)
    expect(out.text).toBe(src)
  })

  it('refuses a block naming a kind the queue does not take', () => {
    const src = `\`\`\`json\n${JSON.stringify({
      kind: 'Frobnicate',
      problem: 'Erdos.p1',
      payload: {},
    })}\n\`\`\``
    expect(splitPrepared(src).commands).toHaveLength(0)
  })

  it('several prepared commands in one answer all surface', () => {
    const two = `${'```json\n' + block + '\n```'}\n\nand also\n\n${
      '```json\n' +
      JSON.stringify({
        kind: 'MarkDeliverable',
        problem: 'Erdos.p1',
        payload: { target_goal_id: 13 },
      }) +
      '\n```'
    }`
    const out = splitPrepared(two)
    expect(out.commands.map((c) => c.kind)).toEqual(['ConfirmShelve', 'MarkDeliverable'])
  })
})

describe('laneSignal', () => {
  const lane = (over: Partial<RunWorker> = {}): RunWorker =>
    ({
      kind: 'Formalizer',
      slug: 'lemma_a',
      problem: 'Erdos.p1',
      pipeline_id: 'pl-7',
      statement: null,
      leased_at: null,
      mode: null,
      path: null,
      file: null,
      ...over,
    }) as RunWorker

  it('offers the stop control when the feed names the worker', () => {
    expect(laneSignal(lane(), null)).toEqual({
      move: 'stop',
      pipelineId: 'pl-7',
      problem: 'Erdos.p1',
    })
  })

  it('the lane own problem outranks the console lens', () => {
    const r = laneSignal(lane({ problem: 'Erdos.p10' }), 'Erdos.p1')
    expect(r).toEqual({ move: 'stop', pipelineId: 'pl-7', problem: 'Erdos.p10' })
  })

  it('falls back to the lens when the lane names no problem', () => {
    const r = laneSignal(lane({ problem: null }), 'Erdos.p1')
    expect(r).toEqual({ move: 'stop', pipelineId: 'pl-7', problem: 'Erdos.p1' })
  })

  it('says it cannot address a Formalizer whose pipeline is null', () => {
    expect(laneSignal(lane({ pipeline_id: null }), null)).toEqual({ move: 'unaddressable' })
    expect(laneSignal(lane({ pipeline_id: '  ' }), null)).toEqual({ move: 'unaddressable' })
    // a bundle older than the field reads the same way: no id, no aim
    expect(laneSignal(lane({ pipeline_id: undefined }), null)).toEqual({
      move: 'unaddressable',
    })
  })

  it('offers nothing on a kind the applier refuses, even with an id', () => {
    expect(laneSignal(lane({ kind: 'Strategist' }), null)).toEqual({ move: 'none' })
    // and nothing on a lane belonging to no problem the console knows
    expect(laneSignal(lane({ problem: null }), null)).toEqual({ move: 'none' })
  })
})
