import React, { useMemo, useState } from 'react'

/** Generic grid. columns: [{key, label, render?(row), value?(row), align?, width?, title?}] */
export default function DataGrid({ columns, rows, rowKey, rowClass, onRowClick, empty = 'No rows', maxHeight, dense }) {
  const [sort, setSort] = useState(null) // {key, dir}
  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col) return rows
    const get = col.value || ((r) => r[col.key])
    return [...rows].sort((a, b) => {
      const x = get(a), y = get(b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      const r = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })
      return sort.dir === 'asc' ? r : -r
    })
  }, [rows, sort, columns])

  const toggle = (k) => setSort((s) => (!s || s.key !== k ? { key: k, dir: 'asc' } : s.dir === 'asc' ? { key: k, dir: 'desc' } : null))

  return (
    <div className={`grid-wrap ${dense ? 'dense' : ''}`} style={maxHeight ? { maxHeight } : undefined}>
      <table className="grid">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} onClick={() => toggle(c.key)} style={{ width: c.width, textAlign: c.align }} title={c.title || 'Click to sort'}>
                {c.label}
                <span className="sort">{sort?.key === c.key ? (sort.dir === 'asc' ? '▲' : '▼') : ''}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr><td colSpan={columns.length} className="empty">{empty}</td></tr>
          )}
          {sorted.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i} className={rowClass ? rowClass(r) : ''} onClick={onRowClick ? () => onRowClick(r) : undefined}>
              {columns.map((c) => {
                const v = c.render ? c.render(r) : r[c.key]
                return (
                  <td key={c.key} style={{ textAlign: c.align }}>
                    {v === null || v === undefined ? (c.render ? v : <span className="null">null</span>) : v}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Cell({ v, masked }) {
  if (v === null || v === undefined) return <span className="null">null</span>
  if (masked) return <span className="masked">••••••</span>
  const s = typeof v === 'object' ? JSON.stringify(v) : String(v)
  if (s === '') return <span className="null">''</span>
  return <span className="cell" title={s.length > 40 ? s : undefined}>{s}</span>
}
