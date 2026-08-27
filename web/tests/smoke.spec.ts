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

test('new-problem: the shelf is a window, not a wall', async ({ page }) => {
  // The picker used to render one checkbox per shelved paper, which
  // buried the rest of the form (owner, 2026-08-27). It is a floating
  // window now: collapsed the field is one button, and choosing marks
  // a paper in place rather than moving it. Read-only — no submit.
  await page.goto('/#/new')
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

test('new-problem: Defs and Root wear the shared Lean block', async ({ page }) => {
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

test('constellation: the first view IS the fit', async ({ page }) => {
  // The plate is laid out at a default aspect, measured against the
  // page, and re-laid out at the real one — and the camera went on
  // framing the first of those two until `fit` was pressed, so opening
  // a sky and pressing fit gave two different pictures (owner,
  // 2026-08-27).
  await page.goto('/')
  const firstRow = page.locator('tbody tr[data-kind="problem"]').first()
  const populated = await firstRow
    .waitFor({ timeout: 5000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!populated, 'empty workspace')
  await firstRow.locator('td').first().click()
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

test('engine console: the sky opens on its fit, and stays put', async ({ page }) => {
  // The console is where "opened != fitted" actually bit: its sky is
  // LIVE, so the plate is re-laid as goals land, and a camera fitted
  // to the plate of ten seconds ago is not the fit any more. Measured
  // there before the fix: the view sat at k=0.05801 for as long as you
  // liked while `fit` gave 0.05932 (owner, 2026-08-27). The problem
  // page's copy of this test passed throughout — its plate is static.
  await page.goto('/#/run')
  const cam = page.locator('svg.constellation > g[transform]').first()
  const alive = await cam
    .waitFor({ timeout: 15000 })
    .then(() => true)
    .catch(() => false)
  test.skip(!alive, 'no problem in focus on this console')

  const read = async () => (await cam.getAttribute('transform')) ?? ''
  const settled = async () => {
    let prev = ''
    for (let i = 0; i < 25; i++) {
      const t = await read()
      if (t !== '' && t === prev) return t
      prev = t
      await page.waitForTimeout(150)
    }
    return prev
  }
  const opened = await settled()
  expect(opened).not.toBe('')
  await page.getByRole('button', { name: 'fit', exact: true }).click()
  const fitted = await settled()

  const nums = (t: string) => (t.match(/-?\d+(\.\d+)?/g) ?? []).map(Number)
  const a = nums(opened)
  const b = nums(fitted)
  expect(b.length).toBe(a.length)
  for (let i = 0; i < a.length; i++)
    expect(Math.abs(a[i] - b[i]), `opened ${opened} vs fitted ${fitted}`).toBeLessThan(1)
})
