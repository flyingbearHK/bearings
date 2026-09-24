import React, { useEffect, useRef } from 'react'
import { STORAGE, fmt } from '../api.js'
import { Flags } from './Charts.jsx'
import { Hl } from './DataGrid.jsx'

export const TABLE_SORTS = { relevance: 'Best match', name: 'Name', rows: 'Most rows', columns: 'Most columns', schema: 'Schema' }

/** Keep the active list item visible while moving with the keyboard. */
function useScrollActive(dep) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.querySelector('li.active')?.scrollIntoView({ block: 'nearest' }) }, [dep])
  return ref
}

/** Layer 1: tables. Layer 2 (only when columns matched): matched columns grouped by table. */
export function TablePane({ results, selected, onSelect, onProfile, mode, browsing, checked, setChecked, canLookup, onLookup, lookupHint, lkRemote, setLkRemote,
  term, sort, setSort }) {
  const listRef = useScrollActive(selected)
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
        <span className="spacer" />
        {setSort && (
          <select className="pane-sort" value={sort} onChange={(e) => setSort(e.target.value)} title="Sort the list">
            {Object.entries(TABLE_SORTS).map(([k, l]) => <option key={k} value={k}>{k === 'relevance' && browsing ? 'Default' : l}</option>)}
          </select>
        )}
      </div>
      {nChecked > 0 && (
        <div className="lookup-bar">
          <button className="btn primary" disabled={!canLookup} onClick={onLookup} title={canLookup ? '' : lookupHint}>
            Show rows · {nChecked} table{nChecked > 1 ? 's' : ''}
          </button>
          {results.some((r) => keys.includes(`${r.schema}.${r.table}`) && checked.has(`${r.schema}.${r.table}`) && r.storage && r.storage !== 'local') && setLkRemote && (
            <label className="check" title="Run the lookup live on the remote source for remote tables (whole tables, slower). Off: cached tables run locally">
              <input type="checkbox" checked={!!lkRemote} onChange={(e) => setLkRemote(e.target.checked)} /> ⚡ Remote
            </label>
          )}
          <button className="link small" onClick={() => setChecked(new Set())}>clear</button>
          {!canLookup && <div className="muted small">{lookupHint}</div>}
        </div>
      )}
      <ul className="list" ref={listRef}>
        {results.length === 0 && <li className="muted pad">No match</li>}
        {results.map((r) => {
          const k = `${r.schema}.${r.table}`
          const nCols = r.matched_columns?.length || 0
          return (
            <li key={k} className={`${selected === k ? 'active' : ''} ${checked.has(k) ? 'checked' : ''}`} onClick={() => onSelect(r)}>
              <div className="li-main">
                <input type="checkbox" checked={checked.has(k)} onClick={(e) => e.stopPropagation()} onChange={() => toggle(k)} title="Select for multi-table lookup" />
                <span className="li-name"><span className={`mono ${r.table_score && !(term && r.table.toLowerCase().includes(term.toLowerCase())) ? 'hl-text' : ''}`}><Hl text={r.table} term={term} /></span></span>
                <span className="li-actions">
                  <button className="icon-btn small" title="Table profile" onClick={(e) => { e.stopPropagation(); onProfile(r) }}>▤</button>
                </span>
              </div>
              <div className="li-sub">
                <span className="muted">{r.schema}</span>
                {r.row_count != null && <span className="muted">{fmt.n(r.row_count)} rows</span>}
                {STORAGE[r.storage] && <span className={`chip ${STORAGE[r.storage].chip}`} title={`${r.remote?.full_name || ''} – ${STORAGE[r.storage].title}`}>{STORAGE[r.storage].label}</span>}
                {r.remote?.cache?.outdated && <span className="chip warn" title="The source data changed since it was cached – bearings refresh">⚠ outdated</span>}
                {r.remote?.cache?.masked?.length > 0 && <span className="chip" title={`PII masked: ${r.remote.cache.masked.join(', ')}`}>🔒</span>}
                {r.partial && <span className="chip warn" title={`Found in the cached sample; the whole table is on ${r.remote?.platform || 'the remote source'}`}>in sample</span>}
                {!r.profiled && r.kind !== 'remote' && <span className="chip warn" title="Run bearings profile">no profile</span>}
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

export function ColumnPane({ results, selectedTable, selectedColumn, onSelect, onProfile, mode, term }) {
  const listRef = useScrollActive(`${selectedTable}.${selectedColumn}`)
  const groups = results.filter((r) => r.matched_columns?.length)
  const total = groups.reduce((a, r) => a + r.matched_columns.length, 0)
  return (
    <section className="pane cols-pane">
      <div className="pane-head">Matched columns <span className="muted">{total}</span></div>
      <div className="list-scroll" ref={listRef}>
        {groups.map((r) => {
          const k = `${r.schema}.${r.table}`
          return (
            <div key={k} className={`group ${selectedTable === k ? 'active' : ''}`}>
              <div className="group-head mono">{r.table}</div>
              <ul className="list">
                {r.matched_columns.map((c) => (
                  <li key={c.column} className={selectedTable === k && selectedColumn === c.column ? 'active' : ''} onClick={() => onSelect(r, c)}>
                    <div className="li-main">
                      <span className="li-name"><span className={`mono ${term && c.column.toLowerCase().includes(term.toLowerCase()) ? '' : 'hl-text'}`}><Hl text={c.column} term={term} /></span></span>
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
                    {c.comment && mode !== 'value' && <div className="li-ex"><Hl text={c.comment} term={term} /></div>}
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
