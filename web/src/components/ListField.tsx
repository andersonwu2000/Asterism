import { useState } from 'react'

/**
 * Chip-list editor for a list-of-strings setting (forbidden lemmas,
 * lemma hints, axiom whitelist). Extracted from ManifestEditor so the
 * New-problem form and the Manifest tab share one control.
 */
export default function ListField({
  label,
  hint,
  values,
  onChange,
}: {
  label: string
  hint: string
  values: string[]
  onChange: (v: string[]) => void
}) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const v = draft.trim()
    if (v !== '' && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        {label}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {values.map((v) => (
          <span
            key={v}
            className="group flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-dim"
          >
            {v}
            <button
              className="text-ink-faint transition-colors hover:text-ink"
              title={`remove ${v}`}
              onClick={() => onChange(values.filter((x) => x !== v))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="w-44 rounded border border-edge bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
          placeholder={hint}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') add()
          }}
          onBlur={add}
        />
      </div>
    </div>
  )
}
