import React, { useEffect, useRef, useState } from 'react'
import { ago, api, fmt } from '../api.js'
import SyncResult from './SyncResult.jsx'
import { useRemoteJob } from './RemoteProfile.jsx'

/** Header control: restrict the whole app (search, lists, lookups, relationships, annotations, exports) to schemas.
 *  Local schemas and attached Databricks schemas (grouped by connection → catalog) can be mixed; remote ones can be re-synced here. */
export default function ScopePicker({ schemas, scope, setScope, onSynced }) {
  const [open, setOpen] = useState(false)
  const [job, setJob] = useState(null)
  const [err, setErr] = useState(null)
  const [remoteInfo, setRemoteInfo] = useState({})
  const pj = useRemoteJob(() => { onSynced?.(); loadRemote() })
  const loadRemote = () => api.remote().then((r) => setRemoteInfo(Object.fromEntries(r.sources.map((x) => [x.alias, x])))).catch(() => {})
  const ref = useRef(null)
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  useEffect(() => { if (open) loadRemote() }, [open]) // eslint-disable-line
  // poll a running sync job
  useEffect(() => {
    if (!job || job.status !== 'running') return
    const h = setTimeout(() => api.remoteJob(job.id).then((j) => {
      setJob(j)
      if (j.status !== 'running') onSynced?.()
    }).catch((e) => setErr(e.message)), 700)
    return () => clearTimeout(h)
  }, [job]) // eslint-disable-line
  if (!schemas?.length) return null

  const sel = new Set(scope)
  const toggle = (s) => { const n = new Set(sel); n.has(s) ? n.delete(s) : n.add(s); setScope([...n].sort()) }
  const label = scope.length === 0 ? 'All schemas' : scope.join(', ')
  const local = schemas.filter((s) => s.kind !== 'remote')
  const remote = schemas.filter((s) => s.kind === 'remote')
  const groups = {}
  for (const s of remote) (groups[`${s.connection} · ${s.catalog}`] ||= { connection: s.connection, catalog: s.catalog, items: [] }).items.push(s)
  const running = job?.status === 'running'
  const sync = (body) => { setErr(null); api.remoteSync(body).then(setJob).catch((e) => setErr(e.message)) }

  const row = (s) => (
    <li key={s.schema}>
      <label>
        <input type="checkbox" checked={sel.has(s.schema)} onChange={() => toggle(s.schema)} />
        <span className="mono">{s.schema}</span>
        {s.kind === 'remote'
          ? <span className="muted small" title={`${s.catalog}.${s.remote_schema} · synced ${s.synced_at || 'never'}`}>
              {s.tables} tables{remoteInfo[s.schema] && ` · ${remoteInfo[s.schema].profiled} profiled${remoteInfo[s.schema].stale ? ` (${remoteInfo[s.schema].stale} stale)` : ''}`} · synced {ago(s.synced_at)}</span>
          : <span className="muted small">{s.tables} tables · {fmt.n(s.rows)} rows</span>}
      </label>
      <span className="row-actions">
        {s.kind === 'remote' && (
          <button className="icon-btn small" disabled={running} title={`Re-sync metadata of ${s.catalog}.${s.remote_schema} from Databricks`}
            onClick={() => sync({ aliases: [s.schema] })}>↻</button>
        )}
        {s.kind === 'remote' && (
          <button className="icon-btn small" disabled={pj.running}
            title="Profile tables not profiled yet, or changed since, on the SQL warehouse (uses warehouse time)"
            onClick={() => pj.start({ aliases: [s.schema], only_stale: true })}>⚡</button>
        )}
        <button className="link small" onClick={() => { setScope([s.schema]); setOpen(false) }}>only</button>
      </span>
    </li>
  )

  return (
    <div className="picker scope" ref={ref}>
      <button className={`btn scope-btn ${scope.length ? 'scoped' : ''}`} onClick={() => setOpen((o) => !o)}
        title="Limit search, lists, lookups, relationships, annotations and exports to these schemas">
        <span className="muted small">Schema</span> <b>{label}</b> {running && <span className="spin" title="Syncing…">↻</span>} ▾
      </button>
      {open && (
        <div className="picker-pop scope-pop">
          <ul className="picker-list">
            <li className={scope.length === 0 ? 'active' : ''}>
              <label><input type="radio" checked={scope.length === 0} onChange={() => { setScope([]); setOpen(false) }} /> All schemas</label>
            </li>
            {remote.length > 0 && local.length > 0 && <li className="group-head">Local <span className="muted small">DuckDB</span></li>}
            {local.map(row)}
            {Object.entries(groups).map(([k, g]) => (
              <React.Fragment key={k}>
                <li className="group-head">
                  <span><span className="cloud" title="Azure Databricks – metadata synced locally">☁</span> {g.connection} <span className="muted">· {g.catalog}</span></span>
                  <button className="link small" disabled={running} title={`Re-sync every attached schema from catalog ${g.catalog}`}
                    onClick={() => sync({ connection: g.connection, catalog: g.catalog })}>↻ sync all</button>
                </li>
                {g.items.map(row)}
              </React.Fragment>
            ))}
          </ul>
          {err && <div className="error small pad-x">{err}</div>}
          {job && <SyncResult job={job} onClose={() => setJob(null)} onChanged={onSynced} />}
          {(pj.job || pj.err) && (
            <div className="sync-result">
              <div className="sync-head">
                <b>{pj.running ? `Profiling on Databricks… ${pj.job.done || 0}/${pj.job.total}` : pj.job?.status === 'failed' ? 'Profiling failed' : pj.job ? `Profiled ${pj.job.results.length}/${pj.job.total} tables` : ''}</b>
                {!pj.running && <button className="link small" onClick={pj.clear}>close</button>}
              </div>
              {pj.running && pj.job.current && <div className="muted small mono">{pj.job.current}</div>}
              {pj.job?.errors.map((e) => <div key={e.alias} className="error small"><span className="mono">{e.alias}</span>: {e.error}</div>)}
              {pj.err && <div className="error small">{pj.err}</div>}
              {!pj.running && pj.job?.results.length > 0 && <div className="muted small">Next: find relationships with <code>bearings relate -s {pj.job.results[0].alias}</code></div>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
