import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, exportUrl, fmt, recent, store, waitJob } from './api.js'
import AddData, { filesFromDrop } from './components/AddData.jsx'
import QuickOpen, { ShortcutHelp } from './components/QuickOpen.jsx'
import ScopePicker from './components/ScopePicker.jsx'
import ProfileDrawer from './components/ProfileDrawer.jsx'
import { ColumnPane, TablePane } from './components/Results.jsx'
import TableDetail from './components/TableDetail.jsx'
import { AnnotationsView, RelationshipsView, SqlView } from './components/Views.jsx'
import CodeListsView from './components/CodeLists.jsx'
import LookupResults from './components/Lookup.jsx'

// `column op value`, e.g. reservationid=9401, guest_code = G1,G2, arrival_date >= 2026-01-01, email ~ gmail
const FILTER_RE = /^\s*([^=<>!~]+?)\s*(>=|<=|!=|=|>|<|~)\s*(.+?)\s*$/
export function parseFilter(q) {
  const m = q.match(FILTER_RE)
  return m && m[1].trim() && m[3].trim() ? { column: m[1].trim(), op: m[2], value: m[3].trim() } : null
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
const MOD = isMac ? '⌘' : 'Ctrl'

function sortTables(list, how) {
  if (!how || how === 'relevance') return list
  const by = {
    name: (a, b) => a.table.localeCompare(b.table) || a.schema.localeCompare(b.schema),
    rows: (a, b) => (b.row_count ?? -1) - (a.row_count ?? -1),
    columns: (a, b) => (b.column_count ?? b.columns?.length ?? 0) - (a.column_count ?? a.columns?.length ?? 0),
    schema: (a, b) => a.schema.localeCompare(b.schema) || a.table.localeCompare(b.table),
  }[how]
  return by ? [...list].sort(by) : list
}

/** The part of the query worth highlighting: no wildcards, the column part of table.column / column=value. */
function highlightTerm(q, mode, filter) {
  if (mode === 'value') return q.trim()
  const t = (filter ? filter.column : q).replace(/\*/g, '').trim()
  return t.includes('.') ? t.split('.').pop() : t
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
  const [tableSort, setTableSortState] = useState(() => store.get('tableSort', 'relevance'))
  const setTableSort = (v) => { setTableSortState(v); store.set('tableSort', v) }
  const [adding, setAdding] = useState(null)   // null | {files?: [...]} – the Add data dialog
  const [palette, setPalette] = useState(false)
  const [help, setHelp] = useState(false)
  const [toast, setToast] = useState(null)
  const [dragging, setDragging] = useState(false)

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
  // toasts (e.g. "Copied") from anywhere
  useEffect(() => {
    let timer
    const h = (e) => { setToast(e.detail); clearTimeout(timer); timer = setTimeout(() => setToast(null), 1800) }
    window.addEventListener('bearings:toast', h)
    return () => { window.removeEventListener('bearings:toast', h); clearTimeout(timer) }
  }, [])
  // drop files anywhere → Add data
  useEffect(() => {
    const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files')
    const over = (e) => { if (hasFiles(e)) { e.preventDefault(); if (!adding) setDragging(true) } }
    const leave = (e) => { if (!e.relatedTarget || e.clientX <= 0 || e.clientY <= 0) setDragging(false) }
    const drop = async (e) => {
      if (!hasFiles(e)) return
      e.preventDefault(); setDragging(false)
      if (adding) return  // the dialog's own drop zone handles it
      const files = await filesFromDrop(e.dataTransfer)
      if (files.length) setAdding({ files })
    }
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    return () => { window.removeEventListener('dragover', over); window.removeEventListener('dragleave', leave); window.removeEventListener('drop', drop) }
  }, [adding])

  // modelling insights for every profiled table in scope (background job, progress pill in the header)
  const [insJob, setInsJob] = useState(null)   // running job, or {finished: true, text}
  const runAllInsights = useCallback(async (missing = true) => {
    if (insJob && !insJob.finished) return
    setError(null)
    try {
      const j0 = await api.runInsights({ schemas: scopeRef.current ? scopeRef.current.split(',') : undefined, missing })
      setInsJob(j0)
      const j = await waitJob(j0, setInsJob)
      const errs = j.errors?.length ? ` · ${j.errors.length} failed (${j.errors[0].table}: ${j.errors[0].error})` : ''
      setInsJob({ finished: true, failed: !!j.errors?.length, text: `✓ Insights computed for ${j.results.length} table${j.results.length === 1 ? '' : 's'}${errs}` })
      loadMeta(); setRefreshKey((k) => k + 1)
      window.dispatchEvent(new CustomEvent('bearings:insights-done'))
    } catch (e) { setInsJob(null); setError(e.message) }
  }, [insJob, loadMeta])
  useEffect(() => {
    const h = (e) => runAllInsights(e.detail?.missing ?? true)
    window.addEventListener('bearings:insights-all', h)
    return () => window.removeEventListener('bearings:insights-all', h)
  }, [runAllInsights])
  useEffect(() => {
    if (!insJob?.finished || insJob.failed) return
    const t = setTimeout(() => setInsJob(null), 10000)
    return () => clearTimeout(t)
  }, [insJob])

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

  const list = useMemo(() => sortTables(results ? results.tables : allTables, tableSort), [results, allTables, tableSort])
  const term = highlightTerm(q, mode, filter)
  const hasCols = !!results?.has_column_matches
  const selKey = sel ? `${sel.schema}.${sel.table}` : null
  const highlight = useMemo(() => {
    const r = results?.tables.find((t) => `${t.schema}.${t.table}` === selKey)
    return new Set((r?.matched_columns || []).map((c) => c.column))
  }, [results, selKey])

  const openTable = (schema, table, column = null, t = 'columns') => {
    setView('explore'); setPanel('detail'); setSel({ schema, table }); setSelCol(column); setTab(t)
  }
  // remember a table once it has been looked at for a moment (not every table passed with the arrow keys)
  useEffect(() => {
    if (!sel) return
    const h = setTimeout(() => recent.add(sel.schema, sel.table), 1500)
    return () => clearTimeout(h)
  }, [selKey]) // eslint-disable-line

  // keyboard: ↑/↓ tables, ⇧↑/⇧↓ matched columns, x tick, 1-6 tabs, s sample, a add data, ? help, ⌘/Ctrl+K jump
  const matchedCols = useMemo(() => (results?.tables || []).flatMap((r) => (r.matched_columns || []).map((c) => ({ r, c }))), [results])
  useEffect(() => {
    const h = (e) => {
      const el = document.activeElement
      const inSearch = el === inputRef.current
      const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el?.tagName) || el?.isContentEditable
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette((x) => !x); return }
      if (palette || help || adding || e.metaKey || e.ctrlKey || e.altKey) return
      if (inField && !inSearch) return
      if (e.key === '/' && !inSearch) { e.preventDefault(); setView('explore'); inputRef.current?.focus(); return }
      if (inSearch && !['ArrowDown', 'ArrowUp', 'Escape'].includes(e.key)) return
      if (e.key === '?') { e.preventDefault(); setHelp(true); return }
      if (e.key === 'a') { e.preventDefault(); setAdding({}); return }
      if (view !== 'explore') return
      const move = (d) => {
        if (e.shiftKey && matchedCols.length) {
          const at = matchedCols.findIndex(({ r, c }) => `${r.schema}.${r.table}` === selKey && c.column === selCol)
          const nx = matchedCols[Math.max(0, Math.min(matchedCols.length - 1, at + d))]
          if (nx) openTable(nx.r.schema, nx.r.table, nx.c.column, tab)
          return
        }
        if (!list.length) return
        const at = list.findIndex((t) => `${t.schema}.${t.table}` === selKey)
        const nx = list[at === -1 ? 0 : Math.max(0, Math.min(list.length - 1, at + d))]
        openTable(nx.schema, nx.table, nx.matched_columns?.[0]?.column || null, ['profile', 'sample', 'rels', 'insights', 'quality'].includes(tab) ? tab : 'columns')
      }
      switch (e.key) {
        case 'ArrowDown': e.preventDefault(); move(1); break
        case 'ArrowUp': e.preventDefault(); move(-1); break
        case 'Escape':
          if (inSearch && q) { setQ(''); setResults(null); setPanel('detail') } else if (panel === 'lookup') { setPanel('detail') } else { inputRef.current?.blur() }
          break
        case 'x': if (selKey) { const n = new Set(checked); n.has(selKey) ? n.delete(selKey) : n.add(selKey); setChecked(n) } break
        case '1': case '2': case '3': case '4': case '5': case '6': if (sel) { setPanel('detail'); setTab(['columns', 'sample', 'profile', 'rels', 'insights', 'quality'][Number(e.key) - 1]) } break
        case 's': if (sel) { setPanel('detail'); setTab('sample') } break
        default:
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })

  const commands = [
    { label: 'Add data (files, folder or path)…', keys: 'a', run: () => setAdding({}) },
    { label: 'Go to Explore', run: () => setView('explore') },
    { label: 'Go to Relationships', run: () => setView('rels') },
    { label: 'Go to Annotations', run: () => setView('ann') },
    { label: 'Go to SQL', run: () => setView('sql') },
    { label: 'Search values in the data', run: () => { setView('explore'); setMode('value'); setResults(null); setTimeout(() => inputRef.current?.focus()) } },
    { label: `${workshop ? 'Leave' : 'Enter'} workshop mode`, run: () => setWorkshop((w) => !w) },
    ...(scope.length ? [{ label: 'Show all schemas (clear scope)', run: () => setScope([]) }] : []),
    { label: `Compute insights for tables without them${scope.length ? ' (in scope)' : ''}`, run: () => runAllInsights(true) },
    { label: `Recompute insights for all profiled tables${scope.length ? ' (in scope)' : ''}`, run: () => runAllInsights(false) },
    { label: 'Export Excel mapping workbook', run: () => { window.location.href = exportUrl('xlsx', scopeParam) } },
    { label: 'Keyboard shortcuts', keys: '?', run: () => setHelp(true) },
  ]
  const onLoaded = (job) => {
    if (scope.length && job.schema && !scope.includes(job.schema)) setScope([...scope, job.schema].sort())
    else loadMeta()
    setRefreshKey((k) => k + 1)
    if (mode === 'name' && q.trim()) runSearch(q, 'name', match)
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
          <span className="brand-by">by Flyingbear{stats?.version ? <span className="brand-ver" title={`Bearings version ${stats.version}`}> · v{stats.version}</span> : null}</span>
        </div>
        <nav className="tabs">
          {[['explore', 'Explore'], ['rels', 'Relationships'], ['codes', 'Code lists'], ['ann', 'Annotations'], ['sql', 'SQL']].map(([k, l]) => (
            <button key={k} className={view === k ? 'active' : ''} onClick={() => setView(k)}>{l}</button>
          ))}
        </nav>
        <span className="spacer" />
        <button className="btn jump" onClick={() => setPalette(true)} title="Jump to any table or column, or run an action">⌕ <span className="jump-label">Jump to…</span> <kbd>{MOD} K</kbd></button>
        <button className="btn" onClick={() => setAdding({})} title="Load CSV, Parquet, JSON or Excel files (or drop them anywhere) · a">＋ <span className="add-label">Add data</span></button>
        <ScopePicker schemas={stats?.schema_stats} scope={scope} setScope={setScope} onSynced={() => { loadMeta(); setRefreshKey((k) => k + 1); if (mode === 'name' && q.trim()) runSearch(q, 'name', match) }} />
        {insJob && (insJob.finished
          ? <button className={`job-pill ${insJob.failed ? 'bad' : 'ok'}`} onClick={() => setInsJob(null)} title="Dismiss">{insJob.text}</button>
          : <span className="job-pill" title={insJob.tables?.join('\n')}>
              <span className="spin">↻</span> Insights {insJob.done}/{insJob.total}{insJob.current ? ` · ${insJob.current}` : ''}{insJob.step ? ` · ${insJob.step}` : ''}
            </span>)}
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
                title="Scan the remote tables in scope live on their SQL engine (one query per table – uses remote compute time)"
                onClick={runRemoteValue}>{remoteBusy ? 'Searching remote tables…' : `⚡ Search ${results.skipped_remote + results.searched_remote_cached} remote tables live`}</button>
            )}
          </div>
          {filter && (
            <div className="filter-hint">
              <span className="chip accent">filter</span> column <b className="mono">{filter.column}</b> ({effMatch}) {filter.op === '~' ? 'contains' : filter.op} <b className="mono">{filter.value}</b>
              <span className="muted"> — tick tables on the left (or select all) and click <b>Show rows</b>{canLookup ? ', or press Enter' : ''}</span>
            </div>
          )}
          {error && <div className="error banner">{error}</div>}
          {empty ? <Welcome db={stats.db} onAdd={() => setAdding({})} /> : (
            <main className={`explore ${hasCols ? 'three' : 'two'}`}>
              <TablePane results={list} selected={selKey} mode={mode} browsing={!results} term={term} sort={tableSort} setSort={setTableSort}
                checked={checked} setChecked={setChecked} canLookup={canLookup} onLookup={() => runLookup()} lookupHint={lookupHint}
                lkRemote={lkRemote} setLkRemote={setLkRemote}
                onSelect={(r) => openTable(r.schema, r.table, r.matched_columns?.[0]?.column || null)}
                onProfile={(r) => openTable(r.schema, r.table, null, 'profile')} />
              {hasCols && <ColumnPane results={results.tables} selectedTable={selKey} selectedColumn={selCol} mode={mode} term={term}
                onSelect={(r, c) => openTable(r.schema, r.table, c.column)}
                onProfile={(r, c) => { openTable(r.schema, r.table, c.column); setDrawer({ schema: r.schema, table: r.table, column: c.column }) }} />}
              {panel === 'lookup' && lk.filter ? (
                <LookupResults data={lk.data} loading={lk.loading} error={lk.error} filter={lk.filter} workshop={workshop}
                  limit={lkLimit} setLimit={(n) => { setLkLimit(n); runLookup(n) }} onRerun={() => runLookup()}
                  onClose={() => setPanel('detail')} onOpenTable={openTable} onOpenSql={(s) => { setSql(s); setView('sql') }} />
              ) : sel ? (
                <TableDetail schema={sel.schema} table={sel.table} highlight={highlight} focusColumn={selCol} tab={tab} setTab={setTab}
                  workshop={workshop} allTables={allTables} refreshKey={refreshKey} onPulled={loadMeta} term={term}
                  onOpenColumn={(c) => { setSelCol(c); setDrawer({ schema: sel.schema, table: sel.table, column: c }) }}
                  onOpenTable={openTable} onOpenSql={(s) => { setSql(s); setView('sql') }} />
              ) : <Hint tables={allTables} onOpenTable={openTable} />}
            </main>
          )}
        </>
      )}
      {view === 'rels' && <RelationshipsView onOpenTable={openTable} scope={scopeParam} onOpenSql={(s) => { setSql(s); setView('sql') }} />}
      {view === 'codes' && <CodeListsView onOpenTable={openTable} scope={scopeParam} />}
      {view === 'ann' && <AnnotationsView onOpenTable={openTable} refreshKey={refreshKey} scope={scopeParam} />}
      {view === 'sql' && <SqlView sql={sql} setSql={setSql} tables={allTables} />}

      {adding && <AddData initialFiles={adding.files} schemas={stats?.schemas || []} onClose={() => setAdding(null)} onLoaded={onLoaded} onOpenTable={openTable} />}
      {palette && <QuickOpen tables={allTables} scope={scopeParam} commands={commands} onOpenTable={openTable} onClose={() => setPalette(false)} />}
      {help && <ShortcutHelp onClose={() => setHelp(false)} />}
      {dragging && !adding && <div className="drop-overlay"><div>⤓ Drop to add data<div className="small muted">CSV · Parquet · JSON · Excel — files or folders</div></div></div>}
      {toast && <div className="toast">{toast}</div>}
      {drawer && <ProfileDrawer target={drawer} onClose={() => setDrawer(null)} onValueSearch={valueSearch}
        onOpenTable={(s, t, c) => { setDrawer(null); openTable(s, t, c) }} onSaved={() => { setRefreshKey((k) => k + 1); loadMeta() }} />}
    </div>
  )
}

function Hint({ tables = [], onOpenTable }) {
  const byKey = Object.fromEntries(tables.map((t) => [`${t.schema}.${t.table}`, t]))
  const rec = recent.get().filter((k) => byKey[k]).slice(0, 8)
  return (
    <div className="detail hint">
      {rec.length > 0 && (
        <>
          <h3>Recent tables</h3>
          <div className="recent">
            {rec.map((k) => <button key={k} className="btn mono" onClick={() => onOpenTable(byKey[k].schema, byKey[k].table)}><span className="muted">{byKey[k].schema}.</span>{byKey[k].table}</button>)}
          </div>
        </>
      )}
      <h3>Pick a table, or search</h3>
      <ul>
        <li><b>Name search</b> is fuzzy across table names, column names, comments and your tags / CDM mappings. Wildcards work: <code>*_dt</code>, <code>res*</code>. Use <code>table.column</code> to narrow it down.</li>
        <li><b>Value search</b> finds which columns contain a value (e.g. a property code or confirmation number). It scans the data, so press Enter.</li>
        <li>Click a <b>column</b> to open its table's schema with the matches highlighted. The <b>▤</b> button opens a profile.</li>
        <li>In the schema, tick columns to <b>sample</b> just those or to <b>check whether they form a key</b>.</li>
        <li><kbd>{MOD} K</kbd> jumps to any table or column · <kbd>↓</kbd><kbd>↑</kbd> move through the list · <kbd>/</kbd> search · <kbd>?</kbd> all shortcuts.</li>
        <li>Drop CSV, Parquet, JSON or Excel files anywhere to <b>add data</b>.</li>
      </ul>
    </div>
  )
}

function Welcome({ db, onAdd }) {
  return (
    <div className="detail hint welcome">
      <h3>No data loaded yet</h3>
      <p className="muted">Database: <code>{db}</code></p>
      <div className="welcome-drop" onClick={onAdd}>
        <div className="dz-icon">⤓</div>
        <b>Drop files or a folder here, or click to add data</b>
        <div className="muted small">CSV · TSV · Parquet · JSON · Excel. A folder becomes a schema; the tables are profiled and related automatically.</div>
      </div>
      <p>Or try it with the sample hotel dataset (PMS + CRM, fictional):</p>
      <pre>{`uv run bearings demo
uv run bearings serve --db data/demo.duckdb`}</pre>
      <p>From the command line:</p>
      <pre>{`uv run bearings load ./exports/opera --schema pms     # CSV / Parquet / JSON / Excel
uv run bearings comments ./exports/columns.csv         # optional descriptions
uv run bearings profile && uv run bearings relate`}</pre>
    </div>
  )
}
