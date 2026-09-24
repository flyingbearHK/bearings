import React, { createContext, useContext, useMemo, useState } from 'react'
import { copy, splitHits, store } from '../api.js'

/** Text to highlight inside cells (the grid's quick filter, or a search term passed in). */
const HighlightCtx = createContext('')

/** Highlight occurrences of the current term in a piece of text. */
export function Hl({ text, term }) {
  const ctx = useContext(HighlightCtx)
  const parts = splitHits(text, term ?? ctx)
  return <>{parts.map((p, i) => (p.hit ? <mark key={i}>{p.t}</mark> : <React.Fragment key={i}>{p.t}</React.Fragment>))}</>
}

const plain = (v) => (v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v))

/** Generic grid. columns: [{key, label, render?(row), value?(row), align?, width?, title?}]
 *  id: remembers the sort order under this name · filterable: quick-filter box · highlight: term marked in cells
 *  hideEmptyToggle: offer "hide empty columns" (columns whose values are all null / blank in these rows) */
export default function DataGrid({ columns, rows, rowKey, rowClass, onRowClick, empty = 'No rows', maxHeight, dense,
  id, filterable, highlight, hideEmptyToggle, defaultSort = null, toolbarExtra }) {
  const [sort, setSortState] = useState(() => (id ? store.get(`sort:${id}`, defaultSort) : defaultSort)) // {key, dir}
  const setSort = (f) => setSortState((s) => { const n = typeof f === 'function' ? f(s) : f; if (id) store.set(`sort:${id}`, n); return n })
  const [filter, setFilter] = useState('')
  const [hideEmpty, setHideEmpty] = useState(() => (hideEmptyToggle ? store.get(`hideEmpty:${id || 'grid'}`, false) : false))

  const getter = (c) => c.value || ((r) => r[c.key])
  const filtered = useMemo(() => {
    const f = filter.trim().toLowerCase()
    if (!f) return rows
    const gets = columns.map(getter)
    return rows.filter((r) => gets.some((g) => plain(g(r)).toLowerCase().includes(f)))
  }, [rows, filter, columns]) // eslint-disable-line
  const sorted = useMemo(() => {
    if (!sort) return filtered
    const col = columns.find((c) => c.key === sort.key)
    if (!col) return filtered
    const get = getter(col)
    return [...filtered].sort((a, b) => {
      const x = get(a), y = get(b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      const r = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })
      return sort.dir === 'asc' ? r : -r
    })
  }, [filtered, sort, columns]) // eslint-disable-line
  const emptyCols = useMemo(() => {
    if (!hideEmptyToggle || !rows.length) return new Set()
    return new Set(columns.filter((c) => c.hideable !== false && rows.every((r) => { const v = getter(c)(r); return v == null || v === '' })).map((c) => c.key))
  }, [rows, columns, hideEmptyToggle]) // eslint-disable-line
  const shownCols = hideEmpty ? columns.filter((c) => !emptyCols.has(c.key)) : columns

  const toggle = (k) => setSort((s) => (!s || s.key !== k ? { key: k, dir: 'asc' } : s.dir === 'asc' ? { key: k, dir: 'desc' } : null))
  const term = filter.trim() || highlight || ''

  return (
    <HighlightCtx.Provider value={term}>
      {(filterable || hideEmptyToggle || toolbarExtra) && (
        <div className="grid-bar">
          {filterable && (
            <input className="grid-filter" placeholder={typeof filterable === 'string' ? filterable : 'Filter rows…'} value={filter}
              onChange={(e) => setFilter(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') setFilter('') }} />
          )}
          {filter && <span className="muted small">{sorted.length} of {rows.length}</span>}
          {hideEmptyToggle && emptyCols.size > 0 && (
            <label className="check small" title="Columns whose values are all null or blank in these rows">
              <input type="checkbox" checked={hideEmpty} onChange={(e) => { setHideEmpty(e.target.checked); store.set(`hideEmpty:${id || 'grid'}`, e.target.checked) }} />
              hide {emptyCols.size} empty column{emptyCols.size > 1 ? 's' : ''}</label>
          )}
          {toolbarExtra}
          {sort && <button className="link small" onClick={() => setSort(null)} title="Back to the original order">clear sort</button>}
        </div>
      )}
      <div className={`grid-wrap ${dense ? 'dense' : ''}`} style={maxHeight ? { maxHeight } : undefined}>
        <table className="grid">
          <thead>
            <tr>
              {shownCols.map((c) => (
                <th key={c.key} onClick={() => toggle(c.key)} style={{ width: c.width, textAlign: c.align }} title={c.title || 'Click to sort'}>
                  {c.label}
                  <span className="sort">{sort?.key === c.key ? (sort.dir === 'asc' ? '▲' : '▼') : ''}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr><td colSpan={shownCols.length} className="empty">{filter ? 'No rows match the filter' : empty}</td></tr>
            )}
            {sorted.map((r, i) => (
              <tr key={rowKey ? rowKey(r) : i} className={rowClass ? rowClass(r) : ''} onClick={onRowClick ? () => onRowClick(r) : undefined}>
                {shownCols.map((c) => {
                  const v = c.render ? c.render(r) : r[c.key]
                  return (
                    <td key={c.key} style={{ textAlign: c.align }}
                      onDoubleClick={(e) => { const raw = getter(c)(r); if (raw != null && typeof raw !== 'object') { e.stopPropagation(); copy(raw) } }}>
                      {v === null || v === undefined ? (c.render ? v : <span className="null">null</span>) : typeof v === 'string' ? <Hl text={v} /> : v}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </HighlightCtx.Provider>
  )
}

export function Cell({ v, masked }) {
  if (v === null || v === undefined) return <span className="null">null</span>
  if (masked) return <span className="masked">••••••</span>
  const s = typeof v === 'object' ? JSON.stringify(v) : String(v)
  if (s === '') return <span className="null">''</span>
  return <span className="cell" title={s.length > 40 ? s : 'Double-click to copy'}><Hl text={s} /></span>
}
