/*
 * Design-review screenshots: every top-level surface, both themes.
 * Scratch output under web/.shots (gitignored) — taken, looked at,
 * thrown away. Run against a dev server or a live serve:
 *
 *   node scripts/shots.mjs [baseURL] [prefix]
 */
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173'
const prefix = process.argv[3] ?? 'p6'
const out = new URL('../.shots/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
mkdirSync(out, { recursive: true })

const api = async (path) => (await fetch(base + path)).json()

const projects = (await api('/api/projects')).projects ?? []
const populated = projects
  .filter((p) => p.problems >= 2)
  .sort((a, b) => a.problems - b.problems)[0] ?? projects[0]
const rows =
  (await api(`/api/problems?project=${encodeURIComponent(populated.name)}`)).problems ?? []
const task = rows[0]?.name

const pages = [
  ['projects', '/#/'],
  ['tasks', `/#/p/${populated.name}/tasks`],
  ['task', `/#/p/${populated.name}/tasks/${task}`],
  ['sky', `/#/p/${populated.name}/sky`],
  ['groups', `/#/p/${populated.name}/groups`],
  ['engine', `/#/p/${populated.name}/engine`],
  ['timeline', `/#/p/${populated.name}/timeline`],
  ['docs', `/#/p/${populated.name}/docs`],
  ['settings', '/#/settings'],
  ['new', '/#/new'],
]

const browser = await chromium.launch()
for (const [w, h] of [
  [1440, 900],
  [1024, 768],
]) {
  for (const theme of ['dark', 'light']) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } })
    await ctx.addInitScript(`localStorage.setItem('asterism.theme', ${JSON.stringify(theme)})`)
    const page = await ctx.newPage()
    for (const [name, path] of pages) {
      if (w === 1024 && !['projects', 'tasks', 'sky', 'engine'].includes(name)) continue
      await page.goto(base + path)
      await page.waitForTimeout(4500)
      await page.screenshot({ path: `${out}${prefix}-${name}-${theme}-${w}.png` })
      console.log(`${prefix}-${name}-${theme}-${w}.png`)
    }
    await ctx.close()
  }
}
await browser.close()
