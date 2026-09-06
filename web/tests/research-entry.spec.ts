import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

// Fully intercepted API: deterministic states, including failures, and
// no command, edit or model probe can reach the running research engine.
async function fixture(page: Page, options: { empty?: boolean; failed?: boolean; pending?: boolean } = {}) {
  const writes: string[] = []
  page.on('pageerror', error => { throw error })
  await page.route('**/api/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() !== 'GET') {
      writes.push(path)
      await route.fulfill({ status: 403, json: { detail: 'No writes in a reading test' } })
      return
    }
    const task = { name: 'Combinatorics.union_closed', project: 'Combinatorics', status: 'proving',
      goals: { open: 2, proved: 179, shelved: 71, total: 253 }, in_flight: 3, queued: 0,
      last_event: '2026-09-05T12:00:00Z', created_at: '2026-09-01T00:00:00Z' }
    const projects = [
      { name: 'Algebra', description: 'Groups and their actions.', problems: 1, running: 0, attention: 0, last_event: null },
      { name: 'Combinatorics', description: 'Union-closed families.', problems: 1, running: 1, attention: 0, last_event: null },
      { name: 'Topology', description: 'Surfaces and spaces.', problems: 1, running: 0, attention: 1, last_event: null },
    ]
    const goals = [1, 2].map(id => ({ id, slug: `step_${id}`, status: 'proved', kind: 'theorem',
      origin: id === 1 ? 'root' : 'backward', attempts: 1, dead_attempts: 0, in_flight: false,
      is_deliverable: false, human_facing_claim: false, alias_target_id: null, detached: false }))
    const groups = [
      { id: 10, problem: task.name, parent_id: null, is_top: true, charter: '', status: 'active', rev: 1, bricks: 0 },
      { id: 11, problem: task.name, parent_id: 10, is_top: false, charter: 'A delegated claim', title: 'A delegated claim', status: 'active', rev: 1, bricks: 0 },
    ]
    if (options.failed && (path === '/api/projects' || path === '/api/problems')) {
      await route.fulfill({ status: 503, json: { detail: 'Reading unavailable' } })
      return
    }
    const body = path === '/api/projects' ? { projects: options.empty ? [] : projects }
      : path === '/api/problems' ? { problems: options.empty ? [] : [task] }
      : path === '/api/meta' ? { claude: { installed: true, logged_in: true }, inbox_count: 0 }
      : path === '/api/daemon' ? { running: false, starting: false, last_exit: null }
      : path === '/api/config' ? { settings: [] }
      : path === '/api/inbox' ? { amends: [], signoffs: [] }
      : path === '/api/run' ? { workers: [] }
      : path.endsWith('/programme') ? { group_id: Number(new URL(request.url()).searchParams.get('group') ?? 10), groups,
        current: { rev: 1, body: '# A readable argument\n\n' + 'A step in the proof.\n\n'.repeat(70), reservations: [] }, history: [], charter: null }
      : path.endsWith('/programme/revisions') ? { revisions: [] }
      : path === `/api/problems/${task.name}` ? { name: task.name, goals, strategies: [{ id: 1, goal_id: 1, status: 'succeeded' }],
        strategy_edges: [{ strategy_id: 1, subgoal_id: 2, position: 0 }], anchor_edges: [], citation_edges: [] }
      : path.endsWith('/intent') ? { problem: task.name, charter: 'Prove the union-closed sets conjecture. For $x \\in F$, read the mathematical statement.', word: '',
        settings: { axioms_whitelist: [], forbidden_lemmas: [], library: false }, pending_amend: options.pending ?? false }
      : path.endsWith('/papers') ? { papers: [] }
      : {}
    await route.fulfill({ json: body })
  })
  return writes
}

test('project search and activity filters compose, and Escape clears the search', async ({ page }) => {
  const writes = await fixture(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Your research.' })).toBeVisible()
  await page.getByRole('searchbox', { name: 'Search projects' }).fill('UNION-CLOSED')
  await expect(page.locator('a[href^="#/p/"]')).toHaveCount(1)
  await expect(page.locator('a[href^="#/p/"]')).toContainText('Combinatorics')
  await page.getByRole('button', { name: /^Needs you/ }).click()
  await expect(page.getByText('No matching projects.')).toBeVisible()
  await page.getByRole('searchbox').focus()
  await page.keyboard.press('Escape')
  await expect(page.locator('a[href^="#/p/"]')).toHaveCount(1)
  await expect(page.locator('a[href^="#/p/"]')).toContainText('Topology')
  await expect(page.getByRole('button', { name: /^Needs you/ })).toHaveAttribute('aria-pressed', 'true')
  expect(writes).toEqual([])
})

test('large project cards show a real nonempty snapshot, not decorative stars', async ({ page }) => {
  const writes = await fixture(page)
  await page.goto('/')
  await page.getByRole('searchbox', { name: 'Search projects' }).fill('Combinatorics')
  const map = page.getByRole('img', { name: 'Proof map snapshot of Combinatorics.union_closed' })
  await expect(map).toBeVisible()
  await expect(map.locator('[data-preview-goal]')).toHaveCount(2)
  await expect(map.locator('path')).toHaveCount(1)
  const card = page.locator('a[href="#/p/Combinatorics/tasks"]')
  expect((await card.boundingBox())!.height).toBeGreaterThanOrEqual(400)
  expect((await card.boundingBox())!.width).toBeGreaterThan(500)
  await card.click({ position: { x: 300, y: 230 } })
  await expect(page).toHaveURL(/#\/p\/Combinatorics\/tasks$/)
  expect(writes).toEqual([])
})

test('a preview skips a task emptied after the listing, without inventing a sky', async ({ page }) => {
  await fixture(page)
  await page.addInitScript(() => { Math.random = () => 0 })
  await page.route('**/api/problems?project=Combinatorics', route => route.fulfill({ json: { problems: [
    { name: 'Combinatorics.a', project: 'Combinatorics', goals: { total: 1 } },
    { name: 'Combinatorics.union_closed', project: 'Combinatorics', goals: { total: 2 } },
  ] } }))
  await page.route('**/api/problems/Combinatorics.a', route => route.fulfill({ json: { goals: [] } }))
  await page.goto('/')
  await page.getByRole('searchbox').fill('Combinatorics')
  await expect(page.getByRole('img', { name: 'Proof map snapshot of Combinatorics.union_closed' })).toBeVisible()
  await expect(page.locator('[data-preview-goal]')).toHaveCount(2)
})

test('empty projects and failed reads are not confused with loading', async ({ page }) => {
  await fixture(page, { empty: true })
  await page.goto('/')
  await expect(page.getByText('Start with a project.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'new project' })).toBeVisible()
  await page.unrouteAll()
  await fixture(page, { failed: true })
  await page.reload()
  await expect(page.getByText("Can't reach the engine")).toBeVisible()
  await expect(page.getByText('Loading projects…')).toHaveCount(0)
})

test('task shelf offers named reading links, honest inventory and a recoverable empty search', async ({ page }) => {
  const writes = await fixture(page)
  await page.goto('/#/p/Combinatorics/tasks')
  const row = page.locator('tr[data-kind="task"]')
  await expect(row).toContainText('179 proved · 2 open')
  await expect(row).not.toContainText('179/253')
  await expect(page.getByRole('link', { name: 'Read the argument — Combinatorics.union_closed' }))
    .toHaveAttribute('href', '#/p/Combinatorics/groups/Combinatorics.union_closed')
  await page.getByRole('checkbox', { name: 'Select Combinatorics.union_closed for the next run' }).check()
  await expect(page.getByRole('button', { name: 'Run 1…' })).toBeEnabled()
  await page.getByRole('button', { name: 'clear 1 selected' }).click()
  await expect(page.getByRole('button', { name: 'Run…', exact: true })).toBeDisabled()
  await page.getByRole('searchbox', { name: 'Search tasks' }).fill('not-here')
  await expect(page.getByText('No matching tasks.')).toBeVisible()
  await page.getByRole('button', { name: 'Clear the search' }).click()
  await expect(row).toBeVisible()
  expect(writes).toEqual([])
})

test('task opens for reading, renders math, and preserves an unsaved edit across view toggles', async ({ page }) => {
  const writes = await fixture(page)
  await page.goto('/#/p/Combinatorics/tasks/Combinatorics.union_closed')
  await expect(page.getByRole('heading', { name: 'The question', exact: true })).toBeVisible()
  await expect(page.locator('.katex').first()).toBeVisible()
  await expect(page.locator('textarea:visible')).toHaveCount(0)
  await page.getByRole('button', { name: 'Edit intent' }).click()
  const charter = page.getByRole('textbox', { name: 'The goal', exact: true })
  await charter.fill('A draft that must survive.')
  await page.getByRole('button', { name: 'Read', exact: true }).click()
  await expect(page.locator('p').filter({ hasText: /^A draft that must survive\.$/ })).toBeVisible()
  await expect(page.getByText('Unsaved changes', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Edit intent' }).click()
  await expect(charter).toHaveValue('A draft that must survive.')
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeEnabled()
  expect(writes).toEqual([])
})

test('a pending amendment still locks the goal, but not the standing word', async ({ page }) => {
  await fixture(page, { pending: true })
  await page.goto('/#/p/Combinatorics/tasks/Combinatorics.union_closed')
  await expect(page.getByText('The strategist has proposed a change', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Edit intent' }).click()
  await expect(page.getByRole('textbox', { name: 'The goal', exact: true })).toBeDisabled()
  await expect(page.getByRole('textbox', { name: 'Your standing word', exact: true })).toBeEnabled()
})

test('failed task listing offers recovery instead of a perpetual loading state', async ({ page }) => {
  await fixture(page, { failed: true })
  await page.goto('/#/p/Combinatorics/tasks')
  await expect(page.getByText("Can't reach the engine")).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
})

test('group navigation stays beside a long argument, and history has its own reading view', async ({ page }) => {
  const writes = await fixture(page)
  await page.goto('/#/p/Combinatorics/groups/Combinatorics.union_closed')
  const rail = page.getByRole('complementary', { name: 'Discussion groups' })
  await expect(rail).toBeVisible()
  await expect(page.getByRole('article', { name: 'Current argument' })).toBeVisible()
  const top = (await rail.boundingBox())!.y
  await page.locator('main').last().evaluate(el => { el.scrollTop = 800 })
  expect((await rail.boundingBox())!.y).toBeGreaterThanOrEqual(top - 25)
  await page.locator('main').last().evaluate(el => { el.scrollTop = 0 })
  // the chain is an INDEX under the reading, not a second view of the
  // page: it unfolds in place and the argument stays where it was
  // (owner, 2026-09-06 — a Timeline row naming a revision used to land
  // on the list side with the argument one click further in)
  await page.getByRole('button', { name: 'revision history' }).click()
  await expect(page.getByText('nothing decided yet', { exact: false })).toBeVisible()
  await expect(page.getByRole('article', { name: 'Current argument' })).toBeVisible()
  await rail.getByRole('button', { name: /A delegated claim/ }).click()
  await expect(rail.getByRole('button', { name: /A delegated claim/ })).toHaveAttribute('aria-current', 'true')
  expect(writes).toEqual([])
})

for (const theme of ['dark', 'light']) {
  test(`${theme}: project layout at narrow desktop width`, async ({ page }) => {
    await fixture(page)
    await page.setViewportSize({ width: 900, height: 800 })
    await page.addInitScript(t => localStorage.setItem('asterism.theme', t), theme)
    await page.goto('/')
    await expect(page.getByRole('searchbox')).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `test-results/research-entry-${theme}.png` })
    await page.goto('/#/p/Combinatorics/tasks/Combinatorics.union_closed')
    await expect(page.getByRole('button', { name: 'Edit intent' })).toBeVisible()
    await expect(page.locator('[data-menu] a')).toHaveCount(6)
    for (const link of await page.locator('[data-menu] a').all()) {
      const bounds = (await link.boundingBox())!
      expect(bounds.x).toBeGreaterThanOrEqual(0)
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(900)
    }
  })
}
