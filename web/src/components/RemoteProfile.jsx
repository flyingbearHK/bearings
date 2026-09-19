import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

/** Start a remote-profiling job and poll it. body: {tables?, aliases?, only_new?, only_stale?} */
export function useRemoteJob(onDone) {
  const [job, setJob] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    if (!job || job.status !== 'running') return
    const h = setTimeout(() => api.remoteJob(job.id).then((j) => {
      setJob(j)
      if (j.status !== 'running') onDone?.(j)
    }).catch((e) => setErr(e.message)), 900)
    return () => clearTimeout(h)
  }, [job]) // eslint-disable-line
  const start = (body) => { setErr(null); api.remoteProfile(body).then(setJob).catch((e) => setErr(e.message)) }
  return { job, err, start, running: job?.status === 'running', clear: () => setJob(null) }
}

/** "⚡ Profile on Databricks" for one remote table (runs on the SQL warehouse). */
export default function RemoteProfileButton({ schema, table, profiled, stale, onDone }) {
  const { job, err, start, running } = useRemoteJob(onDone)
  const label = running ? 'Profiling on Databricks…' : profiled ? (stale ? '⚡ Re-profile (source changed)' : '⚡ Re-profile') : '⚡ Profile on Databricks'
  return (
    <span className="remote-profile">
      <button className={`btn ${!profiled || stale ? 'primary' : ''}`} disabled={running}
        title="Runs on the SQL warehouse: exact counts over the whole table, a sample for top values and patterns, and key values for relationship discovery"
        onClick={() => start({ tables: [`${schema}.${table}`] })}>{label}</button>
      {job?.status === 'failed' && <span className="error small">{job.errors[0]?.error}</span>}
      {err && <span className="error small">{err}</span>}
    </span>
  )
}

/** Wakes the SQL warehouse when a remote table is opened and shows its state (a serverless warehouse
 *  that has been idle takes ~15-20 s to start; after that live queries are quick). */
export function WarehouseState({ connection }) {
  const [st, setSt] = useState(null)
  useEffect(() => {
    let off = false
    let timer
    const poll = () => api.remoteWarmStatus().then((r) => {
      if (off) return
      const s = r[connection]
      setSt(s)
      if (s?.state === 'warming') timer = setTimeout(poll, 2000)
    }).catch(() => {})
    api.remoteWarm(connection).then((r) => { if (!off) { setSt(r[connection]); if (r[connection]?.state === 'warming') timer = setTimeout(poll, 2000) } }).catch(() => {})
    return () => { off = true; clearTimeout(timer) }
  }, [connection])
  if (!st) return null
  if (st.state === 'warming') return <span className="wh warming" title="The first query after the warehouse has been idle waits for it to start">⏳ waking up the SQL warehouse…</span>
  if (st.state === 'ready') return <span className="wh ready" title="Live queries run on the SQL warehouse">● warehouse ready</span>
  if (st.state === 'error') return <span className="wh error" title={st.error}>● warehouse unavailable</span>
  return null
}

/** "⤓ Cache locally" / "↻ Re-cache": copy the table into DuckDB with the schema's cache setting
 *  (whole up to N rows, an N-row random sample of bigger tables), so queries run at local speed. */
export function PullButton({ schema, table, cached, onDone }) {
  const [job, setJob] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    if (!job || job.status !== 'running') return
    const h = setTimeout(() => api.remoteJob(job.id).then((j) => { setJob(j); if (j.status !== 'running') onDone?.(j) }).catch((e) => setErr(e.message)), 1000)
    return () => clearTimeout(h)
  }, [job]) // eslint-disable-line
  const running = job?.status === 'running'
  return (
    <span className="remote-profile">
      <button className="btn" disabled={running}
        title="Copies the table into the local database (whole up to the schema's cache size, a random sample of bigger tables): queries then run locally"
        onClick={() => { setErr(null); api.remotePull({ tables: [`${schema}.${table}`], cache: true }).then(setJob).catch((e) => setErr(e.message)) }}>
        {running ? 'Caching…' : cached ? '↻ Re-cache' : '⤓ Cache locally'}
      </button>
      {job?.status === 'failed' && <span className="error small">{job.errors[0]?.error}</span>}
      {err && <span className="error small">{err}</span>}
    </span>
  )
}
