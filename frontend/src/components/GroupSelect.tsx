import type { GroupMeta } from '../lib/api'

export function GroupSelect({ groups, value, onChange, className = '' }: {
  groups: GroupMeta[]
  value: string
  onChange: (g: string) => void
  className?: string
}) {
  return (
    <select
      aria-label="Competition"
      className={`card px-3 py-1.5 text-sm ${className}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {groups.map((g) => (
        <option key={g.id} value={g.id}>{g.name}</option>
      ))}
    </select>
  )
}
