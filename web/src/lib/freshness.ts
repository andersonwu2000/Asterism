import type { Meta } from './types'

/*
 * Is the process answering us older than the code it is serving?
 *
 * Two pieces of evidence, one question. `version`/`disk_version` is the
 * release stamp, and it only exists in an installed build; `code` is the
 * fingerprint of the source tree this process loaded against the one on
 * disk now, which every workspace has. The old banner read only the
 * first, so in a dev workspace it compared null to null and stayed
 * quiet while a serve started before a commit answered with its old
 * endpoints under the new bundle's pages.
 *
 * A stale process cannot know which of its own answers are lies — this
 * is the one thing it can still tell the reader for certain.
 */
export function serverIsStale(meta: Meta | null): boolean {
  if (!meta) return false
  const v = meta.version ?? null
  const disk = meta.disk_version ?? null
  if (v && disk && v !== disk) return true
  const code = meta.code ?? null
  return Boolean(code?.loaded && code.disk && code.loaded !== code.disk)
}

/** The short forms the banner shows — a release pair when there is one,
 * the code fingerprints otherwise. Null when nothing differs. */
export function stalePair(meta: Meta | null): [string, string] | null {
  if (!serverIsStale(meta) || !meta) return null
  const v = meta.version ?? null
  const disk = meta.disk_version ?? null
  if (v && disk && v !== disk) return [v.slice(0, 8), disk.slice(0, 8)]
  const code = meta.code!
  return [code.loaded.slice(0, 8), code.disk.slice(0, 8)]
}
