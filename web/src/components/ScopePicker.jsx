import React, { useEffect, useRef, useState } from 'react'
import { fmt } from '../api.js'

/** Header control: restrict the whole app (search, lists, lookups, relationships, annotations, exports) to schemas. */
export default function ScopePicker({ schemas, scope, setScope }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  if (!schemas?.length) return null
  const sel = new Set(scope)
  const toggle = (s) => { const n = new Set(sel); n.has(s) ? n.delete(s) : n.add(s); setScope([...n].sort()) }
  const label = scope.length === 0 ? 'All schemas' : scope.join(', ')
  return (
    <div className="picker scope" ref={ref}>
      <button className={`btn scope-btn ${scope.length ? 'scoped' : ''}`} onClick={() => setOpen((o) => !o)}
        title="Limit search, lists, lookups, relationships, annotations and exports to these schemas">
        <span className="muted small">Schema</span> <b>{label}</b> ▾
      </button>
      {open && (
        <div className="picker-pop scope-pop">
          <ul className="picker-list">
            <li className={scope.length === 0 ? 'active' : ''}>
              <label><input type="radio" checked={scope.length === 0} onChange={() => { setScope([]); setOpen(false) }} /> All schemas</label>
            </li>
            {schemas.map((s) => (
              <li key={s.schema}>
                <label>
                  <input type="checkbox" checked={sel.has(s.schema)} onChange={() => toggle(s.schema)} />
                  <span className="mono">{s.schema}</span>
                  <span className="muted small">{s.tables} tables · {fmt.n(s.rows)} rows</span>
                </label>
                <button className="link small" onClick={() => { setScope([s.schema]); setOpen(false) }}>only</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
