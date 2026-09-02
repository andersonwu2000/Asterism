/*
 * One reading per URL, shared by whoever is polling it.
 *
 * Four components on the Tasks section poll `/api/daemon` and two poll
 * `/api/meta` on the Engine room — the same bytes, fetched once per
 * component per interval, because `usePoll` is a private loop and knows
 * nothing about its siblings. Two rules fix that without any component
 * having to know about any other:
 *
 *   - A cached reading is served when it is YOUNGER THAN THE ASKER'S OWN
 *     INTERVAL. That is the honest bound: a 3s poller handed a 1s-old
 *     reading is getting something fresher than its own loop would have
 *     produced, so it has lost nothing; the same poller handed a 3s-old
 *     one would be reading its own staleness back, so that is a miss.
 *   - Two askers in flight at once share the flight, not the request.
 *
 * `etag` rides along for the readings big enough to be conditional (the
 * Sky's ~800KB problem detail). A 304 means "the body did not move" and
 * therefore ages the READING forward (`touch`) while keeping the body.
 *
 * A failed flight is forgotten, never cached: the next poll must be a
 * real retry, not a replay of the failure.
 */

interface Slot {
  at: number
  data: unknown
  etag: string | null
}

const slots = new Map<string, Slot>()
const inflight = new Map<string, Promise<unknown>>()

/** The cached reading, if it is younger than `maxAgeMs`. */
export function peek<T>(url: string, maxAgeMs: number, now = Date.now()): T | undefined {
  const slot = slots.get(url)
  if (!slot) return undefined
  if (now - slot.at >= maxAgeMs) return undefined
  return slot.data as T
}

/** The whole reading regardless of age — what a 304 says is still current. */
export function kept<T>(url: string): T | undefined {
  return slots.get(url)?.data as T | undefined
}

export function etagOf(url: string): string | null {
  return slots.get(url)?.etag ?? null
}

export function put(
  url: string,
  data: unknown,
  etag: string | null = null,
  now = Date.now(),
): void {
  slots.set(url, { at: now, data, etag })
}

/** The body did not change, but the reading is current again. */
export function touch(url: string, now = Date.now()): void {
  const slot = slots.get(url)
  if (slot) slot.at = now
}

/** One flight per URL: a second caller joins the first instead of
 * opening its own. */
export function shared<T>(url: string, run: () => Promise<T>): Promise<T> {
  const live = inflight.get(url)
  if (live) return live as Promise<T>
  const flight = run().finally(() => {
    if (inflight.get(url) === flight) inflight.delete(url)
  })
  inflight.set(url, flight)
  return flight
}

export function clearPollCache(url?: string): void {
  if (url === undefined) {
    slots.clear()
    inflight.clear()
    return
  }
  slots.delete(url)
  inflight.delete(url)
}
