import { describe, expect, it } from 'vitest'
import {
  SECTION_LABEL,
  TASK_SECTIONS,
  defaultTask,
  parseProjectRoute,
  projectPath,
  railVisible,
  shelfOrder,
  tasksOf,
} from './projectRoute'
import type { BoardProblem } from './types'

function task(name: string, over: Partial<BoardProblem> = {}): BoardProblem {
  return {
    name,
    project: 'Erdos',
    status: 'paused',
    goals: { open: 1, proved: 1, shelved: 0, total: 2 },
    in_flight: 0,
    queued: 0,
    last_event: '2026-08-01T00:00:00+00:00',
    created_at: '2026-07-01T00:00:00+00:00',
    ...over,
  } as BoardProblem
}

describe('the menu', () => {
  it('names the engine in one word, and keeps its address (2026-09-05)', () => {
    // the tab was "Engine room": two words beside five one-word peers,
    // for a surface every sentence in the UI already calls "the
    // engine". The route segment is unchanged — bookmarks and mailed
    // links to `…/engine` keep landing.
    expect(SECTION_LABEL.engine).toBe('Engine')
    expect(Object.values(SECTION_LABEL).every((l) => !l.includes(' '))).toBe(true)
    expect(parseProjectRoute(['p', 'Erdos', 'engine'])?.section).toBe('engine')
  })
})

describe('parseProjectRoute', () => {
  it('reads project, section and task out of #/p/<project>/<section>/<task>', () => {
    expect(parseProjectRoute(['p', 'Erdos', 'sky', 'Erdos.p358'])).toEqual({
      project: 'Erdos',
      section: 'sky',
      problem: 'Erdos.p358',
      goal: null,
      rest: [],
    })
  })

  it('defaults to the Tasks section — the shelf is what a Project opens on', () => {
    expect(parseProjectRoute(['p', 'Erdos'])).toEqual({
      project: 'Erdos',
      section: 'tasks',
      problem: null,
      goal: null,
      rest: [],
    })
  })

  it('refuses an unknown section rather than rendering a blank frame', () => {
    expect(parseProjectRoute(['p', 'Erdos', 'library'])?.section).toBe('tasks')
  })

  it('is null when the route is not a Project route at all', () => {
    expect(parseProjectRoute([])).toBeNull()
    expect(parseProjectRoute(['settings'])).toBeNull()
    expect(parseProjectRoute(['p'])).toBeNull()
  })

  it('hands the documents section its whole path — a file is not a task', () => {
    expect(parseProjectRoute(['p', 'Erdos', 'docs', 'user', 'notes', 'a.md'])).toEqual({
      project: 'Erdos',
      section: 'docs',
      problem: null,
      goal: null,
      rest: ['user', 'notes', 'a.md'],
    })
  })
})

describe('parseProjectRoute — a star in the address', () => {
  it('reads /g/<id> after the task, so one node can be linked to', () => {
    const r = parseProjectRoute(['p', 'Erdos', 'sky', 'Erdos.p358', 'g', '4412'])
    expect(r?.goal).toBe(4412)
    expect(r?.problem).toBe('Erdos.p358')
  })
  it('ignores a goal that is not a number rather than selecting NaN', () => {
    expect(parseProjectRoute(['p', 'Erdos', 'sky', 'Erdos.p358', 'g', 'x'])?.goal).toBeNull()
  })
})

describe('projectPath', () => {
  it('encodes both names', () => {
    expect(projectPath('Erdos', 'sky', 'Erdos.p 1')).toBe('/p/Erdos/sky/Erdos.p%201')
  })
  it('omits the task when there is none', () => {
    expect(projectPath('Erdos', 'engine')).toBe('/p/Erdos/engine')
  })
  it('appends the star when one is named', () => {
    expect(projectPath('Erdos', 'sky', 'Erdos.p1', 42)).toBe('/p/Erdos/sky/Erdos.p1/g/42')
  })
})

describe('shelfOrder', () => {
  // Live, 2026-09-04: the same shelf was ordered three ways — the task
  // column in API order, the shelf table by its own status list, the
  // default task by a third rule — so switching section reshuffled the
  // list under the reader. One attention order, read everywhere.
  it('puts the human`s move first, then what is stuck, then what moves', () => {
    const rows = [
      task('Erdos.quiet'),
      task('Erdos.moving', { status: 'proving' }),
      task('Erdos.stuck', { status: 'stalled' }),
      task('Erdos.yours', { status: 'awaiting_human' }),
    ]
    expect(shelfOrder(rows).map((p) => p.name)).toEqual([
      'Erdos.yours',
      'Erdos.stuck',
      'Erdos.moving',
      'Erdos.quiet',
    ])
  })

  it('counts a signoff as the human`s move and an agent in flight as motion', () => {
    const rows = [
      task('Erdos.a', { in_flight: 2 }),
      task('Erdos.b', { status: 'signoff_pending' }),
    ]
    expect(shelfOrder(rows).map((p) => p.name)).toEqual(['Erdos.b', 'Erdos.a'])
  })

  it('reads the newest first inside one rank', () => {
    const rows = [
      task('Erdos.old', { last_event: '2026-08-01T00:00:00+00:00' }),
      task('Erdos.new', { last_event: '2026-08-30T00:00:00+00:00' }),
    ]
    expect(shelfOrder(rows).map((p) => p.name)).toEqual(['Erdos.new', 'Erdos.old'])
  })

  it('keeps a task that has never moved below one that has', () => {
    const rows = [
      task('Erdos.never', { last_event: null }),
      task('Erdos.once', { last_event: '2026-08-01T00:00:00+00:00' }),
    ]
    expect(shelfOrder(rows).map((p) => p.name)).toEqual(['Erdos.once', 'Erdos.never'])
  })

  it('breaks a tie by name, so a reload does not reshuffle the shelf', () => {
    const rows = [task('Erdos.b'), task('Erdos.a')]
    expect(shelfOrder(rows).map((p) => p.name)).toEqual(['Erdos.a', 'Erdos.b'])
  })

  it('leaves the caller`s array alone — the shelf is read, not rewritten', () => {
    const rows = [task('Erdos.b'), task('Erdos.a')]
    shelfOrder(rows)
    expect(rows.map((p) => p.name)).toEqual(['Erdos.b', 'Erdos.a'])
  })
})

describe('defaultTask', () => {
  it('is the first row of the one order — the address agrees with the list', () => {
    const rows = [
      task('Erdos.a', { last_event: '2026-08-30T00:00:00+00:00' }),
      task('Erdos.b', { status: 'stalled' }),
      task('Erdos.c', { status: 'awaiting_human' }),
    ]
    expect(defaultTask(rows)).toBe(shelfOrder(rows)[0].name)
  })

  it('is null for an empty shelf — an empty Project is legal', () => {
    expect(defaultTask([])).toBeNull()
  })

  it('takes what is blocked on the human before anything the engine owns', () => {
    const rows = [
      task('Erdos.a', { status: 'proving', in_flight: 2 }),
      task('Erdos.b', { status: 'awaiting_human' }),
    ]
    expect(defaultTask(rows)).toBe('Erdos.b')
  })

  it('then what is in motion, before what is merely recent', () => {
    const rows = [
      task('Erdos.a', { last_event: '2026-08-30T00:00:00+00:00' }),
      task('Erdos.b', { status: 'proving' }),
    ]
    expect(defaultTask(rows)).toBe('Erdos.b')
  })

  it('otherwise the most recently moved shelf-mate', () => {
    const rows = [
      task('Erdos.a', { last_event: '2026-08-01T00:00:00+00:00' }),
      task('Erdos.b', { last_event: '2026-08-30T00:00:00+00:00' }),
    ]
    expect(defaultTask(rows)).toBe('Erdos.b')
  })

  it('falls back to name order when nothing has ever happened', () => {
    const rows = [task('Erdos.b', { last_event: null }), task('Erdos.a', { last_event: null })]
    expect(defaultTask(rows)).toBe('Erdos.a')
  })
})

describe('tasksOf', () => {
  // Live bug, 2026-09-03: walking from Erdos to Combinatorics rewrote
  // the address to `/p/Combinatorics/groups/Erdos.p358`. The poll for
  // the new shelf had not answered yet, so the shell was still holding
  // Erdos's rows and "the default task" was computed from them. A row
  // belongs to a shelf by its FK, never by the request it arrived in.
  it('keeps only the rows filed on this shelf', () => {
    const rows = [task('Erdos.p1'), task('Comb.x', { project: 'Combinatorics' })]
    expect(tasksOf(rows, 'Combinatorics').map((r) => r.name)).toEqual(['Comb.x'])
  })

  it('is empty while the previous shelf is still in hand', () => {
    expect(tasksOf([task('Erdos.p1'), task('Erdos.p2')], 'Combinatorics')).toEqual([])
  })

  it('drops a row filed on no shelf at all rather than adopting it', () => {
    expect(tasksOf([task('Loose', { project: null })], 'Erdos')).toEqual([])
  })
})

describe('railVisible', () => {
  it('hides the task column when the Project holds one task (§1.4)', () => {
    expect(railVisible([task('Erdos.a')])).toBe(false)
    expect(railVisible([])).toBe(false)
  })
  it('shows it as soon as there is a choice to make', () => {
    expect(railVisible([task('Erdos.a'), task('Erdos.b')])).toBe(true)
  })
})

describe('the Timeline reads whole before it reads scoped', () => {
  // §1.4 makes the Timeline a Project surface whose secondary menu is
  // the task list, and `GET /api/projects/{p}/events` is the shelf-wide
  // feed that makes that possible. Before it existed the section had to
  // borrow a task's feed, so the address was rewritten to name one.
  it('an address with no task stays without one', () => {
    expect(TASK_SECTIONS).not.toContain('timeline')
    const r = parseProjectRoute(['p', 'Erdos', 'timeline'])
    expect(r).toMatchObject({ section: 'timeline', problem: null })
  })

  it('and still carries one when the reader picks a task', () => {
    expect(parseProjectRoute(['p', 'Erdos', 'timeline', 'Erdos.p1'])).toMatchObject({
      section: 'timeline',
      problem: 'Erdos.p1',
    })
    expect(projectPath('Erdos', 'timeline', 'Erdos.p1')).toBe('/p/Erdos/timeline/Erdos.p1')
  })
})
