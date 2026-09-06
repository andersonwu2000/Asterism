import { describe, expect, it } from 'vitest'
import {
  createFolder,
  defaultView,
  docAddress,
  docRefFromWorkspacePath,
  editable,
  editorFor,
  modeFor,
  isTextDoc,
  moveTargets,
  ownerOf,
  panelFor,
  parseDocAddress,
  railGroups,
  refKey,
  syncedScrollTop,
} from './docShell'
import type { PaperRow, RailInput } from './docShell'
import type { DocEntry, TheoryMeta } from './docShelf'

/*
 * The Documents tab's laws (docs_tab_spec.md §B): what the tab can
 * open, how that address is written and read back, which panel a file
 * earns, whose writing it is, and the five groups the rail draws.
 */

function file(path: string, theory?: TheoryMeta): DocEntry {
  return { path, kind: 'file', size: 1, ...(theory ? { theory } : {}) }
}
function dir(path: string): DocEntry {
  return { path, kind: 'dir' }
}
function meta(over: Partial<TheoryMeta> = {}): TheoryMeta {
  return {
    group_id: 5,
    created_at: '2026-09-04T16:12:00Z',
    status: 'accepted',
    rounds: 2,
    objective: 'what breaks the counting?',
    verdict: [],
    ...over,
  }
}
function paper(over: Partial<PaperRow> = {}): PaperRow {
  return {
    id: 'abc123',
    title: null,
    source_name: 'kelley.pdf',
    path: 'user/papers/abc123',
    area: 'user',
    ...over,
  }
}
function input(over: Partial<RailInput> = {}): RailInput {
  return { entries: [], papers: [], task: null, taskFiles: null, query: '', ...over }
}
function group(gs: ReturnType<typeof railGroups>, id: string) {
  return gs.find((g) => g.id === id)
}

describe('parseDocAddress', () => {
  it('reads a path under the person`s own area as a document', () => {
    expect(parseDocAddress(['user', 'notes', 'a.md'])).toEqual({
      kind: 'doc',
      path: 'user/notes/a.md',
    })
  })

  it('reads the Assistant`s area the same way', () => {
    expect(parseDocAddress(['agent', 'g5_x.md'])).toEqual({
      kind: 'doc',
      path: 'agent/g5_x.md',
    })
  })

  it('reads a task address as the engine`s writing for that task', () => {
    expect(parseDocAddress(['task', 'Erdos.p1', 'proofs', 'L_x.lean'])).toEqual({
      kind: 'task',
      task: 'Erdos.p1',
      path: 'proofs/L_x.lean',
    })
  })

  it('still reads the `shelf` links minted before the rewrite', () => {
    expect(parseDocAddress(['shelf', 'user', 'notes.md'])).toEqual({
      kind: 'doc',
      path: 'user/notes.md',
    })
  })

  it('reads a legacy `proofs` link as a task ref the screen must fill in', () => {
    // those links never named a task — they opened whichever task the
    // shelf happened to default to, which is the bug this shape records
    expect(parseDocAddress(['proofs', 'REPORT.md'])).toEqual({
      kind: 'task',
      task: null,
      path: 'REPORT.md',
    })
  })

  it('is null for an address that names nothing', () => {
    expect(parseDocAddress([])).toBeNull()
    expect(parseDocAddress(['shelf'])).toBeNull()
    expect(parseDocAddress(['task', 'Erdos.p1'])).toBeNull()
    expect(parseDocAddress(['whatever', 'x.md'])).toBeNull()
  })
})

describe('docAddress', () => {
  it('writes a document ref back as the address that reads it', () => {
    const ref = { kind: 'doc', path: 'user/notes/a.md' } as const
    expect(docAddress('Erdos', ref)).toBe('/p/Erdos/docs/user/notes/a.md')
    expect(parseDocAddress(['user', 'notes', 'a.md'])).toEqual(ref)
  })

  it('writes a task ref with the task in the address', () => {
    expect(
      docAddress('Erdos', { kind: 'task', task: 'Erdos.p1', path: 'proofs/L_x.lean' }),
    ).toBe('/p/Erdos/docs/task/Erdos.p1/proofs/L_x.lean')
  })

  it('encodes each segment, because a separator is structure', () => {
    expect(docAddress('E d', { kind: 'doc', path: 'user/a b/c#d.md' })).toBe(
      '/p/E%20d/docs/user/a%20b/c%23d.md',
    )
  })

  it('a task ref naming no task is not addressable — it lands on the section', () => {
    expect(docAddress('Erdos', { kind: 'task', task: null, path: 'REPORT.md' })).toBe(
      '/p/Erdos/docs',
    )
  })
})

/* The Timeline's theory rows carry the document they landed as a
 * WORKSPACE-relative path (`Problems/<project>/_docs/agent/x.md`, serve
 * `602c6614`); this tab addresses documents root-relative. One
 * translation, here, so the log's "read the document" link cannot mint
 * an address the tab reads back as something else. */
describe('docRefFromWorkspacePath', () => {
  it('reads a document under this project`s docs root as a doc ref', () => {
    expect(
      docRefFromWorkspacePath('Erdos', 'Problems/Erdos/_docs/agent/theory_5.md'),
    ).toEqual({ kind: 'doc', path: 'agent/theory_5.md' })
  })

  it('normalises the backslashes a Windows writer leaves in the path', () => {
    expect(
      docRefFromWorkspacePath('Erdos', 'Problems\\Erdos\\_docs\\agent\\theory_5.md'),
    ).toEqual({ kind: 'doc', path: 'agent/theory_5.md' })
  })

  it('mints an address the tab reads back as the same document', () => {
    const ref = docRefFromWorkspacePath('Erdos', 'Problems/Erdos/_docs/agent/n/a.md')
    expect(ref).not.toBeNull()
    // the address is `/p/<project>/docs/<rest…>`; the route hands the
    // tab exactly that tail
    const rest = docAddress('Erdos', ref!).split('/').slice(4).map(decodeURIComponent)
    expect(parseDocAddress(rest)).toEqual(ref)
  })

  it('refuses a document belonging to another project', () => {
    expect(docRefFromWorkspacePath('Erdos', 'Problems/Putnam/_docs/agent/a.md')).toBeNull()
  })

  it('refuses anything outside the docs root', () => {
    expect(docRefFromWorkspacePath('Erdos', 'Problems/Erdos/p1/PROGRAMME.md')).toBeNull()
  })

  it('refuses a docs path that names no area — an area is not optional', () => {
    expect(docRefFromWorkspacePath('Erdos', 'Problems/Erdos/_docs/a.md')).toBeNull()
    expect(docRefFromWorkspacePath('Erdos', 'Problems/Erdos/_docs/scratch/a.md')).toBeNull()
  })

  it('refuses an area with no file under it', () => {
    expect(docRefFromWorkspacePath('Erdos', 'Problems/Erdos/_docs/agent/')).toBeNull()
    expect(docRefFromWorkspacePath('Erdos', 'Problems/Erdos/_docs/agent')).toBeNull()
  })
})

describe('refKey', () => {
  it('separates one task`s file from another task`s file of the same name', () => {
    expect(refKey({ kind: 'task', task: 'A', path: 'REPORT.md' })).not.toBe(
      refKey({ kind: 'task', task: 'B', path: 'REPORT.md' }),
    )
  })

  it('separates a document from a task file of the same path', () => {
    expect(refKey({ kind: 'doc', path: 'REPORT.md' })).not.toBe(
      refKey({ kind: 'task', task: null, path: 'REPORT.md' }),
    )
  })
})

describe('panelFor', () => {
  it('gives markdown its render', () => {
    expect(panelFor('user/a.md')).toBe('render')
  })

  it('gives TeX the server`s compile', () => {
    expect(panelFor('user/a.tex')).toBe('pdf-render')
  })

  it('gives Lean the Info panel', () => {
    expect(panelFor('user/a.lean')).toBe('info')
  })

  it('gives plain text no panel — there is nothing to show beside it', () => {
    expect(panelFor('user/a.txt')).toBe('none')
  })

  it('gives a pdf the browser`s own viewer', () => {
    expect(panelFor('user/papers/x/paper.pdf')).toBe('viewer')
  })

  it('gives an image its picture', () => {
    expect(panelFor('user/a.png')).toBe('image')
    expect(panelFor('user/a.jpg')).toBe('image')
    expect(panelFor('user/a.svg')).toBe('image')
  })

  it('gives anything it does not know no panel at all', () => {
    expect(panelFor('user/a.json')).toBe('none')
    expect(panelFor('user/Makefile')).toBe('none')
  })

  it('reads the extension case-insensitively', () => {
    expect(panelFor('user/A.MD')).toBe('render')
  })
})

describe('isTextDoc', () => {
  it('is the four kinds the console can put in a box', () => {
    expect(['a.md', 'a.tex', 'a.txt', 'a.lean'].map(isTextDoc)).toEqual([
      true,
      true,
      true,
      true,
    ])
  })

  it('is not a pdf or an image — those are shown, not written', () => {
    expect(['a.pdf', 'a.png', 'a.json'].map(isTextDoc)).toEqual([false, false, false])
  })
})

describe('editable', () => {
  it('is the person`s own text, and only that', () => {
    expect(editable({ kind: 'doc', path: 'user/notes.md' })).toBe(true)
  })

  it('is false in the Assistant`s area — this door does not write it', () => {
    expect(editable({ kind: 'doc', path: 'agent/notes.md' })).toBe(false)
  })

  it('is false for the engine`s own writing', () => {
    expect(editable({ kind: 'task', task: 'Erdos.p1', path: 'Root.lean' })).toBe(false)
  })

  it('is false for a pdf the person owns — there is no box for it', () => {
    expect(editable({ kind: 'doc', path: 'user/papers/x/paper.pdf' })).toBe(false)
  })
})

describe('defaultView', () => {
  it('opens the person`s own document beside its panel', () => {
    expect(defaultView({ kind: 'doc', path: 'user/a.md' })).toBe('split')
    expect(defaultView({ kind: 'doc', path: 'user/a.tex' })).toBe('split')
    expect(defaultView({ kind: 'doc', path: 'user/a.lean' })).toBe('split')
  })

  it('opens read-only prose on its render — there is nothing to write', () => {
    expect(defaultView({ kind: 'doc', path: 'agent/a.md' })).toBe('render')
    expect(defaultView({ kind: 'task', task: 'p', path: 'REPORT.md' })).toBe('render')
  })

  it('opens read-only Lean split, because the caret still drives the Info panel', () => {
    expect(defaultView({ kind: 'task', task: 'p', path: 'Root.lean' })).toBe('split')
  })

  it('opens plain text as source — a document with no panel cannot split', () => {
    // the person's own .txt is editable, and split would mean a pane
    // with nothing in it
    expect(defaultView({ kind: 'doc', path: 'user/a.txt' })).toBe('source')
  })

  it('opens a pdf and an image on the panel that IS the document', () => {
    expect(defaultView({ kind: 'doc', path: 'user/a.pdf' })).toBe('render')
    expect(defaultView({ kind: 'doc', path: 'user/a.png' })).toBe('render')
  })
})

describe('ownerOf', () => {
  it('says nothing about the person`s own document — the settled norm earns no ink', () => {
    expect(ownerOf({ kind: 'doc', path: 'user/a.md' })).toBeNull()
  })

  it('names the theory layer when the listing carries its record', () => {
    expect(ownerOf({ kind: 'doc', path: 'agent/x.md' }, meta())).toBe(
      "the theory layer's — read-only",
    )
  })

  it('names the Assistant for everything else in its area', () => {
    expect(ownerOf({ kind: 'doc', path: 'agent/x.md' })).toBe(
      "the Assistant's — read-only",
    )
  })

  it('names the engine for a task`s own writing', () => {
    expect(ownerOf({ kind: 'task', task: 'Erdos.p1', path: 'Root.lean' })).toBe(
      "the engine's — read-only",
    )
  })
})

describe('railGroups — yours', () => {
  it('lists the person`s own tree, and never the area folder itself', () => {
    const gs = railGroups(
      input({ entries: [dir('user'), file('user/a.md'), dir('user/n'), file('user/n/b.md')] }),
    )
    expect(group(gs, 'yours')!.rows.map((r) => r.name)).toEqual(['a.md', 'n', 'b.md'])
  })

  it('takes the depth from the path, so the tree draws itself', () => {
    const gs = railGroups(input({ entries: [file('user/a.md'), file('user/n/b.md')] }))
    expect(group(gs, 'yours')!.rows.map((r) => r.depth)).toEqual([0, 1])
  })

  it('leaves papers out of it — they are their own group', () => {
    const gs = railGroups(
      input({
        entries: [
          file('user/a.md'),
          dir('user/papers'),
          dir('user/papers/abc123'),
          file('user/papers/abc123/text.md'),
        ],
      }),
    )
    expect(group(gs, 'yours')!.rows.map((r) => r.name)).toEqual(['a.md'])
  })

  it('renders even with nothing in it — the group is where a first file starts', () => {
    const gs = railGroups(input())
    expect(group(gs, 'yours')).toBeDefined()
    expect(group(gs, 'yours')!.rows).toEqual([])
  })

  it('is the one primary group', () => {
    const gs = railGroups(input({ task: 'p' }))
    expect(gs.filter((g) => !g.secondary).map((g) => g.id)).toEqual(['yours'])
  })
})

describe('railGroups — papers', () => {
  it('names a paper by its title when it has one, and its file name when it does not', () => {
    const gs = railGroups(
      input({
        papers: [
          paper({ id: 'a', path: 'user/papers/a', title: 'Compact spaces' }),
          paper({ id: 'b', path: 'user/papers/b', title: null, source_name: 'zorn.pdf' }),
        ],
      }),
    )
    expect(group(gs, 'papers')!.rows.map((r) => r.name)).toEqual([
      'Compact spaces',
      'zorn.pdf',
    ])
  })

  it('sorts by the name it shows, not by the id on disk', () => {
    const gs = railGroups(
      input({
        papers: [
          paper({ id: 'zzz', path: 'user/papers/zzz', title: 'Alpha' }),
          paper({ id: 'aaa', path: 'user/papers/aaa', title: 'Beta' }),
        ],
      }),
    )
    expect(group(gs, 'papers')!.rows.map((r) => r.name)).toEqual(['Alpha', 'Beta'])
  })

  it('nests the paper`s own files one deeper, in reading order', () => {
    const gs = railGroups(
      input({
        papers: [paper({ id: 'a', path: 'user/papers/a', title: 'A' })],
        entries: [
          dir('user/papers/a'),
          file('user/papers/a/map.md'),
          file('user/papers/a/paper.pdf'),
          file('user/papers/a/text.md'),
        ],
      }),
    )
    const rows = group(gs, 'papers')!.rows
    expect(rows.map((r) => [r.name, r.depth])).toEqual([
      ['A', 0],
      ['paper.pdf', 1],
      ['text.md', 1],
      ['map.md', 1],
    ])
  })

  it('never lists meta.json or the map spawn`s sandbox', () => {
    const gs = railGroups(
      input({
        papers: [paper({ id: 'a', path: 'user/papers/a', title: 'A' })],
        entries: [
          file('user/papers/a/meta.json'),
          dir('user/papers/a/.index_attempt'),
          file('user/papers/a/.index_attempt/notes.md'),
          file('user/papers/a/text.md'),
        ],
      }),
    )
    expect(group(gs, 'papers')!.rows.map((r) => r.name)).toEqual(['A', 'text.md'])
  })

  it('reads both areas — a paper the engine fetched is still a paper', () => {
    const gs = railGroups(
      input({
        papers: [
          paper({ id: 'a', path: 'user/papers/a', title: 'Mine', area: 'user' }),
          paper({ id: 'b', path: 'agent/papers/b', title: 'Theirs', area: 'agent' }),
        ],
      }),
    )
    expect(group(gs, 'papers')!.rows.map((r) => r.name)).toEqual(['Mine', 'Theirs'])
  })
})

describe('railGroups — agent', () => {
  it('reads the Assistant`s area as a log, newest first', () => {
    const gs = railGroups(
      input({
        entries: [
          dir('agent'),
          file('agent/a_old.md', meta({ created_at: '2026-09-01T09:00:00Z' })),
          file('agent/plain.md'),
          file('agent/z_new.md', meta({ created_at: '2026-09-04T16:12:00Z' })),
        ],
      }),
    )
    expect(group(gs, 'agent')!.rows.map((r) => r.name)).toEqual([
      'z_new.md',
      'a_old.md',
      'plain.md',
    ])
  })

  it('leaves the engine`s fetched papers to the papers group', () => {
    const gs = railGroups(
      input({
        entries: [
          file('agent/x.md'),
          dir('agent/papers'),
          file('agent/papers/b/text.md'),
        ],
      }),
    )
    expect(group(gs, 'agent')!.rows.map((r) => r.name)).toEqual(['x.md'])
  })

  it('carries the theory record onto the row that wears the page mark', () => {
    const gs = railGroups(input({ entries: [file('agent/x.md', meta())] }))
    expect(group(gs, 'agent')!.rows[0].theory).toEqual(meta())
  })
})

describe('railGroups — engine', () => {
  it('is absent when no task is chosen — there is no writing to list', () => {
    expect(group(railGroups(input()), 'engine')).toBeUndefined()
  })

  it('reads the task`s files in the order a person opens them', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: {
          problem_files: [
            'BRIEF.md',
            'Defs.lean',
            'PROGRAMME.md',
            'REPORT.md',
            'Root.lean',
            'TREE.md',
          ],
          proof_files: [],
          hasReport: true,
        },
      }),
    )
    expect(group(gs, 'engine')!.rows.map((r) => r.name)).toEqual([
      'REPORT.md',
      'PROGRAMME.md',
      'BRIEF.md',
      'TREE.md',
      'Root.lean',
      'Defs.lean',
    ])
  })

  it('omits a file the task never wrote', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: {
          problem_files: ['PROGRAMME.md', 'Root.lean'],
          proof_files: [],
          hasReport: false,
        },
      }),
    )
    expect(group(gs, 'engine')!.rows.map((r) => r.name)).toEqual([
      'PROGRAMME.md',
      'Root.lean',
    ])
  })

  it('holds REPORT.md back until the DB says one was written', () => {
    // the file may sit on disk from an earlier run; `ingest_report` is
    // the SoT and the file is its render
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: {
          problem_files: ['REPORT.md', 'Root.lean'],
          proof_files: [],
          hasReport: false,
        },
      }),
    )
    expect(group(gs, 'engine')!.rows.map((r) => r.name)).toEqual(['Root.lean'])
  })

  it('puts anything else the task wrote after the six, alphabetically', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: {
          problem_files: ['Notes.md', 'Aux.lean', 'Root.lean'],
          proof_files: [],
          hasReport: false,
        },
      }),
    )
    expect(group(gs, 'engine')!.rows.map((r) => r.name)).toEqual([
      'Root.lean',
      'Aux.lean',
      'Notes.md',
    ])
  })

  it('addresses each row at the task whose writing it is', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: { problem_files: ['Root.lean'], proof_files: [], hasReport: false },
      }),
    )
    expect(group(gs, 'engine')!.rows[0].ref).toEqual({
      kind: 'task',
      task: 'Erdos.p1',
      path: 'Root.lean',
    })
  })
})

describe('railGroups — proofs', () => {
  it('counts what the task proved', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: {
          problem_files: [],
          proof_files: ['L_a.lean', 'L_b.lean', 'c.lean'],
          hasReport: false,
        },
      }),
    )
    expect(group(gs, 'proofs')!.count).toBe(3)
  })

  it('drops the brick prefix from the name and keeps the path in the ref', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: { problem_files: [], proof_files: ['L_a.lean'], hasReport: false },
      }),
    )
    const row = group(gs, 'proofs')!.rows[0]
    expect(row.name).toBe('a.lean')
    expect(row.ref).toEqual({
      kind: 'task',
      task: 'Erdos.p1',
      path: 'proofs/L_a.lean',
    })
  })
})

describe('railGroups — the filter', () => {
  it('keeps only the rows whose name carries the query, whatever its case', () => {
    const gs = railGroups(
      input({
        entries: [file('user/Notes.md'), file('user/plan.md')],
        query: 'note',
      }),
    )
    expect(group(gs, 'yours')!.rows.map((r) => r.name)).toEqual(['Notes.md'])
  })

  it('drops a folder that matches nothing', () => {
    const gs = railGroups(
      input({
        entries: [dir('user/n'), file('user/n/plan.md')],
        query: 'plan',
      }),
    )
    expect(group(gs, 'yours')!.rows.map((r) => r.name)).toEqual(['plan.md'])
  })

  it('drops a group left with nothing — including the person`s own', () => {
    const gs = railGroups(
      input({
        entries: [file('user/a.md'), file('agent/plan.md')],
        query: 'plan',
      }),
    )
    expect(gs.map((g) => g.id)).toEqual(['agent'])
  })

  it('counts what it shows, not what it hid', () => {
    const gs = railGroups(
      input({
        task: 'Erdos.p1',
        taskFiles: {
          problem_files: [],
          proof_files: ['L_a.lean', 'L_b.lean'],
          hasReport: false,
        },
        query: 'a.lean',
      }),
    )
    expect(group(gs, 'proofs')!.count).toBe(1)
  })
})

describe('createFolder', () => {
  it('starts a new thing inside the folder that is open', () => {
    expect(createFolder({ kind: 'doc', path: 'user/n' }, true)).toBe('user/n')
  })

  it('starts it beside the file that is open', () => {
    expect(createFolder({ kind: 'doc', path: 'user/n/a.md' }, false)).toBe('user/n')
  })

  it('starts it at the area root when nothing of the person`s is open', () => {
    // a selection in another group never redirects a create into it
    expect(createFolder(null, false)).toBe('user')
    expect(createFolder({ kind: 'task', task: 'p', path: 'Root.lean' }, false)).toBe('user')
    expect(createFolder({ kind: 'doc', path: 'agent/x.md' }, false)).toBe('user')
  })

  it('never starts one inside a paper — that folder is the shelf`s', () => {
    expect(createFolder({ kind: 'doc', path: 'user/papers/abc/text.md' }, false)).toBe(
      'user',
    )
  })
})

describe('moveTargets', () => {
  it('offers the area itself first, then the folders under it', () => {
    expect(
      moveTargets([dir('user/n'), dir('user/n/deep'), file('user/a.md')], 'user/a.md', 'file'),
    ).toEqual(['user/n', 'user/n/deep'])
  })

  it('never offers the folder the thing is already in', () => {
    expect(moveTargets([dir('user/n')], 'user/n/a.md', 'file')).toEqual(['user'])
  })

  it('never offers a folder itself, nor anything inside it', () => {
    expect(
      moveTargets([dir('user/n'), dir('user/n/deep'), dir('user/m')], 'user/n', 'dir'),
    ).toEqual(['user/m'])
  })

  it('does not offer the papers area — a paper is a folder of its own', () => {
    expect(
      moveTargets(
        [dir('user/papers'), dir('user/papers/abc'), dir('user/m'), dir('user/n')],
        'user/n/a.md',
        'file',
      ),
    ).toEqual(['user', 'user/m'])
  })
})

describe('which editor a document earns', () => {
  it('paints what it has a painter for, and nothing it does not', () => {
    // The console has exactly two tokenizers — the Lean one and the
    // markdown one — and until now the Documents tab used neither:
    // every file the person could edit got a bare textarea, while the
    // task page's own markdown was coloured (owner, 2026-09-06).
    expect(editorFor('user/notes.md')).toBe('markdown')
    expect(editorFor('user/Root.lean')).toBe('lean')
    // a painter that does not know the language would paint it WRONG —
    // `#` opens no heading in TeX, and a backtick opens no Lean span
    expect(editorFor('user/paper.tex')).toBe('plain')
    expect(editorFor('user/raw.txt')).toBe('plain')
  })
})

/*
 * `.md` and `.tex` must OPERATE alike (owner, 2026-09-06): the same tab
 * set, the same save, the same check, the same following render. They
 * had drifted into two branches of the shell — markdown had no bar over
 * its render at all, TeX had no painter under its caret — so the table
 * below is where the two now differ, and every difference in it has to
 * be a difference in the medium rather than in the code that grew.
 */
describe('the document mode table', () => {
  it('offers the same three tabs for prose and for TeX', () => {
    expect(modeFor('user/a.md').third).toBe('render')
    expect(modeFor('user/a.tex').third).toBe('render')
  })

  it('offers a check on both — the painter one side, the engine the other', () => {
    expect(modeFor('user/a.md').check).toBe('prose')
    expect(modeFor('user/a.tex').check).toBe('tex')
  })

  it('paints the source in the language`s own painter, or not at all', () => {
    expect(modeFor('user/a.md').editor).toBe('markdown')
    expect(modeFor('user/a.lean').editor).toBe('lean')
    // `#` opens no heading in TeX — a painter that does not know the
    // language paints it wrong
    expect(modeFor('user/a.tex').editor).toBe('plain')
  })

  it('follows the writing wherever the render pane is ours to drive', () => {
    expect(modeFor('user/a.md').scrollSync).toBe(true)
    // a compiled pdf lives in the browser's own viewer, which takes no
    // instruction from this page
    expect(modeFor('user/a.tex').scrollSync).toBe(false)
  })

  it('is the one source panelFor and editorFor read', () => {
    for (const path of ['a.md', 'a.tex', 'a.lean', 'a.txt', 'a.pdf', 'a.png', 'Makefile']) {
      expect(panelFor(path)).toBe(modeFor(path).panel)
      expect(editorFor(path)).toBe(modeFor(path).editor)
    }
  })

  it('gives a language it does not know the plain row', () => {
    expect(modeFor('user/a.json')).toEqual(modeFor('user/a.txt'))
  })
})

/* The render pane follows the editor. A rendered document is a
 * different LENGTH from its source, so the mapping is proportional on
 * each pane's own scrollable range: the ends meet, which is the only
 * part of it a reader can check at a glance. */
describe('syncedScrollTop', () => {
  const source = { scrollTop: 0, scrollHeight: 2000, clientHeight: 500 }
  const target = { scrollHeight: 3000, clientHeight: 600 }

  it('puts the top of the render at the top of the source', () => {
    expect(syncedScrollTop({ ...source, scrollTop: 0 }, target)).toBe(0)
  })

  it('puts the bottom at the bottom, whatever the two lengths are', () => {
    expect(syncedScrollTop({ ...source, scrollTop: 1500 }, target)).toBe(2400)
  })

  it('maps the middle proportionally, not by pixels', () => {
    expect(syncedScrollTop({ ...source, scrollTop: 750 }, target)).toBe(1200)
  })

  it('leaves the render alone when the source has nothing to scroll', () => {
    expect(
      syncedScrollTop({ scrollTop: 0, scrollHeight: 400, clientHeight: 500 }, target),
    ).toBe(0)
    expect(
      syncedScrollTop(source, { scrollHeight: 400, clientHeight: 600 }),
    ).toBe(0)
  })

  it('never asks for a position outside the render (rubber-band scroll)', () => {
    expect(syncedScrollTop({ ...source, scrollTop: -80 }, target)).toBe(0)
    expect(syncedScrollTop({ ...source, scrollTop: 1800 }, target)).toBe(2400)
  })
})

describe('the split divider — where the reader put it', () => {
  it('keeps both panes readable, whatever is dragged', async () => {
    const { SPLIT_MIN, clampSplit } = await import('./docShell')
    // a pane dragged to nothing is not a layout, it is a lost pane
    expect(clampSplit(0.5)).toBe(0.5)
    expect(clampSplit(0)).toBe(SPLIT_MIN)
    expect(clampSplit(1)).toBe(1 - SPLIT_MIN)
    expect(clampSplit(-4)).toBe(SPLIT_MIN)
    // a ratio that is not a number at all leaves the default standing
    expect(clampSplit(Number.NaN)).toBe(0.5)
  })

  it('walks the same grammar with keys as with the pointer', async () => {
    const { SPLIT_MIN, splitStep } = await import('./docShell')
    expect(splitStep(0.5, 'ArrowRight')).toBeCloseTo(0.52)
    expect(splitStep(0.5, 'ArrowLeft')).toBeCloseTo(0.48)
    expect(splitStep(SPLIT_MIN, 'ArrowLeft')).toBe(SPLIT_MIN)
    expect(splitStep(0.5, 'Home')).toBe(SPLIT_MIN)
    expect(splitStep(0.5, 'End')).toBe(1 - SPLIT_MIN)
    // every other key belongs to whoever else wants it
    expect(splitStep(0.5, 'ArrowUp')).toBeNull()
    expect(splitStep(0.5, 'a')).toBeNull()
  })

  it('remembers per viewer, and reads 50/50 when nothing can be stored', async () => {
    const { SPLIT_KEY, readSplit, writeSplit } = await import('./docShell')
    const store = new Map<string, string>()
    const g = globalThis as unknown as { localStorage?: unknown }
    const had = 'localStorage' in g
    g.localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    }
    try {
      expect(readSplit()).toBe(0.5)
      writeSplit(0.34)
      expect(store.get(SPLIT_KEY)).toBe('0.34')
      expect(readSplit()).toBe(0.34)
      // a stored value is still bound by the law
      store.set(SPLIT_KEY, '0.99')
      expect(readSplit()).toBe(0.8)
      store.set(SPLIT_KEY, 'wide please')
      expect(readSplit()).toBe(0.5)
      // a private window, cleared site data, a browser that refuses:
      // the page still lays out, it just does not remember
      g.localStorage = {
        getItem: () => { throw new Error('denied') },
        setItem: () => { throw new Error('denied') },
      }
      expect(readSplit()).toBe(0.5)
      expect(() => writeSplit(0.4)).not.toThrow()
    } finally {
      if (had) delete g.localStorage
      else delete g.localStorage
    }
  })
})
