import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

/*
 * Read-only smoke over ANY workspace state - a fresh reset, an idle
 * engine, or a mid-run live one. Assertions never bind to specific
 * projects, tasks, counts or engine state: they check structure (a row
 * or its empty state, a label that renders either way) and skip
 * gracefully where population is genuinely required.
 *
 * Every address here is the Project shell's (human_interface_design.md
 * 1.4): #/ is the picker, #/p/<project>/<section>[/<task>] is inside
 * one. The old top-level board, library, run and inbox routes are gone.
 */

interface Shelf {
  project: string
  task: string
}

// A reading test must not trigger a model refresh, command or save as
// a side effect of opening a panel. Enforce the promise above in the
// browser, rather than relying on every component to remain read-only.
test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', route => route.request().method() === 'GET'
    ? route.fallback()
    : route.fulfill({ status: 403, json: { detail: 'Read-only smoke test' } }))
})

/** A populated Project and one of its tasks. What the workspace holds
 * is not this suite's business, so the address comes from the API — the
 * SMALLEST shelf that meets the bar, so the pages under test stay light
 * and the choice is deterministic across workspaces. */
async function firstShelf(
  request: APIRequestContext,
  minTasks = 1,
): Promise<Shelf | null> {
  const r = await request.get('/api/projects')
  if (!r.ok()) return null
  const projects: { name: string; problems: number }[] = (await r.json()).projects ?? []
  const fit = projects
    .filter((p) => p.problems >= minTasks)
    .sort((a, b) => a.problems - b.problems || a.name.localeCompare(b.name))[0]
  if (!fit) return null
  const t = await request.get(`/api/problems?project=${encodeURIComponent(fit.name)}`)
  if (!t.ok()) return null
  const rows: { name: string }[] = (await t.json()).problems ?? []
  if (rows.length === 0) return null
  return { project: fit.name, task: rows[0].name }
}

const at = (project: string, section: string, task?: string) =>
  `/#/p/${encodeURIComponent(project)}/${section}` +
  (task ? `/${encodeURIComponent(task)}` : '')

/** Open a populated shelf, or skip. */
async function openShelf(
  page: Page,
  request: APIRequestContext,
  section: string,
  withTask = true,
  minTasks = 1,
): Promise<Shelf> {
  const shelf = await firstShelf(request, minTasks)
  test.skip(shelf === null, 'needs a workspace with at least one task')
  const s = shelf as Shelf
  await page.goto(at(s.project, section, withTask ? s.task : undefined))
  return s
}

test('picker: project tiles, or the empty shelf', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Asterism').first()).toBeVisible()
  // a tile per Project, or the one affordance a workspace with none has
  const tiles = page.locator('main a[href^="#/p/"]')
  const mint = page.getByRole('button', { name: 'new project' })
  // `.first()` on the union too: `or` is a union of LOCATORS, so on a
  // workspace that has both it resolves to two elements and strict
  // mode refuses the assertion
  await expect(tiles.first().or(mint).first()).toBeVisible()
  // the picker has NO menu: the gear and the help glyph, and nothing
  // else (1.4-1)
  await expect(page.locator('main nav')).toHaveCount(0)
})

test('project shell: six sections, two corner glyphs', async ({ page, request }) => {
  await openShelf(page, request, 'tasks', false, 2)
  const menu = page.locator('[data-menu] a')
  await expect(menu).toHaveCount(6)
  expect(await menu.allInnerTexts()).toEqual([
    'Tasks',
    'Sky',
    'Groups',
    'Engine',
    'Timeline',
    'Documents',
  ])
  // the owner's ruling is a NUMBER, so the test counts (1.4-2)
  await expect(page.locator('[data-corner] > *')).toHaveCount(2)
})

test('shelf: tasks listed, and the filter narrows them', async ({ page, request }) => {
  await openShelf(page, request, 'tasks', false, 2)
  const rows = page.locator('tr[data-kind="task"]')
  await expect(rows.first()).toBeVisible()
  const total = await rows.count()
  const first = (await rows.first().locator('a').first().innerText()).trim()
  await page.getByPlaceholder('filter tasks…').fill(first)
  await expect.poll(async () => rows.count()).toBeLessThanOrEqual(total)
  await expect(rows.first()).toContainText(first)
})

test('shelf: run control refuses to start with nothing ticked', async ({
  page,
  request,
}) => {
  // the multi-task run takes an EXPLICIT list (3.3) - an empty one is
  // not a run over everything, so the button is closed until a task is
  // chosen
  await openShelf(page, request, 'tasks', false)
  const run = page.getByRole('button', { name: /^Run/ })
  const stop = page.getByRole('button', { name: /Stop/ })
  const live = await stop
    .waitFor({ timeout: 2000 })
    .then(() => true)
    .catch(() => false)
  test.skip(live, 'the engine is running - Stop is showing, not Run')
  await expect(run).toBeDisabled()
})

test('sky: the constellation renders, or says why it cannot', async ({
  page,
  request,
}) => {
  const s = await openShelf(page, request, 'sky')
  await expect(page.getByRole('button', { name: 'map', exact: true })).toBeVisible()
  const sky = page.locator('main svg.constellation')
  const noGoals = page.getByText(/No goals yet|the engine is working/)
  await expect(sky.or(noGoals).first()).toBeVisible({ timeout: 15000 })
  // the list view is the same data, not another page
  const proved = page.getByText(/\d+\/\d+ proved/)
  if (await sky.count()) {
    await expect(proved.first()).toBeVisible()
    await page.getByRole('button', { name: 'list', exact: true }).click()
    await expect(page.locator('table')).toBeVisible()
  }
  expect(page.url()).toContain(encodeURIComponent(s.task))
})

test('engine: slots, plan usage, engine log', async ({ page, request }) => {
  await openShelf(page, request, 'engine', false)
  await expect(page.getByText('slots')).toBeVisible()
  // idle or live, the room says which - never a blank panel
  await expect(
    page
      .getByText(/the engine is not running|none this instant|none yet|busy/)
      .first(),
  ).toBeVisible()
  await expect(page.getByText(/plan usage|engine log/).first()).toBeVisible()
})

test('timeline and documents render inside the shell', async ({ page, request }) => {
  const s = await openShelf(page, request, 'timeline')
  await expect(page.locator('[data-menu] a').first()).toBeVisible()
  await page.goto(at(s.project, 'docs'))
  // the two root buttons ('proofs' / 'documents') went with the
  // 2026-09-04 rewrite: the tab is ONE rail whose groups are the kinds
  // of writing, and the person's own is the primary one
  await expect(page.getByPlaceholder('find by name')).toBeVisible()
  await expect(page.getByRole('treeitem', { name: /yours/ })).toBeVisible()
})

test('legacy problem address redirects into its Project', async ({ page, request }) => {
  // links minted before the shell (a chat citation, a bookmark) must
  // still open - and the shelf comes from the DB, never from splitting
  // the name (3.1)
  const shelf = await firstShelf(request)
  test.skip(shelf === null, 'needs a workspace with at least one task')
  const s = shelf as Shelf
  await page.goto(`/#/problems/${encodeURIComponent(s.task)}`)
  await expect.poll(() => page.url(), { timeout: 10000 }).toContain('#/p/')
  expect(page.url()).toContain(encodeURIComponent(s.project))
})

test('settings: a window over the page, not a page of its own', async ({ page }) => {
  // the gear stopped being an address (assistant_redesign_2026-09-06
  // 5): the reader keeps their place, so the assertion is that the
  // sections are ON SCREEN and the address never moved
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Settings' }).click()
  const sheet = page.locator('.fixed.inset-0')
  await expect(sheet.getByText('Settings', { exact: true })).toBeVisible()
  await expect(sheet.getByText('Machine', { exact: true })).toBeVisible()
  await expect(sheet.getByText('Appearance', { exact: true })).toBeVisible()
  await expect(sheet.getByText('Shut down', { exact: true })).toBeVisible()
  expect(page.url()).not.toContain('settings')
  // the RUN parameters are NOT here (owner: what changes every run is
  // not hidden in settings)
  await expect(page.getByText('formalizer.model')).toHaveCount(0)
})

test('the old settings address opens the window and steps out of the way', async ({
  page,
}) => {
  // a bookmark minted while it was a page still works, and leaves the
  // reader on the picker rather than on an address that is gone
  await page.goto('/#/settings')
  await expect(page.locator('.fixed.inset-0').getByText('Shut down', { exact: true })).toBeVisible()
  await expect.poll(() => page.url()).not.toContain('settings')
})

test('the Assistant answers Ctrl+/', async ({ page, request }) => {
  await openShelf(page, request, 'tasks', false)
  const panel = page.locator('[aria-label="assistant"]')
  // the drawer's open state is remembered, so start from closed
  if (await panel.isVisible()) await page.keyboard.press('Control+/')
  await expect(panel).toBeHidden()
  await page.keyboard.press('Control+/')
  await expect(panel).toBeVisible()
  // its conversations open in place, under the header — on demand,
  // through the fold toggle (a closed fold renders nothing, which is
  // what let the old label collision pass as a false green)
  await panel.getByRole('button', { name: 'conversations' }).click()
  await expect(panel.getByLabel('conversation list')).toBeVisible()
})

test('the Assistant header names the conversation and nothing else', async ({
  page,
  request,
}) => {
  await openShelf(page, request, 'tasks', false)
  const panel = page.locator('[aria-label="assistant"]')
  if (!(await panel.isVisible())) await page.keyboard.press('Control+/')
  await expect(panel).toBeVisible()

  // the header is the conversation's name. Which page the question is
  // about is the address's job and the panel already follows it — said
  // twice, it was just a suffix eating the title's room (owner,
  // 2026-09-06)
  await expect(panel.getByText(/^about /)).toHaveCount(0)

  // the fold toggle speaks the console's own fold glyph (▸ closed, ▾
  // open — every other fold on every other screen), and it is not
  // written in the faintest ink there is: a control the reader has to
  // find is not settled chrome
  const toggle = panel.getByRole('button', { name: 'conversations' })
  await expect(toggle).toHaveText('▸')
  const inks = await page.evaluate(() => {
    const s = getComputedStyle(document.documentElement)
    return {
      faint: s.getPropertyValue('--color-ink-faint').trim(),
      dim: s.getPropertyValue('--color-ink-dim').trim(),
    }
  })
  const rgb = (hex: string) => {
    const h = hex.replace('#', '')
    return `rgb(${parseInt(h.slice(0, 2), 16)}, ${parseInt(h.slice(2, 4), 16)}, ${parseInt(
      h.slice(4, 6),
      16,
    )})`
  }
  await expect(toggle).toHaveCSS('color', rgb(inks.dim))
  expect(rgb(inks.dim)).not.toBe(rgb(inks.faint))
  await toggle.click()
  await expect(toggle).toHaveText('▾')
})

test('the Assistant model picker is two levels, not a flat list', async ({
  page,
  request,
}) => {
  await openShelf(page, request, 'tasks', false)
  const panel = page.locator('[aria-label="assistant"]')
  if (!(await panel.isVisible())) await page.keyboard.press('Control+/')
  await expect(panel).toBeVisible()

  await panel.getByRole('button', { name: 'model', exact: true }).click()
  const menu = panel.locator('[data-model-menu]')
  await expect(menu).toBeVisible()

  // a machine has BACKENDS and a backend ships models: both levels are
  // drawn, and the models sit further in than the header above them
  const headers = menu.locator('[data-provider-header]')
  await expect(headers.first()).toBeVisible()
  const options = menu.getByRole('option')
  await expect(options.first()).toBeVisible()
  // the TEXT's left edge, not the row box's: both rows span the menu,
  // and it is the writing that steps in
  const textLeft = (el: Element) =>
    el.getBoundingClientRect().x + parseFloat(getComputedStyle(el).paddingLeft)
  const headLeft = await headers.first().evaluate(textLeft)
  const optLeft = await options.first().evaluate(textLeft)
  expect(optLeft).toBeGreaterThan(headLeft)

  // the caveats are the PROVIDER's, so they ride its header — never
  // repeated onto each of its models
  const noteOnHeader = await headers.allInnerTexts()
  for (const t of await options.allInnerTexts()) {
    expect(t).not.toMatch(/list not live|not installed/)
  }
  expect(noteOnHeader.length).toBeGreaterThan(0)
  await page.keyboard.press('Escape')
  await expect(menu).toBeHidden()
})

test('run parameters live beside Run, not in settings', async ({ page, request }) => {
  await openShelf(page, request, 'tasks', false)
  await page.getByRole('button', { name: /run parameters/ }).click()
  await expect(page.getByText('formalizer.model')).toBeVisible()
  await expect(page.getByText('dispatch.budget_sec')).toBeVisible()
  // and the machine's own knobs are not
  await expect(page.getByText('dispatch.pool')).toHaveCount(0)
})

test('the Library is not reachable from anywhere', async ({ page }) => {
  // 1.4-3: the Library's surfaces come down until the owner tests the
  // wind. A dead route must not render a screen either.
  await page.goto('/#/library')
  await expect(page.getByRole('heading', { name: 'Library' })).toHaveCount(0)
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Library' })).toHaveCount(0)
})

test('the papers page is not reachable from anywhere', async ({ page }) => {
  // §3.9: the workspace-global shelf retired — a paper is one of its
  // Project's documents. A dead route must not render a screen either.
  await page.goto('/#/papers')
  await expect(page.getByRole('heading', { name: 'Papers' })).toHaveCount(0)
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Papers' })).toHaveCount(0)
})

test("Documents is where a paper is shelved", async ({ page, request }) => {
  // §3.9: the drop target and the "paper" affordance live on the
  // Project's own document column, and the areas it writes are named
  // there.
  const shelf = await firstShelf(request)
  test.skip(!shelf, 'needs a workspace with a Project')
  // `docs/shelf` was the second root's address; the tab has one address
  // now and the affordance sits on the `papers` group's header
  await page.goto(`/#/p/${encodeURIComponent(shelf!.project)}/docs`)
  await expect(page.getByTitle(/shelve a paper/)).toBeVisible()
})

test('api meta reachable and shaped', async ({ request }) => {
  const r = await request.get('/api/meta')
  expect(r.ok()).toBeTruthy()
  const body = await r.json()
  expect(body).toHaveProperty('workspace')
  expect(body).toHaveProperty('daemon')
  expect(['ok', 'missing', 'behind', 'unavailable']).toContain(body.db)
})

test('new-task form renders (read-only: no submit)', async ({ page }) => {
  await page.goto('/#/new')
  await expect(page.getByRole('heading', { name: 'New task' })).toBeVisible()
  await expect(page.getByPlaceholder('Topology.my_theorem')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create task' })).toBeDisabled()
})

test('new-task: the paper shelf is a window, not a wall', async ({
  page,
  request,
}) => {
  // The picker used to render one checkbox per shelved paper, which
  // buried the rest of the form (owner, 2026-08-27). It is a floating
  // window now: collapsed the field is one button, and choosing marks
  // a paper in place rather than moving it. Read-only — no submit.
  //
  // Addressed at a PROJECT (§3.9): the shelf on offer is the one the
  // task will be filed on, so `#/new` with nothing typed has none.
  const shelf = await firstShelf(request)
  test.skip(!shelf, 'needs a workspace with a Project')
  await page.goto(`/#/new/${encodeURIComponent(shelf!.project)}`)
  const open = page.locator('[data-paper-open]')
  const shelved = await open
    .waitFor({ timeout: 5000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!shelved, 'needs a workspace with a paper shelf')

  // shut: the wall is gone — no checkbox, and no list at all
  expect(await page.locator('input[type="checkbox"]').count()).toBe(0)
  const options = page.locator('[data-paper-option]')
  await expect(options).toHaveCount(0)

  await open.click()
  await expect(options.first()).toBeVisible()
  const all = await options.count()
  expect(all).toBeGreaterThan(0)

  // search narrows, and a query nothing matches says so rather than
  // leaving an empty box
  const search = page.getByPlaceholder(/search \d+ papers/)
  await search.fill('zzzzz-no-such-paper')
  await expect(page.getByText('nothing on the shelf matches')).toBeVisible()
  await search.fill('')
  await expect(options).toHaveCount(all)

  // taking one marks it IN PLACE (the row must not jump away under
  // the cursor) and raises a chip on the form behind
  const first = (await options.first().locator('[data-paper-name]').innerText()).trim()
  await options.first().click()
  await expect(page.locator('[data-paper-option][data-bound]')).toHaveCount(1)
  await expect(options).toHaveCount(all)
  await expect(page.locator('[data-paper-chip]')).toHaveCount(1)

  // Escape closes any floating surface; the chip survives it and
  // drops the paper on click
  await page.keyboard.press('Escape')
  await expect(options).toHaveCount(0)
  const chip = page.locator('[data-paper-chip]')
  await expect(chip.first()).toContainText(first)
  await chip.first().click()
  await expect(chip).toHaveCount(0)
})

test('new-task: Defs and Root wear the shared Lean block', async ({ page }) => {
  // They had grown their own arrangement — a bare editor per box and
  // ONE goal panel below both — and a first fix only imitated the
  // probe's shape instead of using it (68a344a3, reverted). Both now
  // render `LeanBlock`, the same component the chapter and console
  // probes do. Safe against a live engine: with both boxes empty the
  // session stays disabled, so no Lean slot is claimed.
  await page.goto('/#/new')
  await page.getByRole('button', { name: /pin exact Lean/ }).click()
  const boxes = page.locator('textarea[placeholder*="namespace Problems."]')
  await expect(boxes).toHaveCount(2)
  // the block's frame is the container rung over the wash ground —
  // the editor is frameless inside it, never bare on the page
  for (let i = 0; i < 2; i++) {
    await expect(
      boxes.nth(i).locator('xpath=ancestor::div[contains(@class,"bg-wash")][1]'),
    ).toHaveCount(1)
  }
  // nothing to report yet, so no InfoView and no orphaned goal panel
  await expect(page.getByText('goal at cursor')).toHaveCount(0)
})

test('timeline: a revision row opens onto the judge that ruled on it', async ({
  page,
  request,
}) => {
  // The judge changed shape on 2026-08-29 (calibration survey, knives
  // 0+1): a criterion takes a LIST of bullets, a killed proposal keeps
  // the verdict that killed it instead of a hard-coded NULL, and every
  // `clear` carries its reason. None of it was reachable from the
  // console — this row is where it landed.
  const list = await request.get('/api/problems')
  const rows: { name: string; goals: { total: number } }[] = list.ok()
    ? ((await list.json()).problems ?? [])
    : []
  rows.sort((a, b) => (b.goals?.total ?? 0) - (a.goals?.total ?? 0))
  let target: string | null = null
  for (const r of rows.slice(0, 6)) {
    const ev = await request.get(
      `/api/problems/${encodeURIComponent(r.name)}/events`,
    )
    if (!ev.ok()) continue
    const events: { object_kind: string; rev_id?: number | null }[] =
      (await ev.json()).events ?? []
    if (events.some((e) => e.object_kind === 'programme' && e.rev_id)) {
      target = r.name
      break
    }
  }
  test.skip(target === null, 'no workspace problem has argued a Programme')

  // Prefer a revision where a criterion carries MORE THAN ONE bullet:
  // that is the shape the 2026-08-28 list schema introduced, and a
  // renderer that shows the first and drops the rest passes every other
  // check in this test. Any revision will do when the workspace has no
  // such row yet.
  const ev = await request.get(
    `/api/problems/${encodeURIComponent(target as string)}/events`,
  )
  const ids: number[] = ((await ev.json()).events ?? [])
    .filter((e: { object_kind: string; rev_id?: number | null }) =>
      e.object_kind === 'programme' && e.rev_id)
    .map((e: { rev_id: number }) => e.rev_id)
  let listy: number | null = null
  for (const id of ids.slice(0, 14)) {
    const r = await request.get(
      `/api/problems/${encodeURIComponent(target as string)}/programme/verdict/${id}`,
    )
    if (!r.ok()) continue
    const v: { criteria: { bullets: string[] }[] } = await r.json()
    if ((v.criteria ?? []).some((c) => c.bullets.length > 1)) {
      listy = id
      break
    }
  }

  const where = await request.get('/api/problems')
  const shelfOf: { name: string; project: string | null }[] =
    (await where.json()).problems ?? []
  const project = shelfOf.find((r) => r.name === target)?.project
  test.skip(!project, 'the task is on no shelf')
  await page.goto(
    `/#/p/${encodeURIComponent(project as string)}/timeline/${encodeURIComponent(
      target as string,
    )}`,
  )
  const row =
    listy === null
      ? page.locator('[data-verdict-row]').first()
      : page.locator(`[data-verdict-row="${listy}"]`).first()
  await expect(row).toBeVisible({ timeout: 30000 })
  // the far left of the row: the object's NAME carries its own click
  // (it follows the log), and hitting the row's centre lands on it
  await row.click({ position: { x: 6, y: 6 } })

  // it always answers: the ruling, or the fact that this one predates
  // the record. A revision row that opens onto nothing is the bug this
  // whole read exists to end.
  const block = page.locator('[data-verdict="read"], [data-verdict="none"]').first()
  await expect(block).toBeVisible({ timeout: 30000 })
  if ((await block.getAttribute('data-verdict')) === 'none') return

  // the rubric's five criteria, named and in its own order
  const crit = page.locator('[data-criterion]')
  await expect(crit).toHaveCount(5)
  expect(
    await crit.evaluateAll((els) =>
      els.map((e) => e.getAttribute('data-criterion')),
    ),
  ).toEqual(['1', '2', '3', '4', '5'])

  // a criterion is a LIST: however many bullets the judge wrote, that
  // many render. The one-string schema bound in 4,495 of 4,495 rounds
  // and hid ~22% of objections for a round; a reader shown the first
  // bullet is in the same position.
  for (const c of await crit.all()) {
    const n = Number(await c.getAttribute('data-bullets'))
    if (n === 0) {
      expect((await c.innerText()).trim()).toContain('no reason recorded')
      continue
    }
    expect(await c.locator('[data-bullet]').count()).toBe(n)
  }
  if (listy !== null) {
    const counts = await crit.evaluateAll((els) =>
      els.map((e) => Number(e.getAttribute('data-bullets'))),
    )
    expect(
      Math.max(...counts),
      'this revision was chosen BECAUSE a criterion carries several bullets',
    ).toBeGreaterThan(1)
  }
  const fired = page.locator('[data-criterion][data-state="fired"]')
  if ((await fired.count()) > 0)
    await expect(fired.first()).toContainText('fired')
  // clearing is the settled norm and says nothing (subtraction rule)
  const cleared = page.locator('[data-criterion][data-state="clear"]')
  if ((await cleared.count()) > 0)
    await expect(cleared.first()).not.toContainText('cleared')
})

test('constellation: the first view IS the fit', async ({ page, request }) => {
  // The plate is laid out at a default aspect, measured against the
  // page, and re-laid out at the real one — and the camera went on
  // framing the first of those two until `fit` was pressed, so opening
  // a sky and pressing fit gave two different pictures (owner,
  // 2026-08-27).
  const shelf = await firstShelf(request)
  test.skip(shelf === null, 'empty workspace')
  const s = shelf as Shelf
  await page.goto(at(s.project, 'sky', s.task))
  const cam = page.locator('main svg.constellation > g[transform]').first()
  await cam.waitFor({ timeout: 10000 })

  // let the opening settle (the camera glides), then read it
  const settled = async () => {
    let prev = ''
    for (let i = 0; i < 30; i++) {
      const t = (await cam.getAttribute('transform')) ?? ''
      if (t !== '' && t === prev) return t
      prev = t
      await page.waitForTimeout(120)
    }
    return prev
  }
  const opened = await settled()
  expect(opened).not.toBe('')

  await page.getByRole('button', { name: 'fit', exact: true }).click()
  const fitted = await settled()

  // same camera, to the pixel the renderer rounds to
  const nums = (t: string) => (t.match(/-?\d+(\.\d+)?/g) ?? []).map(Number)
  const a = nums(opened)
  const b = nums(fitted)
  expect(a.length, `unreadable transform ${opened}`).toBeGreaterThan(0)
  expect(b.length).toBe(a.length)
  for (let i = 0; i < a.length; i++)
    expect(Math.abs(a[i] - b[i]), `opened ${opened} vs fitted ${fitted}`).toBeLessThan(1)
})

test('constellation: a resize refits, and a drag never rescales', async ({ page, request }) => {
  // Un-maximising the window parked the sky at scale(1) — an 11x zoom
  // on union_closed, whose fit is 0.07 — and it stayed there until the
  // reader nudged it (owner, 2026-08-27: 取消最大化就會變這樣然後停住,
  // 稍微拖動一下就會恢復 fit 的大小). Two effects wrote the camera in
  // one commit, `setView(null)` ran last, and React's null-to-null
  // bail-out meant the refit never ran again. `viewRef` still held the
  // true fit, so the FIRST DRAG published it — which is the tell this
  // test reads: a pan must move the sky and never rescale it.
  //
  // It takes a sky whose PLATE answers the page's shape, so the target
  // is the biggest one this workspace has; a small graph packs the same
  // at every aspect and never enters the race.
  const list = await request.get('/api/problems')
  const rows: { name: string; goals: { total: number } }[] = list.ok()
    ? ((await list.json()).problems ?? [])
    : []
  const biggest = rows.sort((a, b) => (b.goals?.total ?? 0) - (a.goals?.total ?? 0))[0]
  test.skip(
    !biggest || (biggest.goals?.total ?? 0) < 200,
    'needs a sky whose plate answers the page shape',
  )

  await page.setViewportSize({ width: 1900, height: 1000 })
  await page.goto(`/#/problems/${encodeURIComponent(biggest.name)}`)
  const cam = page.locator('main svg.constellation > g[transform]').first()
  await cam.waitFor({ timeout: 20000 })
  const settled = async () => {
    let prev = ''
    for (let i = 0; i < 40; i++) {
      const t = (await cam.getAttribute('transform')) ?? ''
      if (t !== '' && t === prev) return t
      prev = t
      await page.waitForTimeout(120)
    }
    return prev
  }
  await settled()

  await page.setViewportSize({ width: 1200, height: 700 })
  const resized = await settled()
  // `view === null` renders the sky on the no-camera fallback; a sky
  // that settles there settled on nothing
  expect(resized, 'parked on the no-camera fallback').not.toBe('translate(0,0) scale(1)')
  // the smaller page gets its OWN fit, not the one it was carrying
  await page.getByRole('button', { name: 'fit', exact: true }).click()
  const fitted = await settled()
  expect(resized, `resized ${resized} vs fitted ${fitted}`).toBe(fitted)

  const scaleOf = (t: string) => Number(/scale\(([-\d.eE]+)\)/.exec(t)?.[1] ?? NaN)
  const sky = await page.locator('main svg.constellation').first().boundingBox()
  const cx = Math.round((sky?.x ?? 0) + (sky?.width ?? 0) / 2)
  const cy = Math.round((sky?.y ?? 0) + (sky?.height ?? 0) / 2)
  await page.mouse.move(cx, cy)
  await page.mouse.down()
  await page.mouse.move(cx + 24, cy + 18, { steps: 4 })
  await page.mouse.up()
  const dragged = await settled()
  expect(scaleOf(dragged), `fitted ${fitted} then dragged ${dragged}`).toBeCloseTo(
    scaleOf(fitted),
    6,
  )
  expect(dragged, 'the drag moved nothing').not.toBe(fitted)
})

test('sky: the first node hover needs no priming click', async ({ page, request }) => {
  const shelf = await firstShelf(request)
  test.skip(shelf === null, 'empty workspace')
  const s = shelf as Shelf
  await page.goto(at(s.project, 'sky', s.task))
  const star = page.locator('svg.constellation g.cursor-pointer[transform]').first()
  const alive = await star
    .waitFor({ timeout: 15000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!alive, 'this task has no stars yet')

  // Regression: the mount reset used to publish a null camera AFTER
  // the layout fit. Hover state rendered, but its card was gated on a
  // camera; clicking any node caused the second render that repaired it.
  await star.hover()
  await expect(page.locator('[data-goal-hover]')).toBeVisible()
})
