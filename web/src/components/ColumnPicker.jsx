import React, { useEffect, useRef, useState } from 'react'

/**
 * Choose which columns are visible and their order (drag or ↑↓).
 * items: [{key, label, hint?}], value: {order: [key], hidden: [key]}, presets: [{label, apply(items) => value}]
 */
export default function ColumnPicker({ items, value, onChange, presets = [], label = 'Columns' }) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState('')
  const [drag, setDrag] = useState(null)
  const ref = useRef(null)

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const keys = items.map((i) => i.key)
  const order = [...value.order.filter((k) => keys.includes(k)), ...keys.filter((k) => !value.order.includes(k))]
  const hidden = new Set(value.hidden || [])
  const byKey = Object.fromEntries(items.map((i) => [i.key, i]))
  const visibleCount = order.filter((k) => !hidden.has(k)).length

  const set = (o, h) => onChange({ order: o, hidden: [...h] })
  const toggle = (k) => { const h = new Set(hidden); h.has(k) ? h.delete(k) : h.add(k); set(order, h) }
  const move = (k, d) => {
    const i = order.indexOf(k), j = i + d
    if (j < 0 || j >= order.length) return
    const o = [...order]; [o[i], o[j]] = [o[j], o[i]]; set(o, hidden)
  }
  const drop = (target) => {
    if (!drag || drag === target) return
    const o = order.filter((k) => k !== drag)
    o.splice(o.indexOf(target), 0, drag)
    set(o, hidden); setDrag(null)
  }
  const shown = order.filter((k) => !filter || byKey[k].label.toLowerCase().includes(filter.toLowerCase()))

  return (
    <div className="picker" ref={ref}>
      <button className="btn" onClick={() => setOpen((o) => !o)} title="Choose and reorder columns">
        ☰ {label} <span className="muted">{visibleCount}/{items.length}</span>
      </button>
      {open && (
        <div className="picker-pop">
          <div className="picker-head">
            <input placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} autoFocus />
          </div>
          <div className="picker-presets">
            <button className="link" onClick={() => set(order, new Set())}>All</button>
            <button className="link" onClick={() => set(order, new Set(keys))}>None</button>
            <button className="link" onClick={() => set(keys, new Set())}>Reset order</button>
            {presets.map((p) => (
              <button key={p.label} className="link" onClick={() => onChange(p.apply(items, order))}>{p.label}</button>
            ))}
          </div>
          <ul className="picker-list">
            {shown.map((k) => (
              <li key={k} draggable onDragStart={() => setDrag(k)} onDragOver={(e) => e.preventDefault()} onDrop={() => drop(k)}
                  className={drag === k ? 'dragging' : ''}>
                <span className="grip" title="Drag to reorder">⋮⋮</span>
                <label>
                  <input type="checkbox" checked={!hidden.has(k)} onChange={() => toggle(k)} />
                  <span className={byKey[k].strong ? 'hl-text' : ''}>{byKey[k].label}</span>
                  {byKey[k].hint && <span className="muted small"> {byKey[k].hint}</span>}
                </label>
                <span className="arrows">
                  <button onClick={() => move(k, -1)} title="Move up">↑</button>
                  <button onClick={() => move(k, 1)} title="Move down">↓</button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function visibleKeys(items, value) {
  const keys = items.map((i) => i.key)
  const order = [...(value.order || []).filter((k) => keys.includes(k)), ...keys.filter((k) => !(value.order || []).includes(k))]
  const hidden = new Set(value.hidden || [])
  return order.filter((k) => !hidden.has(k))
}
