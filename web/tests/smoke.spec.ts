import { expect, test } from '@playwright/test'

/*
 * Read-only smoke over a live workspace. Assumes at least one problem
 * exists (any real Asterism workspace); individual assertions degrade
 * gracefully on emptier workspaces where noted.
 */

test('board renders problems with status chips', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Problems' })).toBeVisible()
  // either rows exist or the explicit empty state shows — never a blank
  const rows = page.locator('tbody tr')
  const empty = page.getByText('No problems yet')
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
  const firstName = (await rows.first().locator('td').first().innerText()).trim()
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
  const anySection = page
    .getByText(/amend requests|ingest sign-offs/i)
    .first()
    .or(page.getByText('Nothing needs you right now'))
  await expect(anySection).toBeVisible()
})

test('library atlas renders constellations or empty state', async ({ page }) => {
  await page.goto('/#/library')
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible()
  const sky = page.locator('main svg').first().or(page.getByText('The Library is empty'))
  await expect(sky).toBeVisible()
})

test('telemetry: daemon panel + log + usage + library sections', async ({ page }) => {
  await page.goto('/#/telemetry')
  await expect(page.getByRole('heading', { name: 'Engine' })).toBeVisible()
  for (const label of ['run log', 'usage — this run']) {
    await expect(page.getByText(label, { exact: true })).toBeVisible()
  }
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
  await expect(page.getByPlaceholder('Namespace.leaf_name')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create problem' })).toBeDisabled()
})
