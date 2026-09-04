import { groupCode } from './format'

/*
 * The Documents shelf's reading of its own list (human_interface_design
 * .md §3.6, theory_wake_design.md §4).
 *
 * `user/` is a person's folder and reads like one: alphabetical, the
 * order they filed it in. `agent/` is not a folder a person keeps —
 * the theory layer lands one document per wake, and the question a
 * reader arrives with is "what did it write, and when", never "what
 * begins with a". So the agent area is a LOG in the shelf's clothing:
 * newest first, each row naming its group, its day and what the review
 * cost.
 *
 * The three facts are nowhere in the prose (DESIGN.md, "a row names an
 * object"): the API carries them from `theory_documents`, and the
 * ordering and the wording of the line are the parts with a right
 * answer, so they live here and are tested rather than inline in the
 * rail that draws them (`components/DocRail.tsx`, through
 * `lib/docShell`'s `railGroups`).
 */

/** The record the listing carries for a document the theory layer
 * wrote. Absent — not null — on every other entry: a plain `.md` under
 * `agent/` is a file, and there is no row to show. */
export interface TheoryMeta {
  group_id: number | null
  created_at: string
  status: 'accepted' | 'rejected'
  rounds: number
  /** the question the document was written to answer */
  objective: string
  /** the reviewer's own sentence per criterion, as the rubric's parser
   * renders it — four lines, or none when the row's verdict was
   * unreadable */
  verdict: string[]
}

export interface DocEntry {
  path: string
  kind: 'file' | 'dir'
  size?: number
  theory?: TheoryMeta | null
}

/* Locale PINNED, on the Timeline's ruling: `undefined` follows the
 * browser and drops 下午04:12 into an English-voiced page. Its two
 * locales, for its two reasons — en-US names the months the Timeline
 * names them (`Sept` is en-GB's spelling and would read as a second
 * calendar), en-GB gives the 24h clock. */
const DAY_FMT = new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'short' })
const TIME_FMT = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

/** `4 Sep 16:12`, or '' for a stamp that will not parse. Compact on
 * purpose: it sits under a filename in the narrowest column on the
 * page, and the year is the one part a document written this week
 * never needs to say. Day before month — the shelf reads left to right
 * from the smallest unit, the way the clock beside it does. */
function stamp(iso: string): string {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const d = new Date(t)
  const parts = DAY_FMT.formatToParts(d)
  const at = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return `${at('day')} ${at('month')} ${TIME_FMT.format(d)}`
}

/** One theory document's second line: whose wall, when, and what the
 * review cost. A document written for no group simply omits that
 * segment — "(none)" would spend a reader's attention saying nothing. */
export function theoryLine(t: TheoryMeta): string {
  const when = stamp(t.created_at)
  return [
    t.group_id === null ? '' : groupCode(t.group_id),
    when,
    `${t.status}, ${t.rounds} ${t.rounds === 1 ? 'round' : 'rounds'}`,
  ]
    .filter((s) => s !== '')
    .join(' · ')
}

/** The `agent/` area's rows, in the order that area is read in.
 *
 * What the theory layer wrote comes first, newest first; everything
 * else keeps the tree's own order below it, so a `papers/` folder still
 * nests the way the path says. The area folder itself is not a row —
 * it is the heading above these.
 */
export function agentRows(entries: DocEntry[]): DocEntry[] {
  const rows = entries.filter((e) => e.path.startsWith('agent/'))
  const theory = rows.filter((e) => e.theory != null)
  const rest = rows.filter((e) => e.theory == null)
  theory.sort(
    (a, b) =>
      (b.theory?.created_at ?? '').localeCompare(a.theory?.created_at ?? '') ||
      a.path.localeCompare(b.path),
  )
  return [...theory, ...rest]
}
