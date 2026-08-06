/*
 * Light / dark.
 *
 * One achromatic language, two ends of the lightness scale: the ink
 * ladder and the elevation ladder invert together, so every rule in
 * DESIGN.md still holds — loudest is still furthest from the page,
 * settled still recedes, depth is still stepped lightness. Code hues
 * keep their hue and trade lightness for the new background.
 *
 * The choice lives in one attribute on <html>; every colour in the
 * app is a token, so nothing else has to know. `index.html` applies
 * the stored choice BEFORE the first paint — a dark page flashing
 * white on every load is the one thing a theme switch must not do.
 */

export type Theme = 'dark' | 'light'

const KEY = 'asterism.theme'

/** The stored choice, or null when the reader has never chosen (the
 * system preference stands in — and keeps standing in, so a machine
 * that switches at dusk carries the app with it). */
export function storedTheme(): Theme | null {
  const v = localStorage.getItem(KEY)
  return v === 'dark' || v === 'light' ? v : null
}

export function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches
    ? 'light'
    : 'dark'
}

export function currentTheme(): Theme {
  return storedTheme() ?? systemTheme()
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t
}

export function setTheme(t: Theme): void {
  localStorage.setItem(KEY, t)
  applyTheme(t)
}
