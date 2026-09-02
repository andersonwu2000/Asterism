import { useState } from 'react'
import { usePoll } from '../lib/api'
import { usePublishFocus } from '../lib/focus'
import { Link } from '../lib/router'
import { Lean } from '../lib/lean'
import { renderProse } from '../lib/prose'
import { frameClass } from '../lib/textFrame'
import { Select } from '../components/ui'
import DocShelf from '../components/DocShelf'
import { projectPath } from '../lib/projectRoute'
import type { ProblemDetail } from '../lib/types'

/*
 * Documents — the Project's file column (human_interface_design.md
 * §1.4-2, last bullet: "次級選單：檔案列表", and §1.2 for what it will
 * eventually hold).
 *
 * Two roots today, because two kinds of file exist and a reader looking
 * for "the files" means either:
 *   proofs     what the engine wrote for the task in the column
 *   documents  the Project's own shelf (§3.6 `_docs/`), Assistant
 *              output under `agent/` and yours under `user/`
 *
 * The proofs root is read-only — it is the engine's own writing, and
 * the chokepoint that produces it is not an HTTP door. The documents
 * root is the Project's own shelf and IS writable (§1.2, §3.6); it
 * lives in `DocShelf`, which owns the two areas, the editor and the
 * refusals.
 */

function Body({ path, content }: { path: string; content: string }) {
  if (path.endsWith('.lean'))
    return (
      <pre className={frameClass({ frame: false, size: 'md', wrap: false })}>
        <Lean code={content} />
      </pre>
    )
  if (path.endsWith('.md') || path.endsWith('.tex'))
    return (
      <div className="max-w-[78ch] text-[13px] leading-relaxed text-ink-dim">
        {renderProse(content, { mode: 'document', frontmatter: true })}
      </div>
    )
  return (
    <pre className={frameClass({ frame: false, size: 'md', wrap: false })}>{content}</pre>
  )
}

/** The engine's own output for the task in the column: Root, Defs and
 * everything under proofs/. */
function ProofsView({
  problem,
  file,
  onPick,
}: {
  problem: string
  file: string | null
  onPick: (path: string) => void
}) {
  const { data: detail } = usePoll<ProblemDetail>(
    `/api/problems/${encodeURIComponent(problem)}`,
    30000,
  )
  // REPORT.md heads the list when the Ingest terminal wrote one (HID
  // §3.4): it is the only file here written FOR a reader, so it is
  // also what the column opens on. `ingest_report` is the DB's SoT and
  // the file is its render, so listing on the column can never offer a
  // file that is not there.
  const hasReport = Boolean((detail?.ingest_report ?? '').trim())
  const files = detail
    ? [
        ...(hasReport ? ['REPORT.md'] : []),
        'Root.lean',
        'Defs.lean',
        ...detail.proof_files.map((f) => `proofs/${f}`),
      ]
    : []
  // Root.lean heads the Lean list because it is the statement — but a
  // v40 task may not have one on disk, and opening on "not found" is a
  // poor first sentence. The proof files are listed FROM disk, so the
  // first of those is a file that certainly exists.
  const fallback = hasReport
    ? 'REPORT.md'
    : (files.find((f) => f.startsWith('proofs/')) ?? files[0] ?? null)
  const selected = file && files.includes(file) ? file : fallback
  const { data, error } = usePoll<{ path: string; content: string }>(
    selected
      ? `/api/problems/${encodeURIComponent(problem)}/file?path=${encodeURIComponent(selected)}`
      : null,
    10000,
  )
  return (
    <>
      <div className="w-72 shrink-0 overflow-y-auto border-r border-edge py-2">
        {files.map((f, i) => (
          <div key={f}>
            {/* one "proofs/" header instead of a 130-row prefix wall */}
            {f.startsWith('proofs/') && !files[i - 1]?.startsWith('proofs/') && (
              <div className="mt-2 px-4 pb-1 text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase">
                proofs · {files.length - i}
              </div>
            )}
            <button
              className={`block w-full truncate px-4 py-1.5 text-left font-mono text-xs ${
                f === selected ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
              }`}
              onClick={() => onPick(f)}
              title={f}
            >
              {f.startsWith('proofs/L_')
                ? f.slice('proofs/L_'.length)
                : f.startsWith('proofs/')
                  ? f.slice('proofs/'.length)
                  : f}
            </button>
          </div>
        ))}
      </div>
      <div className="min-w-0 flex-1 overflow-auto p-4">
        {error && !data && (
          <div className="text-xs text-ink-faint">
            {selected} — not found (the file may not exist for this task).
          </div>
        )}
        {data && data.path === selected && <Body path={selected} content={data.content} />}
      </div>
    </>
  )
}

export default function Docs({
  project,
  problem,
  tasks,
  path,
}: {
  project: string
  /** the task the column opens on — its proofs are one of the two roots */
  problem: string | null
  /** the shelf, so the proofs root can be pointed at another task
   * without leaving the section (this section hides the task column —
   * its own column is the files) */
  tasks: string[]
  /** `<root>/<path…>` out of the address */
  path: string[]
}) {
  const [root, setRoot] = useState<'proofs' | 'shelf'>(
    path[0] === 'shelf' ? 'shelf' : 'proofs',
  )
  // the address seeds the selection (a goal panel's file link lands
  // here); after that the column owns it, so clicking through files
  // does not fill the reader's history with one entry per file
  const [sel, setSel] = useState<string | null>(path.slice(1).join('/') || null)
  const [task, setTask] = useState<string | null>(problem)
  const [docPath, setDocPath] = useState<string | null>(null)
  const shown = task && tasks.includes(task) ? task : problem
  // ONE author for the screen's focus: the shelf hands its selection up
  // rather than publishing beside this, so the two cannot overwrite
  // each other's answer to "what is open"
  usePublishFocus({
    problem: root === 'proofs' ? shown : null,
    doc_path: root === 'shelf' ? docPath : null,
  })
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-edge px-4 py-2">
        {(
          [
            ['proofs', "the engine's Lean for this task"],
            ['shelf', "the Project's own documents"],
          ] as const
        ).map(([r, hint]) => (
          <button
            key={r}
            title={hint}
            className={`cursor-pointer rounded-md px-2 py-0.5 text-[11px] transition-colors ${
              root === r ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:text-ink-dim'
            }`}
            onClick={() => setRoot(r)}
            aria-pressed={root === r}
          >
            {r === 'proofs' ? 'proofs' : 'documents'}
          </button>
        ))}
        {root === 'proofs' && shown && (
          <>
            {tasks.length > 1 ? (
              <Select
                className="ml-2 w-56"
                value={shown}
                onChange={(e) => {
                  setTask(e.target.value)
                  setSel(null)
                }}
                title="whose proofs the column lists"
              >
                {tasks.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            ) : null}
            <Link
              to={projectPath(project, 'sky', shown)}
              className="ml-2 font-mono text-[11px] text-ink-faint transition-colors hover:text-ink"
              title="open this task's sky"
            >
              {tasks.length > 1 ? 'open its sky' : shown}
            </Link>
          </>
        )}
      </div>
      <div className="flex min-h-0 flex-1">
        {root === 'proofs' ? (
          shown ? (
            <ProofsView key={shown} problem={shown} file={sel} onPick={setSel} />
          ) : (
            <p className="p-6 text-xs text-ink-faint">
              No task on this shelf yet — proofs appear once one runs.
            </p>
          )
        ) : (
          <DocShelf project={project} onOpenChange={setDocPath} />
        )}
      </div>
    </div>
  )
}
