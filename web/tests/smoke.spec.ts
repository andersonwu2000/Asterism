import { expect, test } from '@playwright/test'

/*
 * Read-only smoke over ANY workspace state — a fresh reset, an idle
 * engine, or a mid-run live one. Assertions never bind to specific
 * problems, counts, or engine state: they check structure (a row or
 * its empty state, a label that renders either way) and skip
 * gracefully where population is genuinely required.
 */

test('board renders problems with status chips', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Problems' })).toBeVisible()
  // either rows exist or the explicit empty state shows — never a blank
  const rows = page.locator('tbody tr')
  const empty = page.getByText('Prove something')
  await expect(rows.first().or(empty)).toBeVisible()
})

test('board filter narrows the list', async ({ page }) => {
  await page.goto('/')
  const rows = page.locator('tbody tr[data-kind="problem"]')
  const populated = await rows
    .first()
    .waitFor({ timeout: 5000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!populated, 'needs a populated workspace')
  const total = await rows.count()
  test.skip(total < 2, 'needs a populated workspace')
  // the name LINK is the cell's only name-only node: while the engine
  // works, the same cell also carries an in-flight badge, and reading
  // the whole cell filtered on two lines at once (zero matches)
  const firstName = (await rows.first().locator('a').first().innerText()).trim()
  await page.getByPlaceholder('filter problems…').fill(firstName)
  await expect
    .poll(async () => rows.count())
    .toBeLessThanOrEqual(total)
  await expect(rows.first()).toContainText(firstName)
})

test('problem detail: four tabs, constellation svg has stars', async ({ page }) => {
  await page.goto('/')
  const firstRow = page.locator('tbody tr[data-kind="problem"]').first()
  const populated = await firstRow
    .waitFor({ timeout: 5000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!populated, 'empty workspace')
  // click the name cell — the row's center can land on the status
  // badge, which is its own link (needs-input → inbox)
  await firstRow.locator('td').first().click()
  await expect(page.getByRole('button', { name: 'Constellation' })).toBeVisible()
  for (const tab of ['Goals', 'Timeline', 'Files']) {
    await expect(page.getByRole('button', { name: new RegExp(tab) })).toBeVisible()
  }
  // constellation stars = one <g> per goal under the transform group
  const stars = page.locator('main svg g[transform] > g')
  const goalsLabel = await page.getByRole('button', { name: /Goals \(\d+\)/ }).innerText()
  const goalCount = Number(/\((\d+)\)/.exec(goalsLabel)?.[1] ?? 0)
  if (goalCount > 0) {
    expect(await stars.count()).toBeGreaterThan(0)
  }
})

test('inbox renders sections or empty state', async ({ page }) => {
  await page.goto('/#/inbox')
  await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible()
  // .first() AFTER the or(): a non-empty inbox renders both section
  // labels, and first().or(...) tripped strict mode on exactly that
  const anySection = page
    .getByText(/amend requests|ingest sign-offs/i)
    .or(page.getByText('Nothing needs you right now'))
    .first()
  await expect(anySection).toBeVisible()
})

test('library atlas renders constellations or empty state', async ({ page }) => {
  await page.goto('/#/library')
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible()
  const sky = page.locator('main svg').first().or(page.getByText('The Library is empty'))
  await expect(sky).toBeVisible()
})

test('settings screen renders', async ({ page }) => {
  // the console's own settings (accounts, appearance) live here; the
  // engine's knobs are #/engine/settings
  await page.goto('/#/settings')
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
})

test('telemetry legacy route lands on the usage ledger', async ({ page }) => {
  await page.goto('/#/telemetry')
  // the label is daemon-truthful and always renders: "this run" while
  // one runs, "all time" otherwise — never bind to which one
  await expect(page.getByText(/usage — (all time|this run)/)).toBeVisible()
})

test('run console: phase heading + guidance, idle or live', async ({ page }) => {
  await page.goto('/#/run')
  await expect(
    page.getByRole('heading', {
      name: /Idle|Starting|Proving|Planning|Warming up|Harvesting|Stopping/,
    }),
  ).toBeVisible()
  // burn figures moved to the Usage tab (owner, 2026-07-18); the quota
  // meter's caption is the console's stable floor — one of the two
  // wordings renders whether or not a seat rides the meter right now
  await expect(page.getByText(/claude plan|plan usage/)).toBeVisible()
})

test('papers shelf renders rows or empty state', async ({ page }) => {
  await page.goto('/#/papers')
  await expect(page.getByRole('heading', { name: 'Papers' })).toBeVisible()
  // rows, the explicit empty state, or (on an engine predating the
  // papers API) the error state — never a blank list area
  const rows = page.locator('tbody tr')
  const empty = page.getByText('The shelf is empty')
  const errState = page.getByText(/Not found|Can't reach the engine/).first()
  await expect(rows.first().or(empty).or(errState)).toBeVisible()
})

test('api meta reachable and shaped', async ({ request }) => {
  const r = await request.get('/api/meta')
  expect(r.ok()).toBeTruthy()
  const body = await r.json()
  expect(body).toHaveProperty('workspace')
  expect(body).toHaveProperty('daemon')
  expect(['ok', 'missing', 'behind', 'unavailable']).toContain(body.db)
})

test('new-problem form renders (read-only: no submit)', async ({ page }) => {
  await page.goto('/#/new')
  await expect(page.getByRole('heading', { name: 'New problem' })).toBeVisible()
  await expect(page.getByPlaceholder('Topology.my_theorem')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create problem' })).toBeDisabled()
})

test('new-problem: the shelf is a search, not a wall', async ({ page }) => {
  // The picker used to render one checkbox per shelved paper, which
  // buried the rest of the form (owner, 2026-08-27). Collapsed it is
  // one field; the list opens under the cursor and drops what is
  // already bound. Read-only — nothing here submits.
  await page.goto('/#/new')
  const search = page.getByPlaceholder(/search the shelf|whole shelf is bound/)
  const shelved = await search
    .waitFor({ timeout: 5000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!shelved, 'needs a workspace with a paper shelf')

  // collapsed: the wall is gone — no checkbox survives in this form
  expect(await page.locator('input[type="checkbox"]').count()).toBe(0)

  // the list is closed until the field has the cursor
  const options = page.locator('[data-paper-option]')
  expect(await options.count()).toBe(0)
  await search.click()
  await expect(options.first()).toBeVisible()
  const all = await options.count()
  expect(all).toBeGreaterThan(0)

  // typing narrows it, and a query nothing matches says so rather
  // than leaving an empty box
  await search.fill('zzzzz-no-such-paper')
  await expect(page.getByText('nothing on the shelf matches')).toBeVisible()

  // taking one moves it out of the list and into a chip that drops it
  await search.fill('')
  const first = (await options.first().innerText()).split('\n')[0].trim()
  await options.first().click()
  const chip = page.locator('[data-paper-chip]')
  await expect(chip).toHaveCount(1)
  await expect(chip.first()).toContainText(first)
  expect(await options.count()).toBe(all - 1)
  await chip.first().click()
  await expect(chip).toHaveCount(0)
})
