import { useId } from 'react'
import type { TeamListItem } from '../lib/api'

/** Native datalist combobox: accessible, keyboardable, zero dependencies. */
export function TeamSelect({ teams, value, onChange, placeholder }: {
  teams: TeamListItem[]
  value: string
  onChange: (t: string) => void
  placeholder: string
}) {
  const listId = useId()
  return (
    <>
      <input
        className="card w-full px-3 py-1.5 text-sm"
        list={listId}
        value={value}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      <datalist id={listId}>
        {teams.map((t) => <option key={t.team} value={t.team} />)}
      </datalist>
    </>
  )
}
