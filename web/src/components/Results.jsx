import React from 'react'
import { fmt } from '../api.js'
import { Flags } from './Charts.jsx'

/** Layer 1: tables. Layer 2 (only when columns matched): matched columns grouped by table. */
export function TablePane({ results, selected, onSelect, onProfile, mode, browsing, checked, setChecked, canLookup, onLookup, lookupHint }) {
  const keys = results.map((r) => `${r.schema}.${r.table}`)
  const nChecked = keys.filter((k) => checked.has(k)).length
  const all = nChecked > 0 && nChecked === keys.length
  const toggle = (k) => { const s = new Set(checked); s.has(k) ? s.delete(k) : s.add(k); setChecked(s) }
  return (
    <section className="pane tables-pane">
      <div className="pane-head">
        <input type="checkbox" checked={all} ref={(el) => el && (el.indeterminate = nChecked > 0 && !all)}
          onChange={() => setChecked(all ? new Set() : new Set(keys))} title="Select all / none" />
        {browsing ? 'All tables' : 'Tables'} <span className="muted">{results.length}</span>
      </div>
      {nChecked > 0 && (
        <div className="lookup-bar">
          <button className="btn primary" disabled={!canLookup} onClick={onLookup} title={canLookup ? '' : lookupHint}>
            Show rows · {nChecked} table{nChecked > 1 ? 's' : ''}
          </button>
          <button className="link small" onClick={() => setChecked(new Set())}>clear</button>
          {!canLookup && <div className="muted small">{lookupHint}</div>}
        </div>
      )}
      <ul className="list">
        {results.length === 0 && <li className="muted pad">No match</li>}
        {results.map((r) => {
          const k = `${r.schema}.${r.table}`
          const nCols = r.matched_columns?.length || 0
          return (
            <li key={k} className={`${selected === k ? 'active' : ''} ${checked.has(k) ? 'checked' : ''}`} onClick={() => onSelect(r)}>
              <div className="li-main">
                <input type="checkbox" checked={checked.has(k)} onClick={(e) => e.stopPropagation()} onChange={() => toggle(k)} title="Select for multi-table lookup" />
                <span className="li-name"><span className={`mono ${r.table_score ? 'hl-text' : ''}`}>{r.table}</span></span>
                <span className="li-actions">
                  <button className="icon-btn small" title="Table profile" onClick={(e) => { e.stopPropagation(); onProfile(r) }}>▤</button>
                </span>
              </div>
              <div className="li-sub">
                <span className="muted">{r.schema}</span>
                <span className="muted">{fmt.n(r.row_count)} rows</span>
                {!r.profiled && <span className="chip warn" title="Run bearings profile">no profile</span>}
                {r.table_matched_by && r.table_matched_by !== 'table' && <span className="chip info">{r.table_matched_by}</span>}
                {nCols > 0 && <span className="chip accent">{nCols} {mode === 'value' ? 'col' : 'col'}{nCols > 1 ? 's' : ''}{mode === 'value' ? ` · ${fmt.n(r.hits)} hits` : ''}</span>}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function ColumnPane({ results, selectedTable, selectedColumn, onSelect, onProfile, mode }) {
  const groups = results.filter((r) => r.matched_columns?.length)
  const total = groups.reduce((a, r) => a + r.matched_columns.length, 0)
  return (
    <section className="pane cols-pane">
      <div className="pane-head">Matched columns <span className="muted">{total}</span></div>
      <div className="list-scroll">
        {groups.map((r) => {
          const k = `${r.schema}.${r.table}`
          return (
            <div key={k} className={`group ${selectedTable === k ? 'active' : ''}`}>
              <div className="group-head mono">{r.table}</div>
              <ul className="list">
                {r.matched_columns.map((c) => (
                  <li key={c.column} className={selectedTable === k && selectedColumn === c.column ? 'active' : ''} onClick={() => onSelect(r, c)}>
                    <div className="li-main">
                      <span className="li-name"><span className="mono hl-text">{c.column}</span></span>
                      <span className="li-actions">
                        <button className="icon-btn small" title="Column profile" onClick={(e) => { e.stopPropagation(); onProfile(r, c) }}>▤</button>
                      </span>
                    </div>
                    <div className="li-sub">
                      <span className="mono muted">{c.type?.toLowerCase()}</span>
                      {c.null_pct != null && <span className="muted" title="Null %">∅ {fmt.pct(c.null_pct)}</span>}
                      {c.distinct_count != null && <span className="muted" title="Distinct values">◇ {fmt.n(c.distinct_count)}</span>}
                      {c.matched_by !== 'column' && c.matched_by !== 'value' && <span className="chip info">{c.matched_by}</span>}
                      {mode === 'value' && <span className="chip accent">{fmt.n(c.hits)} hits</span>}
                      <Flags flags={(c.flags || []).filter((f) => f === 'candidate_pk' || f.startsWith('pii_'))} />
                    </div>
                    {mode === 'value' && c.examples?.length > 0 && <div className="li-ex mono">{c.examples.join(' · ')}</div>}
                    {c.comment && mode !== 'value' && <div className="li-ex">{c.comment}</div>}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </section>
  )
}
