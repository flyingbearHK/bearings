import React, { useEffect, useMemo, useRef, useState } from 'react'
import { STORAGE, ago, api, fmt, isPII, sourceNote, store } from '../api.js'
import { Bar, Flags, Tags } from './Charts.jsx'
import ColumnPicker, { visibleKeys } from './ColumnPicker.jsx'
import DataGrid, { Cell } from './DataGrid.jsx'
import RemoteProfileButton, { PullButton, WarehouseState } from './RemoteProfile.jsx'

const SCHEMA_FIELDS = [
  { key: 'ordinal', label: '#' }, { key: 'column', label: 'Column' }, { key: 'type', label: 'Type' },
  { key: 'null_pct', label: 'Null %' }, { key: 'distinct_count', label: 'Distinct' }, { key: 'distinct_pct', label: 'Distinct %' },
  { key: 'min', label: 'Min' }, { key: 'max', label: 'Max' }, { key: 'top', label: 'Top value' },
  { key: 'flags', label: 'Profile flags' }, { key: 'tags', label: 'Tags' }, { key: 'cdm', label: 'CDM mapping' },
  { key: 'comment', label: 'Comment' },
]
const SCHEMA_DEFAULT = { order: SCHEMA_FIELDS.map((f) => f.key), hidden: ['top', 'distinct_pct'] }

export default function TableDetail({ schema, table, highlight, focusColumn, tab, setTab, onOpenColumn, onOpenTable,
  workshop, onOpenSql, allTables, refreshKey, onPulled }) {
  const [t, setT] = useState(null)
  const [err, setErr] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [schemaView, setSchemaView] = useState(() => store.get('schemaFields', SCHEMA_DEFAULT))
  const [uniq, setUniq] = useState(null)
  const [md, setMd] = useState(null)
  const focusRef = useRef(null)
  const [req, setReq] = useState({ n: 20, only: null, id: 0 })
  const [reload, setReload] = useState(0)
  const [useRemote, setUseRemote] = useState(false)
  const sampleRequest = (n, only = null) => { setReq((r) => ({ n, only, id: r.id + 1 })); setTab('sample') }

  useEffect(() => {
    let off = false
    setErr(null); setUniq(null); setSelected(new Set()); setMd(null)
    api.table(schema, table).then((r) => !off && setT(r)).catch((e) => !off && setErr(e.message))
    return () => { off = true }
  }, [schema, table, refreshKey, reload])

  useEffect(() => { focusRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }) }, [t, focusColumn, tab])
  useEffect(() => store.set('schemaFields', schemaView), [schemaView])

  const hl = highlight || new Set()
  if (err) return <div className="detail"><div className="error">{err}</div></div>
  if (!t || t.schema !== schema || t.table !== table) return <div className="detail"><div className="muted pad">Loading {schema}.{table}…</div></div>

  const tp = t.table_profile
  const flagged = t.columns.filter((c) => c.profile?.flags?.length).length
  const toggleSel = (c) => { const s = new Set(selected); s.has(c) ? s.delete(c) : s.add(c); setSelected(s) }

  const fieldRender = {
    ordinal: { render: (c) => c.ordinal, align: 'right', width: 40 },
    column: {
      render: (c) => (
        <span className="colname" ref={c.column === focusColumn ? focusRef : undefined}>
          <input type="checkbox" checked={selected.has(c.column)} onClick={(e) => e.stopPropagation()} onChange={() => toggleSel(c.column)} title="Select for sample / key check" />
          <span className="mono">{c.column}</span>
          {tp?.candidate_keys?.includes(c.column) && <span className="chip good" title="Candidate key">PK?</span>}
          <button className="icon-btn small" title="Column profile" onClick={(e) => { e.stopPropagation(); onOpenColumn(c.column) }}>▤</button>
        </span>),
      value: (c) => c.column,
    },
    type: { render: (c) => <span className="mono muted">{c.type}</span>, value: (c) => c.type },
    null_pct: { render: (c) => c.profile ? <span className="numbar"><Bar pct={c.profile.null_pct} tone={c.profile.null_pct >= 50 ? 'warn' : 'accent'} width={40} />{fmt.pct(c.profile.null_pct)}</span> : '', value: (c) => c.profile?.null_pct, align: 'right' },
    distinct_count: { render: (c) => fmt.n(c.profile?.distinct_count), value: (c) => c.profile?.distinct_count, align: 'right' },
    distinct_pct: { render: (c) => fmt.pct(c.profile?.distinct_pct), value: (c) => c.profile?.distinct_pct, align: 'right' },
    min: { render: (c) => <Cell v={c.profile?.min_val ?? ''} masked={workshop && isPII(c)} />, value: (c) => c.profile?.min_val },
    max: { render: (c) => <Cell v={c.profile?.max_val ?? ''} masked={workshop && isPII(c)} />, value: (c) => c.profile?.max_val },
    top: { render: (c) => { const x = c.profile?.top_values?.[0]; return x ? <span><Cell v={x.v} masked={workshop && isPII(c)} /> <span className="muted small">×{fmt.n(x.n)}</span></span> : '' }, value: (c) => c.profile?.top_values?.[0]?.v },
    flags: { render: (c) => <Flags flags={c.profile?.flags} />, value: (c) => (c.profile?.flags || []).join(',') },
    tags: { render: (c) => <Tags tags={c.annotation?.tags} />, value: (c) => c.annotation?.tags },
    cdm: { render: (c) => c.annotation?.cdm_entity ? <span className="mono small">{c.annotation.cdm_entity}{c.annotation.cdm_attribute ? '.' + c.annotation.cdm_attribute : ''}</span> : '', value: (c) => c.annotation?.cdm_entity },
    comment: { render: (c) => <span className="comment" title={c.comment || ''}>{c.comment}</span>, value: (c) => c.comment },
  }
  const schemaCols = visibleKeys(SCHEMA_FIELDS, schemaView).map((k) => ({ key: k, label: SCHEMA_FIELDS.find((f) => f.key === k).label, ...fieldRender[k] }))

  const checkKey = async () => { setUniq({ loading: true }); try { setUniq(await api.uniqueness(schema, table, [...selected], useRemote)) } catch (e) { setUniq({ error: e.message }) } }
  const selectSql = `SELECT ${t.columns.map((c) => `"${c.column}"`).join(', ')}\nFROM "${schema}"."${table}"\nLIMIT 100`

  return (
    <div className="detail">
      <div className="detail-head">
        <div className="title-row">
          <h2><span className="muted">{schema}.</span>{table}</h2>
          <span className="muted">{t.kind === 'remote' ? '' : `${fmt.n(t.row_count)} rows · `}{t.columns.length} columns</span>
          {t.annotation?.cdm_entity && <span className="chip tag">CDM: {t.annotation.cdm_entity}</span>}
        </div>
        {t.remote && (
          <div className={`remote-line ${t.kind === 'remote' ? 'meta-only' : ''}`}>
            <span className="cloud">☁</span> Databricks <span className="mono">{t.remote.full_name}</span>
            <span className="muted small"> · {t.remote.connection} · synced {ago(t.remote.synced_at)}</span>
            {t.kind === 'remote'
              ? <span className="small"> — rows stay in Databricks. Samples, key checks and lookups run live on the SQL warehouse (⚡).
                  {t.table_profile ? ' Profile, relationships and value search use the cached profile and key values.' : ' Profile it to get stats, key detection and relationships.'}</span>
              : t.storage === 'sample'
                ? <span className="small"> — <span className="chip warn">{STORAGE.sample.label}</span> {fmt.n(t.remote.cache?.rows)} of {fmt.n(t.remote.cache?.total)} rows cached {ago(t.remote.cache?.cached_at)}.
                    Queries run on the sample; tick <b>⚡ Remote</b> for the whole table.{t.table_profile?.stale ? ' The source has changed since – bearings refresh.' : ''}</span>
                : <span className="small"> — <span className="chip good">{STORAGE.cached.label}</span> all {fmt.n(t.remote.cache?.rows ?? t.row_count)} rows cached {ago(t.remote.cache?.cached_at)}; queries run locally.
                    {t.table_profile?.stale ? ' The source has changed since – bearings refresh.' : ''}</span>}
            {t.kind === 'remote' && (
              <div className="remote-actions">
                <RemoteProfileButton schema={schema} table={table} profiled={!!t.table_profile} stale={t.table_profile?.stale}
                  onDone={() => setReload((k) => k + 1)} />
                <PullButton schema={schema} table={table} onDone={() => { setReload((k) => k + 1); onPulled?.() }} />
                {t.table_profile && <span className="muted small">profiled {ago(t.table_profile.profiled_at)}{t.table_profile.sampled_rows ? ` · sample ${fmt.n(t.table_profile.sampled_rows)} rows for top values` : ' · whole table'}</span>}
                <WarehouseState connection={t.remote.connection} />
              </div>
            )}
            {t.kind !== 'remote' && t.remote.cache && (
              <div className="cache-facts small">
                {t.remote.cache.method && t.remote.cache.method !== 'random' && (
                  <span title="Sampled on a key shared with related big tables, so the cached samples join">🔗 sample {t.remote.cache.method.replace(/^key:/, 'keyed on ')}</span>
                )}
                {t.remote.cache.method === 'random' && <span title="Random sample">random sample</span>}
                {t.remote.cache.masked?.length > 0 && (
                  <span title={`Hashed in the local cache and profile: ${t.remote.cache.masked.join(', ')}. Lookups hash what you type the same way; ⚡ Remote shows real values.`}>
                    🔒 {t.remote.cache.masked.length} PII column{t.remote.cache.masked.length > 1 ? 's' : ''} masked</span>
                )}
                {t.remote.cache.outdated
                  ? <span className="warn-text" title={`Cached at Delta version ${t.remote.cache.version}; Databricks is at ${t.remote.cache.latest_version} (checked ${ago(t.remote.cache.checked_at)})`}>
                      ⚠ source data changed (v{t.remote.cache.version} → v{t.remote.cache.latest_version}) – re-cache</span>
                  : t.remote.cache.version != null && <span className="muted" title={`Checked ${ago(t.remote.cache.checked_at)}`}>Delta v{t.remote.cache.version}</span>}
              </div>
            )}
            {t.kind !== 'remote' && (
              <div className="remote-actions">
                <PullButton schema={schema} table={table} cached onDone={() => { setReload((k) => k + 1); onPulled?.() }} />
                <WarehouseState connection={t.remote.connection} />
              </div>
            )}
          </div>
        )}
        {t.comment && <div className="comment-line">{t.comment}</div>}
        <div className="toolbar">
          <div className="tabs small-tabs">
            {[['columns', 'Schema'], ['sample', 'Sample data'], ['profile', 'Profile'], ['rels', `Relationships${t.relationships.length ? ` (${t.relationships.length})` : ''}`]].map(([k, l]) => (
              <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>
            ))}
          </div>
          <span className="spacer" />
          {t.remote && (
            <label className={`check remote-toggle ${t.kind === 'remote' || useRemote ? 'on' : ''}`}
              title={t.kind === 'remote' ? 'Not cached: sample and key check run on Databricks' : 'Run sample and key check on Databricks (whole table, slower) instead of the local cache'}>
              <input type="checkbox" checked={t.kind === 'remote' || useRemote} disabled={t.kind === 'remote'} onChange={(e) => setUseRemote(e.target.checked)} /> ⚡ Remote
            </label>
          )}
          <button className="btn" onClick={() => sampleRequest(10)}>Sample 10</button>
          <button className="btn" onClick={() => sampleRequest(20)}>Sample 20</button>
          <button className="btn" onClick={() => setTab('profile')}>Profile</button>
          <button className="btn" title="Markdown table spec for your CDM notes" onClick={async () => setMd(await api.markdown(schema, table))}>Export .md</button>
          <button className="btn" onClick={() => onOpenSql(selectSql)}>Open in SQL</button>
        </div>
      </div>

      {md && (
        <div className="md-box">
          <div className="md-actions"><button className="btn" onClick={() => navigator.clipboard.writeText(md)}>Copy</button>
            <button className="btn" onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([md], { type: 'text/markdown' })); a.download = `${schema}.${table}.md`; a.click() }}>Download</button>
            <button className="icon-btn" onClick={() => setMd(null)}>✕</button></div>
          <pre>{md}</pre>
        </div>
      )}

      {tab === 'columns' && (
        <>
          <div className="subbar">
            <ColumnPicker label="Fields" items={SCHEMA_FIELDS} value={schemaView} onChange={setSchemaView}
              presets={[{ label: 'Compact', apply: () => ({ order: SCHEMA_DEFAULT.order, hidden: ['min', 'max', 'top', 'distinct_pct', 'cdm', 'comment'] }) },
                        { label: 'Default', apply: () => SCHEMA_DEFAULT }]} />
            {!tp && <span className="muted small">Not profiled — run <code>bearings profile -t {schema}.{table}</code> or open the Profile tab.</span>}
            {hl.size > 0 && <span className="muted small"><span className="hl-swatch" /> {[...hl].filter((c) => t.columns.some((x) => x.column === c)).length} matched</span>}
            <span className="spacer" />
            {selected.size > 0 && (
              <>
                <span className="muted small">{selected.size} selected</span>
                <button className="btn" onClick={() => sampleRequest(20, [...selected])}>Sample selected</button>
                <button className="btn" onClick={checkKey} title="Is this column combination unique?">Check key</button>
                <button className="link" onClick={() => setSelected(new Set())}>clear</button>
              </>
            )}
          </div>
          {uniq && (
            <div className={`notice ${uniq.is_unique ? 'good' : uniq.error ? 'bad' : ''}`}>
              {uniq.loading ? 'Checking…' : uniq.error ? uniq.error : (
                <>
                  <b>{uniq.columns.join(' + ')}</b>: {uniq.is_unique ? 'unique — valid key ✓' : `not unique — ${fmt.n(uniq.rows - uniq.distinct)} duplicate rows`}
                  {uniq.rows_with_nulls > 0 && <> · {fmt.n(uniq.rows_with_nulls)} rows with nulls</>}
                  {uniq.source && uniq.source !== 'local' && <span className="muted small"> · {sourceNote(uniq)}</span>}
                  {uniq.source === 'sample' && uniq.is_unique && <div className="small">Unique in the sample only – tick <b>⚡ Remote</b> and check again to be sure for the whole table.</div>}
                  {!uniq.is_unique && uniq.duplicate_examples.length > 0 && (
                    <div className="mono small muted">e.g. {uniq.duplicate_examples.slice(0, 3).map((d) => `(${d.slice(0, -1).join(', ')}) ×${d[d.length - 1]}`).join('  ')}</div>
                  )}
                </>
              )}
              <button className="icon-btn small" onClick={() => setUniq(null)}>✕</button>
            </div>
          )}
          <DataGrid columns={schemaCols} rows={t.columns} rowKey={(c) => c.column}
            rowClass={(c) => [hl.has(c.column) ? 'hl' : '', c.column === focusColumn ? 'focus' : ''].join(' ')}
            onRowClick={(c) => onOpenColumn(c.column)} />
        </>
      )}

      {tab === 'sample' && <SamplePanel key={`${schema}.${table}.${req.id}`} t={t} hl={hl} workshop={workshop} n={req.n} only={req.only} remote={useRemote} />}
      {tab === 'profile' && <ProfilePanel t={t} onOpenColumn={onOpenColumn} onReload={() => setReload((k) => k + 1)} />}
      {tab === 'rels' && <RelPanel t={t} allTables={allTables} onOpenTable={onOpenTable} />}
    </div>
  )
}

/* ------------------------------------------------------------------ sample */
export function SamplePanel({ t, hl, workshop, n: n0 = 20, only, remote = false }) {
  const key = `sample:${t.schema}.${t.table}`
  const items = t.columns.map((c) => ({ key: c.column, label: c.column, hint: c.type.toLowerCase(), strong: hl.has(c.column) }))
  const [view, setView] = useState(() => {
    if (only?.length) return { order: [...only, ...items.map((i) => i.key).filter((k) => !only.includes(k))], hidden: items.map((i) => i.key).filter((k) => !only.includes(k)) }
    return store.get(key, { order: [], hidden: [] })
  })
  const [n, setN] = useState(n0)
  const [nonNull, setNonNull] = useState(false)
  const [where, setWhere] = useState('')
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)
  const [unmask, setUnmask] = useState(false)
  const [tick, setTick] = useState(0)
  const visible = visibleKeys(items, view)
  const hlCols = t.columns.filter((c) => hl.has(c.column)).map((c) => c.column)

  useEffect(() => { if (!only?.length) store.set(key, view) }, [view])
  useEffect(() => {
    let off = false
    setErr(null)
    api.sample(t.schema, t.table, { n, columns: visible.join(','), nonnull: nonNull ? hlCols.join(',') : undefined, where: where || undefined, remote: remote ? 'true' : undefined })
      .then((r) => !off && setRes(r)).catch((e) => !off && setErr(e.message))
    return () => { off = true }
  }, [n, tick, nonNull, remote, JSON.stringify(visible)])

  const colMeta = Object.fromEntries(t.columns.map((c) => [c.column, c]))
  const gridCols = (res?.columns || []).map((c, i) => ({
    key: String(i), label: <span className={hl.has(c) ? 'hl-text' : ''} title={res.types[i]}>{c}</span>,
    render: (r) => <Cell v={r[i]} masked={workshop && !unmask && isPII(colMeta[c])} />, value: (r) => r[i],
  }))

  return (
    <>
      <div className="subbar">
        <div className="seg">
          {[10, 20, 50].map((x) => <button key={x} className={n === x ? 'active' : ''} onClick={() => setN(x)}>{x}</button>)}
        </div>
        <button className="btn" onClick={() => setTick((x) => x + 1)} title="Draw another random sample">↻ Resample</button>
        <ColumnPicker items={items} value={view} onChange={setView} presets={[
          ...(hlCols.length ? [{ label: 'Matched only', apply: (its) => ({ order: [...hlCols, ...its.map((i) => i.key).filter((k) => !hlCols.includes(k))], hidden: its.map((i) => i.key).filter((k) => !hlCols.includes(k)) }) },
                              { label: 'Matched first', apply: (its) => ({ order: [...hlCols, ...its.map((i) => i.key).filter((k) => !hlCols.includes(k))], hidden: [] }) }] : []),
        ]} />
        {hlCols.length > 0 && <label className="check"><input type="checkbox" checked={nonNull} onChange={(e) => setNonNull(e.target.checked)} /> non-null in matched</label>}
        <form className="where" onSubmit={(e) => { e.preventDefault(); setTick((x) => x + 1) }}>
          <input placeholder="filter, e.g. status_code = 'CXL'" value={where} onChange={(e) => setWhere(e.target.value)} />
        </form>
        {workshop && <label className="check"><input type="checkbox" checked={unmask} onChange={(e) => setUnmask(e.target.checked)} /> show PII</label>}
      </div>
      {err && <div className="error">{err}</div>}
      {res && <DataGrid columns={gridCols} rows={res.rows} empty="No rows match" dense />}
      {res && <div className="muted small pad-x">{res.rows.length} random rows of {fmt.n(t.row_count)}{sourceNote(res) ? ` · ${sourceNote(res)}` : ''}{workshop && !unmask ? ' · PII columns masked' : ''}</div>}
    </>
  )
}

/* ------------------------------------------------------------------ profile overview */
function ProfilePanel({ t, onOpenColumn, onReload }) {
  const [live, setLive] = useState(null)
  const [busy, setBusy] = useState(false)
  const tp = t.table_profile
  const cols = live ? live.columns.map((p) => ({ column: p.column_name, type: p.data_type, profile: p })) : t.columns
  const has = live || tp

  const runLive = async () => {
    setBusy(true)
    try { setLive(await api.profile(t.schema, t.table, { live: true })) } finally { setBusy(false) }
  }
  if (!has && t.kind === 'remote') {
    return (
      <div className="notice pad">
        <b>Not profiled yet.</b> The rows are in Databricks: profile the table on the SQL warehouse
        (or <code>bearings profile -t {t.schema}.{t.table}</code>).
        <div style={{ marginTop: 8 }}><RemoteProfileButton schema={t.schema} table={t.table} profiled={false} onDone={onReload} /></div>
      </div>
    )
  }
  if (!has) {
    return (
      <div className="notice pad">
        <b>Not profiled yet.</b> Run <code>bearings profile -t {t.schema}.{t.table}</code> to store it, or
        <button className="btn" onClick={runLive} disabled={busy}>{busy ? 'Profiling…' : 'Compute live now'}</button>
        <div className="muted small">Live results aren't saved. Large tables can take a while.</div>
      </div>
    )
  }
  const withP = cols.filter((c) => c.profile)
  const flagCount = (f) => withP.filter((c) => c.profile.flags?.includes(f)).length
  const keys = live ? live.table.candidate_keys : tp.candidate_keys
  const tiles = [
    ['Rows', fmt.n(live ? live.table.row_count : tp.row_count)],
    ['Columns', withP.length],
    ['Candidate keys', keys?.length ? keys.join(', ') : '—'],
    ['Avg null %', fmt.pct(withP.reduce((a, c) => a + c.profile.null_pct, 0) / (withP.length || 1))],
    ['All-null / constant', `${flagCount('all_null')} / ${flagCount('constant')}`],
    ['Possible PII', withP.filter((c) => c.profile.flags?.some((f) => f.startsWith('pii_'))).length],
  ]
  const gridCols = [
    { key: 'column', label: 'Column', render: (c) => <span className="mono">{c.column}</span>, value: (c) => c.column },
    { key: 'type', label: 'Type', render: (c) => <span className="mono muted">{c.type}</span> },
    { key: 'null', label: 'Null %', render: (c) => <span className="numbar"><Bar pct={c.profile.null_pct} tone={c.profile.null_pct >= 50 ? 'warn' : 'accent'} width={90} />{fmt.pct(c.profile.null_pct)}</span>, value: (c) => c.profile.null_pct },
    { key: 'dist', label: 'Distinct %', render: (c) => <span className="numbar"><Bar pct={c.profile.distinct_pct} tone="good" width={90} />{fmt.pct(c.profile.distinct_pct)}</span>, value: (c) => c.profile.distinct_pct },
    { key: 'dc', label: 'Distinct', render: (c) => fmt.n(c.profile.distinct_count), value: (c) => c.profile.distinct_count, align: 'right' },
    { key: 'range', label: 'Min → Max', render: (c) => <span className="mono small">{c.profile.min_val ?? ''} → {c.profile.max_val ?? ''}</span> },
    { key: 'pat', label: 'Top pattern', render: (c) => c.profile.patterns?.[0] ? <span className="mono small">{c.profile.patterns[0].p}</span> : '' },
    { key: 'flags', label: 'Flags', render: (c) => <Flags flags={c.profile.flags} />, value: (c) => (c.profile.flags || []).length },
  ]
  return (
    <>
      <div className="tiles">
        {tiles.map(([k, v]) => <div key={k} className="tile"><div className="muted small">{k}</div><div className="tile-v">{v}</div></div>)}
      </div>
      <div className="muted small pad-x">
        {live ? `Computed live in ${live.elapsed_ms} ms (not saved)` : `Profiled ${tp.profiled_at?.slice(0, 16)}${tp.sampled_rows ? ` on a ${fmt.n(tp.sampled_rows)}-row sample` : ''}`} · click a column for full detail
      </div>
      <DataGrid columns={gridCols} rows={withP} rowKey={(c) => c.column} onRowClick={(c) => onOpenColumn(c.column)} />
    </>
  )
}

/* ------------------------------------------------------------------ relationships */
function RelPanel({ t, allTables, onOpenTable }) {
  const [left, setLeft] = useState(t.columns[0]?.column)
  const [other, setOther] = useState('')
  const [otherCols, setOtherCols] = useState([])
  const [right, setRight] = useState('')
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!other) return
    const [s, tb] = other.split('.')
    api.table(s, tb).then((r) => { setOtherCols(r.columns.map((c) => c.column)); setRight(r.columns[0]?.column || '') })
  }, [other])

  const check = async () => {
    setErr(null); setRes(null)
    try { setRes(await api.overlap(`${t.schema}.${t.table}.${left}`, `${other}.${right}`)) } catch (e) { setErr(e.message) }
  }
  const rows = t.relationships.map((r) => ({ ...r, dir: r.from_table === t.table && r.from_schema === t.schema ? 'out' : 'in' }))
  return (
    <>
      <DataGrid rows={rows} empty="No relationships discovered for this table (run bearings relate)" columns={[
        { key: 'dir', label: '', render: (r) => r.dir === 'out' ? '→' : '←', width: 30 },
        { key: 'from', label: 'From (FK)', render: (r) => <span className="mono">{r.from_table}.{r.from_column}</span>, value: (r) => r.from_table + r.from_column },
        { key: 'to', label: 'To (key)', render: (r) => (
          <button className="link mono" onClick={() => r.dir === 'out' ? onOpenTable(r.to_schema, r.to_table, r.to_column) : onOpenTable(r.from_schema, r.from_table, r.from_column)}>
            {r.to_table}.{r.to_column}</button>), value: (r) => r.to_table },
        { key: 'overlap_pct', label: 'Overlap', render: (r) => <span className="numbar"><Bar pct={r.overlap_pct} tone="good" width={60} />{fmt.pct(r.overlap_pct)}</span>, align: 'right' },
        { key: 'name_score', label: 'Name sim.', render: (r) => r.name_score.toFixed(2), align: 'right' },
        { key: 'confidence', label: 'Confidence', render: (r) => r.confidence.toFixed(2), align: 'right' },
      ]} />
      <div className="card">
        <h4>Check a join manually</h4>
        <div className="subbar">
          <select value={left} onChange={(e) => setLeft(e.target.value)}>{t.columns.map((c) => <option key={c.column}>{c.column}</option>)}</select>
          <span>→</span>
          <select value={other} onChange={(e) => setOther(e.target.value)}>
            <option value="">table…</option>
            {allTables.map((x) => <option key={`${x.schema}.${x.table}`} value={`${x.schema}.${x.table}`}>{x.schema}.{x.table}</option>)}
          </select>
          <select value={right} onChange={(e) => setRight(e.target.value)} disabled={!other}>{otherCols.map((c) => <option key={c}>{c}</option>)}</select>
          <button className="btn primary" disabled={!other || !right} onClick={check}>Check overlap</button>
        </div>
        {err && <div className="error">{err}</div>}
        {res && (
          <div className="overlap">
            <div><b>{fmt.pct(res.left_in_right_pct)}</b> of {fmt.n(res.left_distinct)} distinct <span className="mono">{left}</span> values exist in <span className="mono">{right}</span></div>
            <div><b>{fmt.pct(res.right_in_left_pct)}</b> of {fmt.n(res.right_distinct)} distinct <span className="mono">{right}</span> values exist in <span className="mono">{left}</span></div>
            {res.left_orphans.length > 0 && <div className="muted small">Orphans (in {left}, not in {right}): <span className="mono">{res.left_orphans.join(', ')}</span></div>}
          </div>
        )}
      </div>
    </>
  )
}
