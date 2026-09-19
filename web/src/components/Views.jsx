import React, { useEffect, useMemo, useState } from 'react'
import { api, exportUrl, fmt, store } from '../api.js'
import { Bar, Tags } from './Charts.jsx'
import DataGrid, { Cell } from './DataGrid.jsx'

export function RelationshipsView({ onOpenTable, scope }) {
  const [rows, setRows] = useState(null)
  const [f, setF] = useState('')
  const [min, setMin] = useState(0)
  useEffect(() => { api.relationships({ schemas: scope }).then(setRows) }, [scope])
  const shown = useMemo(() => (rows || []).filter((r) =>
    r.confidence >= min && (!f || `${r.from_table}.${r.from_column} ${r.to_table}.${r.to_column}`.toLowerCase().includes(f.toLowerCase()))), [rows, f, min])
  if (!rows) return <div className="muted pad">Loading…</div>
  return (
    <div className="page">
      <div className="subbar">
        <input className="grow" placeholder="Filter by table or column…" value={f} onChange={(e) => setF(e.target.value)} />
        <label className="check">min confidence
          <select value={min} onChange={(e) => setMin(Number(e.target.value))}>{[0, 0.6, 0.8, 0.9].map((x) => <option key={x} value={x}>{x}</option>)}</select></label>
        <span className="muted small">{shown.length} of {rows.length} · discovered by <code>bearings relate</code> (name similarity + value overlap)</span>
      </div>
      <DataGrid rows={shown} empty="No relationships. Run: bearings profile && bearings relate" columns={[
        { key: 'from', label: 'From (FK)', render: (r) => <button className="link mono" onClick={() => onOpenTable(r.from_schema, r.from_table, r.from_column)}>{r.from_table}.{r.from_column}</button>, value: (r) => r.from_table + '.' + r.from_column },
        { key: 'arrow', label: '', render: () => '→', width: 24 },
        { key: 'to', label: 'To (key)', render: (r) => <button className="link mono" onClick={() => onOpenTable(r.to_schema, r.to_table, r.to_column)}>{r.to_table}.{r.to_column}</button>, value: (r) => r.to_table + '.' + r.to_column },
        { key: 'overlap_pct', label: 'Overlap', render: (r) => <span className="numbar"><Bar pct={r.overlap_pct} tone="good" width={70} />{fmt.pct(r.overlap_pct)}</span>, align: 'right' },
        { key: 'from_distinct', label: 'FK distinct', render: (r) => fmt.n(r.from_distinct), align: 'right' },
        { key: 'name_score', label: 'Name sim.', render: (r) => r.name_score.toFixed(2), align: 'right' },
        { key: 'confidence', label: 'Confidence', render: (r) => <b>{r.confidence.toFixed(2)}</b>, align: 'right' },
        { key: 'method', label: 'Method', render: (r) => <span className="muted small">{r.method}</span> },
      ]} />
    </div>
  )
}

export function AnnotationsView({ onOpenTable, refreshKey, scope }) {
  const [rows, setRows] = useState(null)
  const [f, setF] = useState('')
  useEffect(() => { api.annotations(scope).then(setRows) }, [refreshKey, scope])
  if (!rows) return <div className="muted pad">Loading…</div>
  const shown = rows.filter((r) => !f || Object.values(r).join(' ').toLowerCase().includes(f.toLowerCase()))
  return (
    <div className="page">
      <div className="subbar">
        <input className="grow" placeholder="Filter annotations…" value={f} onChange={(e) => setF(e.target.value)} />
        <a className="btn" href={exportUrl('xlsx', scope)}>Export mapping workbook (.xlsx)</a>
        <a className="btn" href={exportUrl('json', scope)}>Export JSON</a>
      </div>
      <DataGrid rows={shown} empty="No annotations yet — open a column's profile (▤) to tag it or map it to a CDM entity" columns={[
        { key: 'table_name', label: 'Table', render: (r) => <button className="link mono" onClick={() => onOpenTable(r.schema_name, r.table_name, r.column_name || null)}>{r.schema_name}.{r.table_name}</button>, value: (r) => r.table_name },
        { key: 'column_name', label: 'Column', render: (r) => <span className="mono">{r.column_name || <span className="muted">(table)</span>}</span> },
        { key: 'tags', label: 'Tags', render: (r) => <Tags tags={r.tags} /> },
        { key: 'cdm_entity', label: 'CDM entity' }, { key: 'cdm_attribute', label: 'CDM attribute' },
        { key: 'notes', label: 'Notes', render: (r) => <span className="comment">{r.notes}</span> },
        { key: 'updated_at', label: 'Updated', render: (r) => <span className="muted small">{r.updated_at?.replace('T', ' ')}</span> },
      ]} />
    </div>
  )
}

export function SqlView({ sql, setSql, tables }) {
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [hist, setHist] = useState(() => store.get('sqlHistory', []))
  const [conns, setConns] = useState([])
  const [engine, setEngine] = useState(() => store.get('sqlEngine', 'duckdb'))
  useEffect(() => { api.remote().then((r) => setConns(r.connections || [])).catch(() => {}) }, [])
  useEffect(() => store.set('sqlEngine', engine), [engine])
  const remoteEngine = engine.startsWith('databricks:')
  const shown = tables.filter((t) => (remoteEngine ? t.kind === 'remote' || t.remote : t.kind !== 'remote'))
  const run = async () => {
    setBusy(true); setErr(null)
    try {
      const r = await api.sql(sql, 1000, engine); setRes(r)
      const h = [sql, ...hist.filter((x) => x !== sql)].slice(0, 20); setHist(h); store.set('sqlHistory', h)
    } catch (e) { setErr(e.message); setRes(null) } finally { setBusy(false) }
  }
  const cols = (res?.columns || []).map((c, i) => ({ key: String(i), label: <span title={res.types[i]}>{c}</span>, render: (r) => <Cell v={r[i]} />, value: (r) => r[i] }))
  return (
    <div className="page sql-page">
      <aside className="sql-side">
        <div className="pane-head">Tables</div>
        <ul className="list compact">
          {shown.map((t) => <li key={`${t.schema}.${t.table}`} className="mono" title="Insert name" onClick={() => setSql(sql + (sql.endsWith(' ') || !sql ? '' : ' ') + `${t.schema}.${t.table}`)}>{t.schema}.{t.table}</li>)}
        </ul>
        {hist.length > 0 && <><div className="pane-head">History</div>
          <ul className="list compact">{hist.map((h, i) => <li key={i} className="mono small" title={h} onClick={() => setSql(h)}>{h.replace(/\s+/g, ' ').slice(0, 60)}</li>)}</ul></>}
      </aside>
      <div className="sql-main">
        <textarea className="sql-editor mono" value={sql} onChange={(e) => setSql(e.target.value)} spellCheck={false}
          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); run() } }}
          placeholder="SELECT * FROM pms.reservation LIMIT 100   — Ctrl/⌘+Enter to run. Read-only. Try SUMMARIZE pms.guest" />
        <div className="subbar">
          {conns.length > 0 && (
            <select className="engine" value={engine} onChange={(e) => setEngine(e.target.value)}
              title="Where the query runs. On Databricks, attached aliases (e.g. dev_raw_pms.reservation) are expanded to catalog.schema.table">
              <option value="duckdb">Local (DuckDB)</option>
              {conns.map((c) => <option key={c.name} value={`databricks:${c.name}`}>⚡ Databricks · {c.name}</option>)}
            </select>
          )}
          <button className="btn primary" onClick={run} disabled={busy || !sql.trim()}>{busy ? 'Running…' : 'Run ⌘↵'}</button>
          {remoteEngine && <span className="muted small">Databricks SQL, read-only, runs on the SQL warehouse</span>}
          {res && <span className="muted small">{fmt.n(res.rows.length)} rows{res.truncated ? ' (first 1,000)' : ''} · {res.elapsed_ms} ms</span>}
        </div>
        {err && <pre className="error">{err}</pre>}
        {res && <DataGrid columns={cols} rows={res.rows} dense />}
      </div>
    </div>
  )
}
