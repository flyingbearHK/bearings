import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, fmt, recent } from '../api.js'
import { Hl } from './DataGrid.jsx'

/** Subsequence score: higher is better, -1 = no match. Contiguous and word-start matches score more. */
export function fuzzyScore(text, q) {
  const s = text.toLowerCase(), t = q.toLowerCase().replace(/\s+/g, '')
  if (!t) return 0
  const idx = s.indexOf(t)
  if (idx !== -1) return 1000 - idx * 2 - (s.length - t.length) + (idx === 0 || /[._ ]/.test(s[idx - 1]) ? 200 : 0)
  let i = 0, score = 0, run = 0
  for (const ch of s) {
    if (i < t.length && ch === t[i]) { i++; run++; score += 5 + run * 3 } else run = 0
  }
  return i === t.length ? score - s.length : -1
}

/** Ctrl/⌘+K: jump to any table or column, or run a command. ↑↓ to move, Enter to open, Esc to close. */
export default function QuickOpen({ tables, scope, commands, onOpenTable, onClose }) {
  const [q, setQ] = useState('')
  const [cols, setCols] = useState([])
  const [i, setI] = useState(0)
  const listRef = useRef(null)
  const seq = useRef(0)

  useEffect(() => {
    const id = ++seq.current
    if (q.trim().length < 2) { setCols([]); return }
    const h = setTimeout(() => api.search(q.trim(), 'name', { match: 'fuzzy', columns_only: true, schemas: scope })
      .then((r) => {
        if (id !== seq.current) return
        setCols(r.tables.flatMap((t) => t.matched_columns.map((c) => ({ ...c, schema: t.schema, table: t.table }))).slice(0, 25))
      }).catch(() => {}), 140)
    return () => clearTimeout(h)
  }, [q, scope])

  const items = useMemo(() => {
    const out = []
    const query = q.trim()
    const cmds = commands.filter((c) => !query || fuzzyScore(c.label, query) >= 0)
    if (!query) {
      const byKey = Object.fromEntries(tables.map((t) => [`${t.schema}.${t.table}`, t]))
      recent.get().filter((k) => byKey[k]).slice(0, 8).forEach((k) => out.push({ kind: 'recent', t: byKey[k] }))
    } else {
      tables.map((t) => ({ t, s: fuzzyScore(`${t.schema}.${t.table}`, query) }))
        .filter((x) => x.s >= 0).sort((a, b) => b.s - a.s).slice(0, 12).forEach((x) => out.push({ kind: 'table', t: x.t }))
      cols.forEach((c) => out.push({ kind: 'column', c }))
    }
    cmds.slice(0, query ? 4 : 8).forEach((c) => out.push({ kind: 'cmd', c }))
    return out
  }, [q, tables, cols, commands])

  useEffect(() => { setI(0) }, [q])
  useEffect(() => { listRef.current?.querySelector('.active')?.scrollIntoView({ block: 'nearest' }) }, [i])

  const go = (it) => {
    if (!it) return
    if (it.kind === 'cmd') { onClose(); it.c.run() } else if (it.kind === 'column') { onClose(); onOpenTable(it.c.schema, it.c.table, it.c.column) } else { onClose(); onOpenTable(it.t.schema, it.t.table) }
  }
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setI((x) => Math.min(items.length - 1, x + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setI((x) => Math.max(0, x - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); go(items[i]) }
    else if (e.key === 'Escape') { e.preventDefault(); onClose() }
  }
  const head = (k, idx) => {
    const prev = items[idx - 1]?.kind
    const label = { recent: 'Recent', table: 'Tables', column: 'Columns', cmd: 'Actions' }[k]
    return prev === k ? null : <li className="qo-group" key={`h-${k}`}>{label}</li>
  }
  const query = q.trim()
  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal quick-open" role="dialog" aria-label="Quick open">
        <input autoFocus className="qo-input" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
          placeholder="Jump to a table or column…   (type part of a name; ↑↓ Enter)" />
        <ul className="qo-list" ref={listRef}>
          {items.length === 0 && <li className="muted pad-x">{query ? 'No match' : 'Type to search tables and columns'}</li>}
          {items.map((it, idx) => (
            <React.Fragment key={`${it.kind}-${idx}`}>
              {head(it.kind, idx)}
              <li className={idx === i ? 'active' : ''} onMouseEnter={() => setI(idx)} onClick={() => go(it)}>
                {it.kind === 'cmd' ? (
                  <><span className="qo-icon">›</span><span>{it.c.label}</span><span className="spacer" />{it.c.keys && <kbd>{it.c.keys}</kbd>}</>
                ) : it.kind === 'column' ? (
                  <><span className="qo-icon">◦</span><span className="mono"><span className="muted">{it.c.schema}.{it.c.table}.</span><b><Hl text={it.c.column} term={query} /></b></span>
                    <span className="muted small mono">{it.c.type?.toLowerCase()}</span><span className="spacer" />
                    {it.c.comment && <span className="muted small qo-comment">{it.c.comment}</span>}</>
                ) : (
                  <><span className="qo-icon">▦</span><span className="mono"><span className="muted">{it.t.schema}.</span><b><Hl text={it.t.table} term={query} /></b></span>
                    <span className="spacer" /><span className="muted small">{it.t.row_count != null ? `${fmt.n(it.t.row_count)} rows · ` : ''}{it.t.column_count} cols</span>
                    {it.t.kind === 'remote' && <span className="chip cloud">☁</span>}</>
                )}
              </li>
            </React.Fragment>
          ))}
        </ul>
        <div className="qo-foot muted small"><kbd>↑</kbd><kbd>↓</kbd> move · <kbd>Enter</kbd> open · <kbd>Esc</kbd> close · <kbd>?</kbd> all shortcuts</div>
      </div>
    </div>
  )
}

export const SHORTCUTS = [
  ['⌘/Ctrl K', 'Jump to a table or column, or run an action'],
  ['/', 'Focus the search box'],
  ['↓ / ↑', 'Next / previous table in the list (from the search box too)'],
  ['⇧↓ / ⇧↑', 'Next / previous matched column'],
  ['x', 'Tick / untick the current table (for Show rows)'],
  ['1 2 3 4', 'Schema · Sample data · Profile · Relationships'],
  ['s', 'Sample 20 rows of the current table'],
  ['a', 'Add data (or drop files anywhere)'],
  ['Esc', 'Clear the search / close a dialog'],
  ['Double-click a cell', 'Copy its value'],
  ['?', 'This help'],
]

export function ShortcutHelp({ onClose }) {
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape' || e.key === '?') { e.preventDefault(); onClose() } }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, []) // eslint-disable-line
  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal shortcuts" role="dialog" aria-label="Keyboard shortcuts">
        <div className="modal-head"><h3>Keyboard shortcuts</h3><span className="spacer" /><button className="icon-btn" onClick={onClose}>✕</button></div>
        <table className="grid">
          <tbody>{SHORTCUTS.map(([k, d]) => <tr key={k}><td style={{ width: 170 }}><kbd>{k}</kbd></td><td>{d}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}
