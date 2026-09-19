import React, { useState } from 'react'
import { STORAGE, fmt } from '../api.js'
import DataGrid, { Cell } from './DataGrid.jsx'

const OP_LABEL = { '=': '=', '!=': '≠', '>': '>', '<': '<', '>=': '≥', '<=': '≤', '~': 'contains' }

function toCsv(res) {
  const esc = (v) => (v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v))
  return [res.columns.map(esc).join(','), ...res.rows.map((r) => r.map(esc).join(','))].join('\n')
}

/** Right-hand panel: rows from every selected table where <matched column> <op> <value>. */
export default function LookupResults({ data, loading, error, filter, onClose, onOpenTable, onOpenSql, workshop, limit, setLimit, onRerun }) {
  const [collapsed, setCollapsed] = useState({})
  const [matchedFirst, setMatchedFirst] = useState(true)
  const [unmask, setUnmask] = useState(false)
  const results = data?.results || []
  const total = results.reduce((a, r) => a + (r.count || 0), 0)
  const hits = results.filter((r) => r.count > 0).length

  return (
    <div className="detail">
      <div className="detail-head">
        <div className="title-row">
          <h2 className="lookup-title">
            {filter.column ? <span className="mono">{filter.column}</span> : <span className="muted">matched columns</span>}
            {' '}<span className="op">{OP_LABEL[filter.op]}</span>{' '}
            <span className="mono">{filter.value}</span>
          </h2>
          {data && <span className="muted">{fmt.n(total)} rows in {hits} of {results.length} tables</span>}
          <span className="spacer" />
          <button className="icon-btn" onClick={onClose} title="Back to table detail">✕</button>
        </div>
        <div className="toolbar">
          <label className="check"><input type="checkbox" checked={matchedFirst} onChange={(e) => setMatchedFirst(e.target.checked)} /> matched column first</label>
          <label className="check">max rows / table
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>{[20, 100, 500, 2000].map((n) => <option key={n}>{n}</option>)}</select>
          </label>
          {workshop && <label className="check"><input type="checkbox" checked={unmask} onChange={(e) => setUnmask(e.target.checked)} /> show PII</label>}
          <span className="spacer" />
          <button className="link" onClick={() => setCollapsed(Object.fromEntries(results.map((r) => [`${r.schema}.${r.table}`, true])))}>collapse all</button>
          <button className="link" onClick={() => setCollapsed({})}>expand all</button>
          <button className="btn" onClick={onRerun}>↻ Re-run</button>
        </div>
      </div>
      {loading && <div className="muted pad">Querying {results.length || ''} tables…</div>}
      {error && <div className="error">{error}</div>}
      {results.map((r) => {
        const k = `${r.schema}.${r.table}`
        const isCollapsed = collapsed[k] ?? r.count === 0
        const order = matchedFirst ? [...r.match_columns, ...r.columns.filter((c) => !r.match_columns.includes(c))] : r.columns
        const idx = Object.fromEntries(r.columns.map((c, i) => [c, i]))
        const pii = new Set(r.pii_columns)
        const cols = order.map((c) => ({
          key: c,
          label: <span className={r.match_columns.includes(c) ? 'hl-text' : ''} title={r.types[idx[c]]}>{c}{r.candidate_keys.includes(c) ? ' 🔑' : ''}</span>,
          render: (row) => <Cell v={row[idx[c]]} masked={workshop && !unmask && pii.has(c)} />, value: (row) => row[idx[c]],
        }))
        return (
          <section key={k} className={`lk-section ${r.count ? '' : 'empty'}`}>
            <div className="lk-head" onClick={() => setCollapsed({ ...collapsed, [k]: !isCollapsed })}>
              <span className="caret">{isCollapsed ? '▸' : '▾'}</span>
              <span className="mono"><span className="muted">{r.schema}.</span><b>{r.table}</b></span>
              <span className={`chip ${r.count ? 'accent' : ''}`}>{fmt.n(r.count)} row{r.count === 1 ? '' : 's'}</span>
              {r.count > r.rows.length && <span className="muted small">showing {fmt.n(r.rows.length)}</span>}
              <span className="muted small">on {r.match_columns.join(', ') || '—'}</span>
              {r.source === 'remote' && <span className="chip cloud" title="Ran on the Databricks SQL warehouse">⚡ Databricks</span>}
              {r.source === 'sample' && <span className="chip warn" title={`Searched the cached sample (${fmt.n(r.cached_rows)} of ${fmt.n(r.total_rows)} rows); tick ⚡ Remote for the whole table`}>{STORAGE.sample.label}</span>}
              {r.source === 'cached' && <span className="chip good" title={STORAGE.cached.title}>{STORAGE.cached.label}</span>}
              {r.error && <span className="chip bad" title={r.error}>{r.error.slice(0, 60)}</span>}
              <span className="spacer" />
              <span className="lk-actions" onClick={(e) => e.stopPropagation()}>
                <button className="btn small" onClick={() => onOpenTable(r.schema, r.table, r.match_columns[0])}>Open table</button>
                {r.sql && <button className="btn small" onClick={() => onOpenSql(r.sql)}>SQL</button>}
                {r.rows.length > 0 && <button className="btn small" onClick={() => {
                  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([toCsv(r)], { type: 'text/csv' }))
                  a.download = `${r.schema}.${r.table}_${filter.value}.csv`.replace(/[^\w.@-]+/g, '_'); a.click()
                }}>CSV</button>}
              </span>
            </div>
            {!isCollapsed && r.rows.length > 0 && <DataGrid columns={cols} rows={r.rows} dense maxHeight={420} />}
          </section>
        )
      })}
    </div>
  )
}
