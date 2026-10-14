import { expect, test } from '@playwright/test'

// These checks exercise reading and navigation with deterministic data.
// Every request is intercepted, including model discovery and document saves.
test.beforeEach(async ({ page }) => {
  page.on('pageerror', error => { throw error })
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET')
      return route.fulfill({ status: 403, json: { detail: 'Read-only interface check' } })
    const tasks = ['first', 'second'].map(name => ({
      name: `Example.${name}`, project: 'Example', status: 'idle',
      goals: { total: 0, open: 0, proved: 0 }, in_flight: 0, queued: 0,
    }))
    const body = path === '/api/projects' ? { projects: [{ name: 'Example', problems: 2, running: 0, attention: 0 }] }
      : path === '/api/problems' ? { problems: tasks }
      : path === '/api/meta' ? { claude: { installed: true, logged_in: true }, providers: [], inbox_count: 0 }
      : path === '/api/config' ? { settings: [] }
      : path === '/api/daemon' ? { running: false, starting: false, last_exit: null }
      : path === '/api/shutdown/preview' ? { daemon: { running: false }, gateway: { phase: null } }
      : path === '/api/run' ? { workers: [] }
      : path === '/api/chat/state' ? { busy: false, model_default: 'model-a', groups: [{ provider: 'example', models: ['model-a', 'model-b'], installed: true, explainer: true }] }
      : path === '/api/chat/sessions' ? { sessions: [] }
      : path.endsWith('/docs') ? { entries: [{ path: 'user', kind: 'dir' }, { path: 'user/notes.md', kind: 'file' }] }
      : path.endsWith('/docs/user/notes.md') ? { content: '# Research notes\n\nA readable document.', etag: 'one' }
      : path.endsWith('/papers') ? { papers: [] }
      : path.endsWith('/intent') ? { charter: 'Prove the claim.', word: '', settings: { axioms_whitelist: [], forbidden_lemmas: [] } }
      : path === '/api/inbox' ? { amends: [], signoffs: [] }
      : { goals: [], strategies: [], events: [] }
    return route.fulfill({ json: body })
  })
})

test('Settings contains keyboard focus and gives it back when dismissed', async ({ page }) => {
  await page.goto('/#/p/Example/workspace')
  const trigger = page.getByRole('button', { name: 'Settings', exact: true })
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: 'Settings', exact: true })
  await expect(dialog).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true)
  for (let i = 0; i < 16; i++) {
    await page.keyboard.press('Tab')
    expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true)
  }
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await trigger.click()
  await dialog.getByRole('button', { name: 'Close Settings', exact: true }).click()
  await expect(trigger).toBeFocused()
})

test('Escape closes the Assistant model menu first and restores its trigger', async ({ page }) => {
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  const trigger = assistant.getByRole('button', { name: 'model', exact: true })
  await trigger.click()
  await expect(page.getByRole('listbox')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('listbox')).toHaveCount(0)
  await expect(assistant).toBeVisible()
  await expect(trigger).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(assistant).toBeHidden()
})

test('a long Settings window keeps its close control visible while its body scrolls', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 600 })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Settings', exact: true })
  await dialog.locator('[data-window-body]').evaluate(el => { el.scrollTop = el.scrollHeight })
  await expect(dialog.getByRole('button', { name: 'Close Settings', exact: true })).toBeInViewport()
  await page.keyboard.press('Control+/')
  await expect(page.getByRole('complementary', { name: 'assistant', exact: true })).toBeHidden()
  await expect(dialog).toBeVisible()
})

test('machine parameters fit a narrow window and expose Save only for a change', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 })
  await page.route('**/api/config', route => route.fulfill({ json: { settings: [
    { key: 'dispatch.pool', resolved: 4, description: 'Maximum agents working at once' },
    { key: 'dispatch.ram_budget', resolved: '85%', description: 'RAM the workers may use' },
  ] } }))
  await page.goto('/#/settings')
  const dialog = page.getByRole('dialog', { name: 'Settings', exact: true })
  const pool = dialog.getByLabel('Concurrent agents', { exact: true })
  await expect(pool).toHaveValue('4')
  await expect(dialog.getByRole('button', { name: 'Save changes', exact: true })).toHaveCount(0)
  await pool.fill('5')
  await expect(dialog.getByRole('button', { name: 'Save changes', exact: true })).toBeEnabled()
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  for (const field of [pool, dialog.getByLabel('Memory limit', { exact: true })]) {
    const box = (await field.boundingBox())!
    expect(box.x).toBeGreaterThan(0)
    expect(box.x + box.width).toBeLessThan(390)
  }
  await pool.fill('4')
  await expect(dialog.getByRole('button', { name: 'Save changes', exact: true })).toHaveCount(0)
})

test('a failed decision check stays visible and can be retried', async ({ page }) => {
  let unavailable = true
  await page.route('**/api/inbox?*', route => route.fulfill(unavailable
    ? { status: 503, json: { detail: 'temporarily unavailable' } }
    : { json: { amends: [], signoffs: [] } }))
  await page.goto('/#/p/Example/tasks')
  const notice = page.getByRole('status').filter({ hasText: 'decisions waiting on you' })
  await expect(notice).toBeVisible()
  unavailable = false
  await notice.getByRole('button', { name: 'Retry' }).click()
  await expect(notice).toHaveCount(0)
})

test('model discovery can be retried after a failure without changing any settings', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/models/refresh', route => {
    attempts++
    return route.fulfill(attempts === 1
      ? { status: 503, json: { detail: 'Catalog temporarily unavailable' } }
      : { json: { groups: [], houses: {} } })
  })
  await page.goto('/#/settings')
  expect(attempts).toBe(0)
  const load = page.getByRole('button', { name: 'Load model choices', exact: true })
  await load.click()
  await expect(page.getByText('Couldn’t load model choices. Try again.')).toBeVisible()
  await expect(load).toBeEnabled()
  await load.click()
  await expect(page.getByText('Couldn’t load model choices. Try again.')).toHaveCount(0)
  await expect(page.getByText('No default model presets available.')).toBeVisible()
  expect(attempts).toBe(2)
})

test('model choices support Home and End and dismiss when Tab leaves the menu', async ({ page }) => {
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  await assistant.getByRole('button', { name: 'model', exact: true }).click()
  await page.keyboard.press('End')
  await expect(page.getByRole('option', { name: 'model-b', exact: true })).toBeFocused()
  await page.keyboard.press('Home')
  await expect(page.getByRole('option', { name: 'model-a', exact: true })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('listbox')).toHaveCount(0)
  await expect(assistant).toBeVisible()
})

test('a late conversation read cannot replace the conversation selected afterward', async ({ page }) => {
  const sessions = ['first', 'slow', 'latest'].map(id => ({ id, title: `${id} conversation`,
    turns: 1, model: 'model-a', provider: 'example', updated_at: '2026-09-08T00:00:00Z' }))
  await page.route('**/api/chat/sessions?*', route => route.fulfill({ json: { sessions } }))
  let releaseSlow!: () => void
  const slow = new Promise<void>(resolve => { releaseSlow = resolve })
  await page.route('**/api/chat/sessions/*', async route => {
    const id = new URL(route.request().url()).pathname.split('/').pop()!
    if (id === 'slow') await slow
    await route.fulfill({ json: { turns: [{ role: 'assistant', text: `Answer from ${id}.` }] } })
  })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  await expect(assistant.getByText('Answer from first.')).toBeVisible()
  await assistant.getByRole('button', { name: 'conversations', exact: true }).click()
  const request = page.waitForRequest('**/api/chat/sessions/slow')
  await assistant.getByRole('button', { name: /^slow conversation/ }).click()
  await request
  await expect(assistant.getByText('Answer from first.')).toHaveCount(0)
  await assistant.getByRole('button', { name: /^latest conversation/ }).click()
  await expect(assistant.getByText('Answer from latest.')).toBeVisible()
  const response = page.waitForResponse('**/api/chat/sessions/slow')
  releaseSlow()
  await response
  await expect(assistant.getByText('Answer from latest.')).toBeVisible()
  await expect(assistant.getByText('Answer from slow.')).toHaveCount(0)
})

for (const reason of ['unavailable', 'different backend']) {
  test(`Enter respects the disabled send control when ${reason}`, async ({ page }) => {
    await page.route('**/api/chat/state?*', route => route.fulfill({ json: {
      available: reason !== 'unavailable', model_default: 'model-a',
      groups: [{ provider: 'example', models: ['model-a'], installed: true, explainer: true }],
    } }))
    await page.route('**/api/chat/sessions?*', route => route.fulfill({ json: { sessions: [{
      id: 'one', title: 'Existing conversation', turns: 1, model: 'old-model', provider: 'another',
      updated_at: '2026-09-08T00:00:00Z',
    }] } }))
    await page.route('**/api/chat/sessions/one', route => route.fulfill({ json: { turns: [] } }))
    let posts = 0
    page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/chat')) posts++ })
    await page.goto('/#/p/Example/workspace')
    await page.getByRole('button', { name: 'Assistant', exact: true }).click()
    const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
    await expect(assistant.getByText('Loading conversation…')).toHaveCount(0)
    const composer = assistant.getByRole('textbox', { name: 'Message to the Assistant' })
    await composer.fill('A question to keep for later.')
    await expect(assistant.getByRole('button', { name: 'send', exact: true })).toBeDisabled()
    await composer.press('Enter')
    await expect(composer).toHaveValue('A question to keep for later.')
    expect(posts).toBe(0)
  })
}

test('an answer finishing after a project switch stays out of the new project conversation', async ({ page }) => {
  await page.route('**/api/chat/sessions?*', route => {
    const project = new URL(route.request().url()).searchParams.get('project') ?? 'Example'
    return route.fulfill({ json: { sessions: [{ id: project, title: `${project} conversation`,
      turns: 1, model: 'model-a', provider: 'example', updated_at: '2026-09-08T00:00:00Z' }] } })
  })
  await page.route('**/api/chat/sessions/*', route => {
    const id = new URL(route.request().url()).pathname.split('/').pop()!
    return route.fulfill({ json: { turns: [{ role: 'assistant', text: `Saved answer for ${id}.` }] } })
  })
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/chat', async route => {
    await pending
    await route.fulfill({ contentType: 'text/event-stream', body:
      'data: {"type":"delta","text":"Late answer for Example."}\n\ndata: {"type":"done","ok":true}\n\n' })
  })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  await expect(assistant.getByText('Saved answer for Example.')).toBeVisible()
  await assistant.getByRole('textbox', { name: 'Message to the Assistant' }).fill('Explain this project.')
  await assistant.getByRole('button', { name: 'send', exact: true }).click()
  await expect(assistant.getByRole('button', { name: 'stop', exact: true })).toBeVisible()
  await page.evaluate(() => { location.hash = '/p/Other/workspace' })
  await expect(assistant.getByText('Saved answer for Other.')).toBeVisible()
  await expect(assistant.getByRole('status').filter({ hasText: 'Still answering in Example' })).toBeVisible()
  release()
  await expect(assistant.getByRole('button', { name: 'stop', exact: true })).toHaveCount(0)
  await expect(assistant.getByText('Saved answer for Other.')).toBeVisible()
  await expect(assistant.getByText('Late answer for Example.')).toHaveCount(0)
})

test('repeating Enter while the first conversation is being created sends only one question', async ({ page }) => {
  let created = 0
  let sent = 0
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/chat/sessions', async route => {
    if (route.request().method() !== 'POST') return route.fallback()
    created++
    await pending
    await route.fulfill({ json: { id: 'created', title: '', turns: 0, provider: 'example' } })
  })
  await page.route('**/api/chat', route => {
    sent++
    return route.fulfill({ contentType: 'text/event-stream', body:
      'data: {"type":"delta","text":"One question, one answer."}\n\ndata: {"type":"done","ok":true}\n\n' })
  })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  const composer = assistant.getByRole('textbox', { name: 'Message to the Assistant' })
  await composer.fill('Please explain.')
  await expect(assistant.getByRole('button', { name: 'send', exact: true })).toBeEnabled()
  await composer.press('Enter')
  await expect.poll(() => created).toBe(1)
  await composer.press('Enter')
  await expect(assistant.getByRole('button', { name: 'send', exact: true })).toBeDisabled()
  release()
  await expect(assistant.getByText('One question, one answer.')).toBeVisible()
  expect(created).toBe(1)
  expect(sent).toBe(1)
})

test('a failed Assistant read offers Retry and retains the question being composed', async ({ page }) => {
  let available = false
  await page.route('**/api/chat/state?*', route => route.fulfill(available ? { json: {
    model_default: 'model-a', groups: [{ provider: 'example', models: ['model-a'], installed: true, explainer: true }],
  } } : { status: 503, json: { detail: 'Temporarily offline' } }))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  const composer = assistant.getByRole('textbox', { name: 'Message to the Assistant' })
  await composer.fill('Keep this question.')
  const notice = assistant.getByRole('status').filter({ hasText: 'Couldn’t load this conversation.' })
  await expect(notice).toBeVisible()
  await expect(assistant.getByRole('button', { name: 'send', exact: true })).toBeDisabled()
  available = true
  await notice.getByRole('button', { name: 'Retry' }).click()
  await expect(notice).toHaveCount(0)
  await expect(composer).toHaveValue('Keep this question.')
  await expect(assistant.getByRole('button', { name: 'send', exact: true })).toBeEnabled()
})

test('a question can be edited by keyboard and an empty re-ask keeps its editor open', async ({ page }) => {
  await page.route('**/api/chat/sessions?*', route => route.fulfill({ json: { sessions: [{
    id: 'one', title: 'Existing conversation', turns: 2, model: 'model-a', provider: 'example',
    updated_at: '2026-09-08T00:00:00Z',
  }] } }))
  await page.route('**/api/chat/sessions/one', route => route.fulfill({ json: { turns: [
    { role: 'user', text: 'My original question.' }, { role: 'assistant', text: 'An earlier answer.' },
  ] } }))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  const question = assistant.getByRole('button', { name: 'My original question.', exact: true })
  await question.focus()
  await page.keyboard.press('Enter')
  await assistant.getByRole('button', { name: 'edit & re-ask', exact: true }).click()
  const editor = assistant.getByRole('textbox', { name: 'Edit question', exact: true })
  await expect(editor).toBeFocused()
  await editor.fill('')
  await editor.press('Enter')
  await expect(editor).toBeVisible()
  await expect(assistant.getByRole('button', { name: 're-ask', exact: true })).toBeDisabled()
  await editor.press('Escape')
  await expect(question).toBeFocused()
  await expect(assistant.getByText('An earlier answer.')).toBeVisible()
})

for (const latest of ['# Newer writing', '# Original text']) {
 for (const navigation of ['tab switch', 'Workspace return']) {
  test(`saving a document preserves later edits (${latest}) across a ${navigation}`, async ({ page }) => {
    await page.route('**/api/projects/Example/docs', route => route.fulfill({ json: { entries: [
      { path: 'user/notes.md', kind: 'file' }, { path: 'user/other.md', kind: 'file' },
    ] } }))
    let disk = '# Original text'
    let release!: () => void
    const pending = new Promise<void>(resolve => { release = resolve })
    const writes: { content: string; base_etag: string }[] = []
    await page.route('**/api/projects/Example/docs/user/notes.md', async route => {
      if (route.request().method() === 'GET') return route.fulfill({ json: { content: disk, etag: 'original' } })
      const body = route.request().postDataJSON()
      writes.push(body)
      if (writes.length === 1) await pending
      disk = body.content
      await route.fulfill({ json: { path: 'user/notes.md', etag: `saved-${writes.length}` } })
    })
    await page.route('**/api/projects/Example/docs/user/other.md', route => route.fulfill({ json: { content: '# Other document', etag: 'other' } }))
    await page.goto('/#/p/Example/workspace')
    await page.getByRole('treeitem', { name: /notes.md/ }).click()
    const source = page.getByLabel('document source', { exact: true })
    await expect(source).toHaveValue('# Original text')
    await source.fill('# Sent snapshot')
    const response = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith('/docs/user/notes.md'))
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect.poll(() => writes.length).toBe(1)
    if (navigation === 'Workspace return') {
      await page.getByRole('link', { name: 'Tasks', exact: true }).click()
      await page.getByRole('link', { name: 'Workspace', exact: true }).click()
      await expect(source).toHaveValue('# Sent snapshot')
      await expect(page.getByRole('button', { name: 'Saving…', exact: true })).toBeDisabled()
      await source.press('Control+s')
      expect(writes).toHaveLength(1)
    }
    await source.fill(latest)
    await page.getByRole('treeitem', { name: /other.md/ }).click()
    await expect(source).toHaveValue('# Other document')
    release()
    await (await response).finished()
    await expect(source).toHaveValue('# Other document')
    await page.getByRole('tab', { name: 'notes.md', exact: true }).click()
    await expect(source).toHaveValue(latest)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect.poll(() => writes.length).toBe(2)
    expect(writes[1]).toEqual({ content: latest, base_etag: 'saved-1' })
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)
  })
 }
}

test('a failed document read can be retried without closing its tab', async ({ page }) => {
  let available = false
  await page.route('**/api/projects/Example/docs/user/notes.md', route => route.fulfill(available
    ? { json: { content: '# Restored reading', etag: 'one' } }
    : { status: 503, json: { detail: 'Temporary read failure' } }))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('treeitem', { name: /notes.md/ }).click()
  const notice = page.getByRole('status').filter({ hasText: 'Couldn’t open this file.' })
  await expect(notice).toBeVisible()
  available = true
  await notice.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByLabel('document source')).toHaveValue('# Restored reading')
  await expect(page.getByRole('tab', { name: 'notes.md', exact: true })).toHaveCount(1)
})

test('saving task instructions retains newer edits and recognizes an undone change', async ({ page }) => {
  const writes: unknown[] = []
  const disk = { charter: 'Prove the claim.', word: '', settings: { axioms_whitelist: [], forbidden_lemmas: [] } }
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/problems/Example.first/intent', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: disk })
    const submitted = route.request().postDataJSON()
    writes.push(submitted)
    if (writes.length === 1) await pending
    Object.assign(disk, submitted)
    await route.fulfill({ json: {} })
  })
  await page.goto('/#/p/Example/tasks/Example.first')
  await page.getByRole('button', { name: 'Edit intent', exact: true }).click()
  const goal = page.getByRole('textbox', { name: 'The goal', exact: true })
  const save = page.getByRole('button', { name: 'Save', exact: true })
  await goal.fill('A change to undo.')
  await expect(save).toBeEnabled()
  await goal.fill('Prove the claim.')
  await expect(save).toBeDisabled()
  await goal.fill('The submitted claim.')
  await save.click()
  await expect.poll(() => writes.length).toBe(1)
  await goal.fill('The next claim.')
  release()
  await expect(save).toBeEnabled()
  await expect(page.getByRole('status').filter({ hasText: 'Unsaved changes' })).toBeVisible()
  await save.click()
  await expect(save).toBeDisabled()
  expect(writes).toEqual([{ charter: 'The submitted claim.' }, { charter: 'The next claim.' }])
  await expect(goal).toHaveValue('The next claim.')
})

test('task instruction drafts survive navigation and a save that finishes after returning', async ({ page }) => {
  const disk = { charter: 'Prove the claim.', word: '', settings: { axioms_whitelist: [], forbidden_lemmas: [] } }
  const writes: unknown[] = []
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/problems/Example.first/intent', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: disk })
    const submitted = route.request().postDataJSON()
    writes.push(submitted)
    if (writes.length === 1) await pending
    Object.assign(disk, submitted)
    await route.fulfill({ json: {} })
  })
  await page.goto('/#/p/Example/tasks/Example.first')
  await page.getByRole('button', { name: 'Edit intent', exact: true }).click()
  const goal = page.getByRole('textbox', { name: 'The goal', exact: true })
  await goal.fill('My draft claim.')
  await page.getByRole('link', { name: 'Timeline', exact: true }).click()
  expect(await page.evaluate(() => !window.dispatchEvent(new Event('beforeunload', { cancelable: true })))).toBe(true)
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await page.getByRole('link', { name: 'first', exact: true }).click()
  await page.getByRole('button', { name: 'Edit intent', exact: true }).click()
  await expect(goal).toHaveValue('My draft claim.')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(() => writes.length).toBe(1)
  await page.getByRole('link', { name: 'Timeline', exact: true }).click()
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await page.getByRole('link', { name: 'first', exact: true }).click()
  await page.getByRole('button', { name: 'Edit intent', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Saving…', exact: true })).toBeDisabled()
  await goal.fill('A newer claim after returning.')
  release()
  const save = page.getByRole('button', { name: 'Save', exact: true })
  await expect(save).toBeEnabled()
  await expect(goal).toHaveValue('A newer claim after returning.')
  await save.click()
  await expect(save).toBeDisabled()
  expect(writes).toEqual([{ charter: 'My draft claim.' }, { charter: 'A newer claim after returning.' }])
})

test('a failed document refresh leaves its unsaved draft available to edit', async ({ page }) => {
  let unavailable = false
  await page.route('**/api/projects/Example/docs/user/notes.md', route => unavailable
    ? route.fulfill({ status: 503, json: { detail: 'Temporarily unavailable' } })
    : route.fallback())
  await page.goto('/#/p/Example/workspace')
  const file = page.getByRole('treeitem', { name: /notes.md/ })
  await file.click()
  await page.getByLabel('document source').fill('# Keep this draft')
  await page.getByRole('tab', { name: 'notes.md', exact: true }).focus()
  await page.keyboard.press('Delete')
  unavailable = true
  await file.click()
  await expect(page.getByRole('status').filter({ hasText: 'Your writing is still here.' })).toBeVisible()
  await expect(page.getByLabel('document source')).toHaveValue('# Keep this draft')
})

test('unsaved document protection remains active after leaving Workspace and clears after undo', async ({ page }) => {
  const guarded = () => page.evaluate(() => !window.dispatchEvent(new Event('beforeunload', { cancelable: true })))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('treeitem', { name: /notes.md/ }).click()
  expect(await guarded()).toBe(false)
  const source = page.getByLabel('document source')
  const original = await source.inputValue()
  await source.fill('# Unsaved note')
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  expect(await guarded()).toBe(true)
  await page.getByRole('link', { name: 'Workspace', exact: true }).click()
  await source.fill(original)
  expect(await guarded()).toBe(false)
})

test('Escape returns from inline file operations to the tree without closing the Assistant', async ({ page }) => {
  await page.route('**/api/projects/Example/docs', route => route.fulfill({ json: { entries: [
    { path: 'user/notes.md', kind: 'file' }, { path: 'user/elsewhere', kind: 'dir' },
  ] } }))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  const file = page.getByRole('treeitem', { name: /notes.md/ })
  await file.click()
  await file.press('F2')
  await expect(page.getByRole('textbox', { name: 'Rename notes.md' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(file).toBeFocused()
  await expect(assistant).toBeVisible()
  await file.press('n')
  await expect(page.getByRole('textbox', { name: 'New file name' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(file).toBeFocused()
  await expect(assistant).toBeVisible()
  await file.press('m')
  await expect(page.getByRole('button', { name: 'user/elsewhere', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(file).toBeFocused()
  await expect(assistant).toBeVisible()
})

test('a project can be created from its name field and a refused attempt retains the form', async ({ page }) => {
  const writes: unknown[] = []
  await page.route('**/api/projects', route => {
    if (route.request().method() === 'GET') return route.fallback()
    writes.push(route.request().postDataJSON())
    return route.fulfill(writes.length === 1
      ? { status: 503, json: { detail: 'Temporary creation failure' } }
      : { json: { project: 'NewExample' } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'new project', exact: true }).click()
  const name = page.getByRole('textbox', { name: 'Project name', exact: true })
  await expect(name).toBeFocused()
  await name.fill('  NewExample  ')
  const description = page.getByRole('textbox', { name: 'Project description (optional)' })
  await description.fill('A place for the next question.')
  await name.press('Enter')
  await expect(page.getByText('Temporary creation failure', { exact: false })).toBeVisible()
  await expect(name).toHaveValue('  NewExample  ')
  await expect(description).toHaveValue('A place for the next question.')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page).toHaveURL(/#\/p\/NewExample\/tasks$/)
  expect(writes).toEqual(Array(2).fill({ name: 'NewExample', description: 'A place for the next question.' }))
})

test('project renaming checks for documents before offering a change', async ({ page }) => {
  let hasFiles = true
  let writes = 0
  await page.route('**/api/projects/Example/docs', route => route.fulfill({ json: { entries: hasFiles ? [{ kind: 'file', path: 'user/notes.md' }] : [] } }))
  await page.route('**/api/projects/Example', route => {
    writes++
    return route.fulfill({ json: { project: 'Renamed' } })
  })
  await page.goto('/#/')
  const opener = page.getByRole('button', { name: 'rename…', exact: true })
  await opener.focus()
  await opener.press('Enter')
  const name = page.getByRole('textbox', { name: 'Project name', exact: true })
  await expect(name).toBeFocused()
  await name.fill('Renamed')
  await expect(page.getByRole('status').filter({ hasText: 'leave their folder behind' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Rename', exact: true })).toBeDisabled()
  await name.press('Enter')
  expect(writes).toBe(0)
  await page.keyboard.press('Escape')
  await expect(opener).toBeFocused()
  hasFiles = false
  await opener.press('Enter')
  await name.fill('Renamed')
  await page.getByRole('button', { name: 'Rename', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(writes).toBe(1)
})

test('a long conversation list keeps the composer visible and returns keyboard focus when closed', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 })
  const sessions = Array.from({ length: 40 }, (_, i) => ({ id: `s${i}`, title: `Conversation ${i + 1}`,
    turns: 1, model: 'model-a', provider: 'example', updated_at: '2026-09-08T00:00:00Z' }))
  await page.route('**/api/chat/sessions?*', route => route.fulfill({ json: { sessions } }))
  await page.route('**/api/chat/sessions/*', route => route.fulfill({ json: { turns: [] } }))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
  const trigger = assistant.getByRole('button', { name: 'conversations', exact: true })
  await trigger.click()
  const list = assistant.locator('[aria-label="conversation list"]')
  expect(await list.evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true)
  await expect(assistant.getByRole('textbox', { name: 'Message to the Assistant' })).toBeInViewport()
  await page.keyboard.press('F2')
  await expect(assistant.getByRole('textbox', { name: 'Conversation title' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(assistant.getByRole('button', { name: /^Conversation 1 / })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
  await expect(list).toHaveCount(0)
  await expect(assistant).toBeVisible()
})

test('a refused clipboard write selects the file path and does not claim it was copied', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { configurable: true,
    value: { writeText: () => Promise.reject(new Error('Clipboard denied')) } }))
  const path = 'D:\\Research\\Example\\user\\notes.md'
  await page.route('**/api/docs/reveal', route => route.fulfill({ json: { revealed: false, path, detail: 'Open this file on the engine’s machine.' } }))
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('treeitem', { name: /notes.md/ }).click()
  await page.getByRole('button', { name: 'show in Explorer', exact: true }).click()
  const copy = page.getByRole('button', { name: 'Copy file path', exact: true })
  await copy.click()
  await expect(page.getByRole('status').filter({ hasText: 'Couldn’t copy automatically.' })).toBeVisible()
  const field = page.getByRole('textbox', { name: 'File path', exact: true })
  await expect(field).toBeFocused()
  expect(await field.evaluate((el: HTMLInputElement) => el.value.slice(el.selectionStart!, el.selectionEnd!))).toBe(path)
  await expect(copy).toHaveText('copy')
  await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true,
    value: { writeText: () => Promise.resolve() } }))
  await copy.click()
  await expect(copy).toHaveText('copied')
  await expect(page.getByRole('status').filter({ hasText: 'Couldn’t copy automatically.' })).toHaveCount(0)
})

for (const navigation of [false, true]) {
  test(`a completed document save keeps writing and focus during a delayed refresh${navigation ? ' after returning' : ''}`, async ({ page }) => {
    let disk = '# Original text'
    let written = false
    let releaseWrite!: () => void
    let releaseRead!: () => void
    const pendingWrite = new Promise<void>(resolve => { releaseWrite = resolve })
    const pendingRead = new Promise<void>(resolve => { releaseRead = resolve })
    await page.route('**/api/projects/Example/docs/user/notes.md', async route => {
      if (route.request().method() === 'PUT') {
        await pendingWrite
        disk = route.request().postDataJSON().content
        written = true
        return route.fulfill({ json: { etag: 'saved' } })
      }
      if (written) await pendingRead
      return route.fulfill({ json: { content: disk, etag: written ? 'saved' : 'original' } })
    })
    await page.goto('/#/p/Example/workspace')
    await page.getByRole('treeitem', { name: /notes.md/ }).click()
    const source = page.getByLabel('document source')
    await source.fill('# Saved snapshot')
    const put = page.waitForRequest(r => r.method() === 'PUT')
    await source.press('Control+s')
    await put
    if (navigation) {
      await page.getByRole('link', { name: 'Tasks', exact: true }).click()
      await page.getByRole('link', { name: 'Workspace', exact: true }).click()
      await expect(source).toHaveValue('# Saved snapshot')
      await source.focus()
    }
    await source.press('Home')
    const read = page.waitForRequest(r => written && r.method() === 'GET' && r.url().endsWith('/docs/user/notes.md'))
    releaseWrite()
    await read
    await expect(source).toBeFocused()
    await expect(source).toHaveValue('# Saved snapshot')
    await page.keyboard.type('++')
    releaseRead()
    await expect(source).toHaveValue('++# Saved snapshot')
    await expect(source).toBeFocused()
  })
}

test('a late TeX render cannot replace the newer saved rendering', async ({ page }) => {
  let disk = 'Original TeX source'
  await page.route('**/api/projects/Example/docs', route => route.fulfill({ json: { entries: [{ path: 'user/notes.tex', kind: 'file' }] } }))
  await page.route('**/api/projects/Example/docs/user/notes.tex', route => {
    if (route.request().method() === 'PUT') disk = route.request().postDataJSON().content
    return route.fulfill({ json: { content: disk, etag: disk } })
  })
  let calls = 0
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/projects/Example/tex', async route => {
    const call = ++calls
    if (call === 1) await pending
    await route.fulfill({ json: { status: 'no_engine', engine: null,
      detail: call === 1 ? 'Old render result' : 'Newest render result' } })
  })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('treeitem', { name: /notes.tex/ }).click()
  await expect.poll(() => calls).toBe(1)
  const source = page.getByLabel('document source')
  await source.fill('New TeX source')
  await source.press('Control+s')
  await expect(page.getByText('Newest render result', { exact: true })).toBeVisible()
  const response = page.waitForResponse(r => r.url().endsWith('/Example/tex'))
  release()
  await (await response).finished()
  await expect(page.getByText('Old render result', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Newest render result', { exact: true })).toBeVisible()
  await source.fill('Another change')
  await expect(page.getByText('Changed since last render', { exact: true })).toBeVisible()
})

test('task creation holds its submitted fields and restores them after a failed attempt', async ({ page }) => {
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/problems/create', async route => {
    await pending
    await route.fulfill({ status: 503, json: { detail: 'Temporary task creation failure' } })
  })
  await page.goto('/#/new/Example')
  const name = page.getByRole('textbox', { name: 'name', exact: true })
  const goal = page.getByRole('textbox', { name: 'what should be proved?', exact: true })
  const word = page.getByRole('textbox', { name: 'standing instructions (optional)', exact: true })
  await name.fill('Example.third')
  await goal.fill('Prove the next claim.')
  await word.fill('Keep the definitions explicit.')
  await page.getByRole('button', { name: 'Create task', exact: true }).click()
  await expect(goal).toBeDisabled()
  await expect(name).toBeDisabled()
  await expect(word).toBeDisabled()
  release()
  await expect(page.getByText('Temporary task creation failure', { exact: false })).toBeVisible()
  await expect(goal).toBeEnabled()
  await expect(name).toHaveValue('Example.third')
  await expect(goal).toHaveValue('Prove the next claim.')
  await expect(word).toHaveValue('Keep the definitions explicit.')
})

test('a compact empty Workspace uses its space to choose the first file', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('button', { name: 'Assistant', exact: true }).click()
  const file = page.getByRole('treeitem', { name: /notes.md/ })
  await expect(file).toBeInViewport()
  await file.click()
  await expect(page.getByLabel('document source')).toBeVisible()
  await page.getByRole('button', { name: 'Hide file list', exact: true }).click()
  await expect(page.getByLabel('document source')).toBeVisible()
  expect(await page.locator('main').last().evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
})

for (const width of [390, 768, 1440]) {
  test(`Workspace keeps reading room with the Assistant at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => localStorage.setItem('asterism.chat.width', '900'))
    await page.goto('/#/p/Example/workspace')
    await page.getByRole('treeitem', { name: /notes.md/ }).click()
    await expect(page.getByLabel('document source')).toBeVisible()
    await page.getByRole('button', { name: 'Assistant', exact: true }).click()
    const assistant = page.getByRole('complementary', { name: 'assistant', exact: true })
    await expect(assistant).toBeVisible()
    const reading = (await page.locator('[data-app-content]').boundingBox())!
    const chat = (await assistant.boundingBox())!
    expect(reading.width).toBeGreaterThanOrEqual(380)
    expect(reading.height).toBeGreaterThan(250)
    expect(chat.x + chat.width).toBeLessThanOrEqual(width + 1)
    expect(chat.y + chat.height).toBeLessThanOrEqual(901)
    const files = (await page.getByRole('complementary', { name: 'Files', exact: true }).boundingBox())!
    const source = (await page.getByLabel('document source').boundingBox())!
    expect(source.width).toBeGreaterThan(100)
    if (reading.width < 768) expect(files.y + files.height).toBeLessThanOrEqual(source.y)
    if (width < 768) expect(reading.y + reading.height).toBeLessThanOrEqual(chat.y)
    else expect(reading.x + reading.width).toBeLessThanOrEqual(chat.x)
    await page.screenshot({ path: `test-results/workspace-assistant-${width}.png` })
  })
}

test('the compact task selector changes tasks without a column taking reading space', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto('/#/p/Example/tasks/Example.first')
  const pick = page.getByLabel('Task', { exact: true })
  for (const link of await page.getByRole('navigation', { name: 'Project sections', exact: true }).getByRole('link').all())
    await expect(link).toBeInViewport({ ratio: 1 })
  await expect(pick).toBeVisible()
  await pick.selectOption('Example.second')
  await expect(page).toHaveURL(/tasks\/Example.second$/)
  await expect(page.getByRole('button', { name: 'Edit intent' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Hide task list' })).toBeHidden()
})

test('earlier history stops at the last page and a failed page can be retried', async ({ page }) => {
  let attempts = 0
  const event = (id: string, label: string) => ({
    id, label, at: '2026-09-08T00:00:00Z', kind: 'proved', object_kind: 'goal',
    goal_id: 1, problem: 'Example.first', note: null, body: null, group_id: null,
    object_group_id: null, approx: false, n: null, batch_id: null, path: null,
  })
  await page.route('**/api/projects/Example/events*', route => {
    if (new URL(route.request().url()).searchParams.has('before')) {
      attempts++
      return attempts === 1
        ? route.fulfill({ status: 503, json: { detail: 'Temporary reading failure' } })
        : route.fulfill({ json: { events: [event('old', 'earlier_step')], next_before: null } })
    }
    return route.fulfill({ json: { events: [event('new', 'latest_step')], next_before: 'older-page' } })
  })
  await page.goto('/#/p/Example/timeline')
  await page.getByRole('button', { name: 'load earlier', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Could not load earlier events')
  await page.getByRole('button', { name: 'load earlier', exact: true }).click()
  await expect(page.getByRole('button', { name: /earlier_step/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'load earlier', exact: true })).toHaveCount(0)
  await expect(page.getByRole('status')).toHaveCount(0)
  expect(attempts).toBe(2)
})

test('a new task fits a narrow screen and Cancel returns to its project', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto('/#/new/Example')
  const name = page.getByRole('textbox', { name: 'name', exact: true })
  await expect(name).toHaveAttribute('placeholder', 'Example.my_theorem')
  await name.fill('Example.a')
  await page.getByRole('textbox', { name: 'what should be proved?' }).fill('Prove the statement.')
  expect(await page.locator('main').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page).toHaveURL(/#\/p\/Example\/tasks$/)
})

test('event details can be opened by keyboard and use the full narrow reading width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 })
  await page.route('**/api/projects/Example/events*', route => route.fulfill({ json: { events: [{
    id: 'one', at: '2026-09-08T00:00:00Z', kind: 'proved', label: 'important_step',
    goal_id: 1, object_kind: 'goal', object_group_id: null, n: null,
    problem: 'Example.first', body: 'The full reasoning remains available.', note: null,
  }], next_before: null } }))
  await page.goto('/#/p/Example/timeline')
  const toggle = page.getByRole('button', { name: 'Details for important_step', exact: true })
  await toggle.focus()
  await page.keyboard.press('Space')
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('The full reasoning remains available.')).toBeVisible()
  expect((await page.locator('[data-event-body]').boundingBox())!.width).toBeGreaterThan(300)
  await page.keyboard.press('Enter')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
})

test('the preview only asks for attention when the draft has formatting issues', async ({ page }) => {
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('treeitem', { name: /notes.md/ }).click()
  const source = page.getByLabel('document source')
  const preview = page.locator('[data-render-pane]')
  await expect(preview.getByRole('heading', { name: 'Research notes' })).toBeVisible()
  await expect(preview.getByText(/formatting issue/)).toHaveCount(0)
  await source.fill('# Notes\n\n```lean\nexample : True := by trivial')
  await preview.getByText('1 formatting issue', { exact: true }).click()
  await expect(preview.getByText('Line 3')).toBeVisible()
  await source.fill('# Notes\n\nReadable again.')
  await expect(preview.getByText(/formatting issue/)).toHaveCount(0)
})

test('a narrow document stacks its panes and the divider follows the reading direction', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto('/#/p/Example/workspace')
  await page.getByRole('treeitem', { name: /notes.md/ }).click()
  const divider = page.getByRole('separator', { name: 'resize the panes' })
  await expect(divider).toHaveAttribute('aria-orientation', 'horizontal')
  const source = page.locator('[data-source-pane]')
  const render = page.locator('[data-render-pane]')
  await expect(source).toBeVisible()
  await expect(render).toBeVisible()
  const sourceBox = (await source.boundingBox())!
  const renderBox = (await render.boundingBox())!
  expect(sourceBox.width).toBeGreaterThan(350)
  expect(sourceBox.y + sourceBox.height).toBeLessThanOrEqual(renderBox.y + 1)
  const before = Number(await divider.getAttribute('aria-valuenow'))
  await divider.focus()
  await page.keyboard.press('ArrowDown')
  expect(Number(await divider.getAttribute('aria-valuenow'))).toBeGreaterThan(before)
  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(divider).toHaveAttribute('aria-orientation', 'vertical')
})

test('an unavailable file list offers recovery and never calls itself empty', async ({ page }) => {
  let failed = true
  await page.route('**/api/projects/Example/docs', route => failed
    ? route.fulfill({ status: 503, json: { detail: 'Files are temporarily unavailable' } })
    : route.fallback())
  await page.goto('/#/p/Example/workspace')
  const rail = page.getByRole('complementary', { name: 'Files', exact: true })
  await expect(rail.getByRole('status')).toContainText('Files unavailable')
  await expect(rail.getByText(/nothing here yet/)).toHaveCount(0)
  failed = false
  await rail.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(page.getByRole('treeitem', { name: /notes.md/ })).toBeVisible()
  await page.getByRole('searchbox', { name: 'Find a file' }).fill('absent-file')
  await expect(rail.getByRole('status')).toContainText('No files match')
  await rail.getByRole('button', { name: 'Clear search', exact: true }).click()
  await expect(page.getByRole('treeitem', { name: /notes.md/ })).toBeVisible()
})

test('closing a document tab by keyboard keeps focus in the remaining tabs', async ({ page }) => {
  await page.route('**/api/projects/Example/docs', route => route.fulfill({ json: {
    entries: [{ path: 'user', kind: 'dir' }, ...['one', 'two', 'three'].map(name => ({ path: `user/${name}.md`, kind: 'file' }))],
  } }))
  await page.route('**/api/projects/Example/docs/user/*', route => route.fulfill({ json: { content: '# Notes', etag: 'one' } }))
  await page.goto('/#/p/Example/workspace')
  for (const name of ['one', 'two', 'three']) await page.getByRole('treeitem', { name: new RegExp(`${name}.md`) }).click()
  await page.getByRole('tab', { name: 'two.md', exact: true }).focus()
  await page.keyboard.press('Delete')
  await expect(page.getByRole('tab', { name: 'two.md', exact: true })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'three.md', exact: true })).toBeFocused()
  await page.keyboard.press('Delete')
  await expect(page.getByRole('tab', { name: 'one.md', exact: true })).toBeFocused()
  await expect(page.getByRole('tab', { name: 'one.md', exact: true })).toHaveAttribute('aria-selected', 'true')
})

test('closing the last document returns to Files and reopening preserves its draft', async ({ page }) => {
  await page.goto('/#/p/Example/workspace')
  const file = page.getByRole('treeitem', { name: /notes.md/ })
  await file.click()
  await page.getByLabel('document source').fill('# My unsaved draft')
  await page.getByRole('tab', { name: 'notes.md', exact: true }).focus()
  await page.keyboard.press('Delete')
  await expect(page.getByLabel('Find a file', { exact: true })).toBeFocused()
  await file.click()
  await expect(page.getByLabel('document source')).toHaveValue('# My unsaved draft')
  await page.getByRole('button', { name: 'Hide file list', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Show file list', exact: true })).toBeFocused()
  await page.getByRole('tab', { name: 'notes.md', exact: true }).focus()
  await page.keyboard.press('Delete')
  await expect(page.getByRole('button', { name: 'Show file list', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Show file list', exact: true }).click()
  await expect(page.getByLabel('Find a file', { exact: true })).toBeFocused()
})

test('reviewing an edited amendment preserves the draft and submits the reviewed text', async ({ page }) => {
  let submitted: unknown = null
  await page.route('**/api/inbox?project=Example', route => route.fulfill({ json: {
    amends: [{ id: 7, problem: 'Example.first', file: 'charter', title: 'Clarify the claim',
      question: 'The current wording is ambiguous.', reason: '', current_body: 'The old claim.',
      proposed_body: 'The proposed claim.', created_at: '2026-09-08T00:00:00Z' }], signoffs: [],
  } }))
  await page.route('**/api/inbox/amend/7/resolve', route => {
    submitted = route.request().postDataJSON()
    return route.fulfill({ json: {} })
  })
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto('/#/p/Example/tasks')
  await page.getByRole('button', { name: 'Edit before accepting', exact: true }).click()
  await page.getByRole('textbox', { name: 'Proposed amendment' }).fill('The claim with my correction.')
  await page.getByRole('button', { name: 'Back to diff', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Accept with edits' })).toBeVisible()
  await page.getByRole('button', { name: 'Edit before accepting', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Proposed amendment' })).toHaveValue('The claim with my correction.')
  expect(await page.locator('main').last().evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  await page.getByRole('button', { name: 'Accept with edits' }).click()
  await expect.poll(() => submitted).toEqual({ action: 'accept', body: 'The claim with my correction.' })
})
