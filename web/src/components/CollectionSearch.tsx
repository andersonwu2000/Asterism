import { useId } from 'react'

/** A labelled, keyboard-clearable search shared by the two shelves. */
export default function CollectionSearch({ value, onChange, label, placeholder }: {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder: string
}) {
  const id = useId()
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-lg border border-edge bg-surface px-3 focus-within:border-ink-faint">
      <svg aria-hidden="true" className="h-4 w-4 shrink-0 text-ink-faint" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.3">
        <circle cx="8.5" cy="8.5" r="5.5" /><path d="m13 13 4 4" />
      </svg>
      <label htmlFor={id} className="sr-only">{label}</label>
      <input id={id} type="search" value={value} placeholder={placeholder}
        className="min-w-0 flex-1 bg-transparent py-2.5 text-xs text-ink outline-none placeholder:text-ink-faint"
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); onChange('') } }} />
    </div>
  )
}
