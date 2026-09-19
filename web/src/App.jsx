import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, exportUrl, fmt, store } from './api.js'
import ScopePicker from './components/ScopePicker.jsx'
import ProfileDrawer from './components/ProfileDrawer.jsx'
import { ColumnPane, TablePane } from './components/Results.jsx'
import TableDetail from './components/TableDetail.jsx'
import { AnnotationsView, RelationshipsView, SqlView } from './components/Views.jsx'
import LookupResults from './components/Lookup.jsx'

// `column op value`, e.g. reservationid=9401, guest_code = G1,G2, arrival_date >= 2026-01-01, email ~ gmail
const FILTER_RE = /^\s*([^=<>!~]+?)\s*(>=|<=|!=|=|>|<|~)\s*(.+?)\s*$/
export function parseFilter(q) {
  const m = q.match(FILTER_RE)
  return m && m[1].trim() && m[3].trim() ? { column: m[1].trim(), op: m[2], value: m[3].trim() } : null
}

export default function App() {
  const [view, setView] = useState('explore')
  const [stats, setStats] = useState(null)
  const [allTables, setAllTables] = useState([])
  const [q, setQ] = useState('')
  const [mode, setMode] = useState('name')
  const [match, setMatch] = useState(() => store.get('match', 'fuzzy'))
  const [checked, setChecked] = useState(new Set())
  const [panel, setPanel] = useState('detail') // detail | lookup
  const [lk, setLk] = useState({ data: null, loading: false, error: null, filter: null })
  const [lkLimit, setLkLimit] = useState(100)
  const [lkRemote, setLkRemote] = useState(false)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sel, setSel] = useState(null) // {schema, table}
  const [selCol, setSelCol] = useState(null)
  const [tab, setTab] = useState('columns')
  const [drawer, setDrawer] = useState(null)
  const [workshop, setWorkshop] = useState(() => store.get('workshop', false))
  const [sql, setSql] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [scope, setScopeState] = useState(() => store.get('scope', []))
  const scopeParam = scope.join(',') || undefined
  const scopeRef = useRef(scopeParam)
  scopeRef.current = scopeParam
  const inputRef = useRef(null)
  const seq = useRef(0)

  const loadMeta = useCallback(() => {
    api.stats(scopeRef.current).then(setStats).catch((e) => setError(e.message))
    api.tables(scopeRef.current).then(setAllTables).catch(() => {})
  }, [])
  // first load: honour `bearings serve --schema …`, then drop stored schemas that no longer exist
  useEffect(() => {
    api.stats().then((st) => {
      let sc = st.default_scope?.length ? st.default_scope : store.get('scope', [])
      sc = sc.filter((x) => (st.schemas || []).includes(x))
      setScope(sc)
    }).catch((e) => setError(e.message))
  }, []) // eslint-disable-line
  const setScope = (sc) => {
    setScopeState(sc); store.set('scope', sc); scopeRef.current = sc.join(',') || undefined
    setChecked(new Set()); setPanel('detail')
    loadMeta()
  }
  useEffect(() => { store.set('workshop', workshop); document.body.classList.toggle('workshop', workshop) }, [workshop])
  useEffect(() => {
    const h = (e) => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) { e.preventDefault(); setView('explore'); inputRef.current?.focus() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  const filter = mode === 'name' ? parseFilter(q) : null
  const effMatch = mode === 'value' && match === 'fuzzy' ? 'contains' : match

  const [remoteBusy, setRemoteBusy] = useState(false)
  const runRemoteValue = async () => {
    setRemoteBusy(true); setError(null)
    try { setResults(await api.search(q, 'value', { exact: effMatch === 'exact', schemas: scopeRef.current, remote: true })) }
    catch (e) { setError(e.message) } finally { setRemoteBusy(false) }
  }
  const runSearch = useCallback(async (query, m, mt) => {
    const id = ++seq.current
    if (!query.trim()) { setResults(null); setLoading(false); return }
    setLoading(true); setError(null)
    try {
      const f = m === 'name' ? parseFilter(query) : null
      const r = m === 'value'
        ? await api.search(query, 'value', { exact: mt === 'exact', schemas: scopeRef.current })
        : await api.search(f ? f.column : query, 'name', { match: mt, columns_only: !!f, schemas: scopeRef.current })
      if (id !== seq.current) return
      setResults(r)
      if (r.tables.length && (!sel || !r.tables.some((t) => t.schema === sel.schema && t.table === sel.table))) {
        const first = r.tables[0]
        setSel({ schema: first.schema, table: first.table })
        setSelCol(first.matched_columns?.[0]?.column || null)
        setTab('columns')
      }
    } catch (e) { if (id === seq.current) setError(e.message) } finally { if (id === seq.current) setLoading(false) }
  }, [sel])

  // name search is instant (debounced); value search scans data, so it runs on Enter
  useEffect(() => {
    if (mode !== 'name') return
    const h = setTimeout(() => runSearch(q, 'name', match), 180)
    return () => clearTimeout(h)
  }, [q, mode, match, scopeParam]) // eslint-disable-line
  // value search is expensive: after a scope change just clear its results
  useEffect(() => { if (mode === 'value') setResults(null) }, [scopeParam]) // eslint-disable-line
  // leave the detail panel if the open table is outside the scope
  useEffect(() => { if (sel && scope.length && !scope.includes(sel.schema)) setSel(null) }, [scopeParam]) // eslint-disable-line
  useEffect(() => store.set('match', match), [match])

  const lookupFilter = mode === 'value' ? { column: null, op: effMatch === 'exact' ? '=' : '~', value: q.trim() } : filter
  const runLookup = async (limit = lkLimit) => {
    if (!lookupFilter || !results) return
    const targets = results.tables.filter((t) => checked.has(`${t.schema}.${t.table}`))
      .map((t) => ({ schema: t.schema, table: t.table, columns: t.matched_columns.map((c) => c.column) }))
    setPanel('lookup'); setLk({ data: lk.data, loading: true, error: null, filter: lookupFilter })
    try {
      const data = await api.lookup(targets, lookupFilter.op, lookupFilter.value, limit, lkRemote)
      setLk({ data, loading: false, error: null, filter: lookupFilter })
    } catch (e) { setLk({ data: null, loading: false, error: e.message, filter: lookupFilter }) }
  }
  const nCheckedInResults = results ? results.tables.filter((t) => checked.has(`${t.schema}.${t.table}`)).length : 0
  const canLookup = !!lookupFilter && !!results && nCheckedInResults > 0
  const lookupHint = mode === 'value' ? 'Run the value search first (Enter)' : 'Type column=value in the search box, e.g. reservationid=9401'

  const list = results ? results.tables : allTables
  const hasCols = !!results?.has_column_matches
  const selKey = sel ? `${sel.schema}.${sel.table}` : null
  const highlight = useMemo(() => {
    const r = results?.tables.find((t) => `${t.schema}.${t.table}` === selKey)
    return new Set((r?.matched_columns || []).map((c) => c.column))
  }, [results, selKey])

  const openTable = (schema, table, column = null, t = 'columns') => {
    setView('explore'); setPanel('detail'); setSel({ schema, table }); setSelCol(column); setTab(t)
  }
  const valueSearch = (v) => {
    setDrawer(null); setView('explore'); setMode('value'); setMatch('exact'); setQ(String(v)); runSearch(String(v), 'value', 'exact')
  }

  const empty = stats && (!stats.exists || stats.tables === 0)

  return (
    <div className={`app ${workshop ? 'workshop' : ''}`}>
      <header className="top">
        <div className="brand" title="Bearings — an open-source project by Flyingbear">
          <span className="brand-name">Bearings</span>
          <span className="brand-by">by Flyingbear</span>
        </div>
        <nav className="tabs">
          {[['explore', 'Explore'], ['rels', 'Relationships'], ['ann', 'Annotations'], ['sql', 'SQL']].map(([k, l]) => (
            <button key={k} className={view === k ? 'active' : ''} onClick={() => setView(k)}>{l}</button>
          ))}
        </nav>
        <span className="spacer" />
        <ScopePicker schemas={stats?.schema_stats} scope={scope} setScope={setScope} onSynced={() => { loadMeta(); setRefreshKey((k) => k + 1); if (mode === 'name' && q.trim()) runSearch(q, 'name', match) }} />
        {stats?.exists && <span className="muted small stats-line">{stats.tables} tables · {fmt.n(stats.columns)} columns · {stats.profiled} profiled · {stats.relationships} relationships</span>}
        <label className="check" title="Larger text; PII columns masked in samples"><input type="checkbox" checked={workshop} onChange={(e) => setWorkshop(e.target.checked)} /> Workshop mode</label>
        <a className="btn" href={exportUrl('xlsx', scopeParam)} title="Tables, columns, profile, annotations, relationships (current schema scope)">⤓ Excel</a>
      </header>

      {view === 'explore' && (
        <>
          <div className="searchbar">
            <form onSubmit={(e) => { e.preventDefault(); if (filter && canLookup) runLookup(); else runSearch(q, mode, match) }} className="search-form">
              <span className="search-icon">⌕</span>
              <input ref={inputRef} autoFocus value={q} onChange={(e) => setQ(e.target.value)} className="search-input"
                placeholder={mode === 'name' ? 'Search tables & columns…   or filter: reservationid=9401 · guest_code=G1,G2 · arrival_date>=2026-01-01 · email~gmail' : 'Find a value in the data, e.g. HKG or a booking number — press Enter'} />
              {q && <button type="button" className="icon-btn" onClick={() => { setQ(''); setResults(null); setPanel('detail') }} title="Clear">✕</button>}
            </form>
            <div className="seg" title="Search in: object names / data values">
              <button className={mode === 'name' ? 'active' : ''} onClick={() => { setMode('name'); runSearch(q, 'name', match) }}>Name</button>
              <button className={mode === 'value' ? 'active' : ''} onClick={() => { setMode('value'); setResults(null) }}>Value</button>
            </div>
            <div className="seg" title="Exact: whole name (case, _ and spaces ignored) · Contains: substring · Fuzzy: typo-tolerant, also searches comments and tags">
              {['exact', 'contains', 'fuzzy'].map((m) => (
                <button key={m} className={effMatch === m ? 'active' : ''} disabled={mode === 'value' && m === 'fuzzy'}
                  onClick={() => { setMatch(m); if (mode === 'value') setResults(null) }}>{m[0].toUpperCase() + m.slice(1)}</button>
              ))}
            </div>
            <span className="muted small search-meta">
              {loading ? (mode === 'value' ? 'Scanning data…' : 'Searching…') : results ? `${results.tables.length} tables${hasCols ? `, ${results.tables.reduce((a, t) => a + t.matched_columns.length, 0)} columns` : ''} · ${results.elapsed_ms} ms${results.skipped_remote ? ` · ${results.skipped_remote} remote tables not searched (not profiled)` : ''}${results.searched_remote_cached ? ` · ${results.searched_remote_cached} remote via cached key values` : ''}${results.remote_searched ? ` · ${results.remote_searched} remote tables searched live` : ''}${results.remote_errors?.length ? ` · ${results.remote_errors.length} failed` : ''}` : ''}
            </span>
            {mode === 'value' && results && (results.skipped_remote > 0 || results.searched_remote_cached > 0) && (
              <button className="btn small" disabled={remoteBusy}
                title="Scan the remote tables in scope on the SQL warehouse (one query per table – uses warehouse time)"
                onClick={runRemoteValue}>{remoteBusy ? 'Searching Databricks…' : `⚡ Search ${results.skipped_remote + results.searched_remote_cached} remote tables live`}</button>
            )}
          </div>
          {filter && (
            <div className="filter-hint">
              <span className="chip accent">filter</span> column <b className="mono">{filter.column}</b> ({effMatch}) {filter.op === '~' ? 'contains' : filter.op} <b className="mono">{filter.value}</b>
              <span className="muted"> — tick tables on the left (or select all) and click <b>Show rows</b>{canLookup ? ', or press Enter' : ''}</span>
            </div>
          )}
          {error && <div className="error banner">{error}</div>}
          {empty ? <Welcome db={stats.db} /> : (
            <main className={`explore ${hasCols ? 'three' : 'two'}`}>
              <TablePane results={list} selected={selKey} mode={mode} browsing={!results}
                checked={checked} setChecked={setChecked} canLookup={canLookup} onLookup={() => runLookup()} lookupHint={lookupHint}
                lkRemote={lkRemote} setLkRemote={setLkRemote}
                onSelect={(r) => openTable(r.schema, r.table, r.matched_columns?.[0]?.column || null)}
                onProfile={(r) => openTable(r.schema, r.table, null, 'profile')} />
              {hasCols && <ColumnPane results={results.tables} selectedTable={selKey} selectedColumn={selCol} mode={mode}
                onSelect={(r, c) => openTable(r.schema, r.table, c.column)}
                onProfile={(r, c) => { openTable(r.schema, r.table, c.column); setDrawer({ schema: r.schema, table: r.table, column: c.column }) }} />}
              {panel === 'lookup' && lk.filter ? (
                <LookupResults data={lk.data} loading={lk.loading} error={lk.error} filter={lk.filter} workshop={workshop}
                  limit={lkLimit} setLimit={(n) => { setLkLimit(n); runLookup(n) }} onRerun={() => runLookup()}
                  onClose={() => setPanel('detail')} onOpenTable={openTable} onOpenSql={(s) => { setSql(s); setView('sql') }} />
              ) : sel ? (
                <TableDetail schema={sel.schema} table={sel.table} highlight={highlight} focusColumn={selCol} tab={tab} setTab={setTab}
                  workshop={workshop} allTables={allTables} refreshKey={refreshKey} onPulled={loadMeta}
                  onOpenColumn={(c) => { setSelCol(c); setDrawer({ schema: sel.schema, table: sel.table, column: c }) }}
                  onOpenTable={openTable} onOpenSql={(s) => { setSql(s); setView('sql') }} />
              ) : <Hint />}
            </main>
          )}
        </>
      )}
      {view === 'rels' && <RelationshipsView onOpenTable={openTable} scope={scopeParam} />}
      {view === 'ann' && <AnnotationsView onOpenTable={openTable} refreshKey={refreshKey} scope={scopeParam} />}
      {view === 'sql' && <SqlView sql={sql} setSql={setSql} tables={allTables} />}

      {drawer && <ProfileDrawer target={drawer} onClose={() => setDrawer(null)} onValueSearch={valueSearch}
        onOpenTable={(s, t, c) => { setDrawer(null); openTable(s, t, c) }} onSaved={() => { setRefreshKey((k) => k + 1); loadMeta() }} />}
    </div>
  )
}

function Hint() {
  return (
    <div className="detail hint">
      <h3>Pick a table, or search</h3>
      <ul>
        <li><b>Name search</b> is fuzzy across table names, column names, comments and your tags / CDM mappings. Wildcards work: <code>*_dt</code>, <code>res*</code>. Use <code>table.column</code> to narrow it down.</li>
        <li><b>Value search</b> finds which columns contain a value (e.g. a property code or confirmation number). It scans the data, so press Enter.</li>
        <li>Click a <b>column</b> to open its table's schema with the matches highlighted. The <b>▤</b> button opens a profile.</li>
        <li>In the schema, tick columns to <b>sample</b> just those or to <b>check whether they form a key</b>.</li>
        <li>Press <kbd>/</kbd> to jump to search.</li>
      </ul>
    </div>
  )
}

function Welcome({ db }) {
  return (
    <div className="detail hint welcome">
      <h3>No data loaded yet</h3>
      <p className="muted">Database: <code>{db}</code></p>
      <p>Try it with the sample hotel dataset (PMS + CRM, fictional):</p>
      <pre>{`uv run bearings demo
uv run bearings serve --db data/demo.duckdb`}</pre>
      <p>Or load your own Databricks exports:</p>
      <pre>{`# 1. load exports (CSV or Parquet; a folder of part-files = one table)
uv run bearings load ./exports --schema pms

# 2. optional: column descriptions (export of information_schema.columns)
uv run bearings comments ./exports/columns.csv

# 3. profile + find relationships
uv run bearings profile
uv run bearings relate`}</pre>
      <p className="muted">Then refresh this page.</p>
    </div>
  )
}
