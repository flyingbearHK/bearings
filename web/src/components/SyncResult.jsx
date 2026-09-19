import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const CHANGE_LABEL = {
  table_added: ['table added', 'tables added'], table_dropped: ['table dropped', 'tables dropped'], table_restored: ['table restored', 'tables restored'],
  column_added: ['column added', 'columns added'], column_dropped: ['column dropped', 'columns dropped'], type_changed: ['type change', 'type changes'],
  comment_changed: ['comment change', 'comment changes'], table_comment_changed: ['table comment change', 'table comment changes'],
}
const changeSummary = (summary) =>
  Object.entries(summary || {}).map(([k, v]) => `${v} ${(CHANGE_LABEL[k] || [k, k])[v === 1 ? 0 : 1]}`).join(', ')

/** Outcome of a remote metadata sync: what changed per schema, and annotations left pointing at vanished columns. */
export default function SyncResult({ job, onClose, onChanged }) {
  const [orphans, setOrphans] = useState([])
  const [msg, setMsg] = useState(null)
  const done = job.status !== 'running'
  const load = () => api.orphans(job.aliases.join(',')).then(setOrphans).catch(() => {})
  useEffect(() => { if (done && !job.dry_run) load() }, [done]) // eslint-disable-line
  const remap = (o, to) => api.remap({ schema: o.schema, table: o.table, column: o.column, new_column: to })
    .then(() => { setMsg(`Moved ${o.table}.${o.column} → ${to}`); load(); onChanged?.() }).catch((e) => setMsg(e.message))

  return (
    <div className="sync-result">
      <div className="sync-head">
        <b>{done ? (job.status === 'failed' ? 'Sync failed' : 'Sync finished') : `Syncing ${job.current || job.aliases.join(', ')}…`}</b>
        {done && <button className="link small" onClick={onClose}>close</button>}
      </div>
      {job.results.map((r) => (
        <div key={r.alias} className="sync-alias">
          <div><span className="mono">{r.alias}</span>{' '}
            <span className="muted small">{r.first_sync ? `${r.tables} tables (first sync)` : r.changes.length ? changeSummary(r.summary) : 'no changes'}</span>
          </div>
          {r.changes.length > 0 && !r.first_sync && (
            <ul className="change-list">
              {r.changes.slice(0, 25).map((c, i) => (
                <li key={i} className={`chg ${c.change}`}>
                  <span className="chg-kind">{c.change.replace(/_/g, ' ')}</span>{' '}
                  <span className="mono">{c.table_name}{c.column_name ? `.${c.column_name}` : ''}</span>
                  {(c.old_value || c.new_value) && (
                    <span className="muted small"> {c.old_value && c.new_value ? `${String(c.old_value).slice(0, 40)} → ${String(c.new_value).slice(0, 40)}` : (c.new_value || c.old_value)}</span>
                  )}
                </li>
              ))}
              {r.changes.length > 25 && <li className="muted small">… {r.changes.length - 25} more</li>}
            </ul>
          )}
        </div>
      ))}
      {job.errors.map((e) => <div key={e.alias} className="error small"><span className="mono">{e.alias}</span>: {e.error}</div>)}
      {orphans.length > 0 && (
        <div className="orphans">
          <div className="small"><b>{orphans.length} annotation{orphans.length > 1 ? 's' : ''}</b> now {orphans.length > 1 ? 'point' : 'points'} at something that no longer exists (kept, not deleted):</div>
          <ul className="change-list">
            {orphans.map((o) => (
              <li key={`${o.schema}.${o.table}.${o.column}`}>
                <span className="mono">{o.table}{o.column ? `.${o.column}` : ''}</span> <span className="muted small">{o.reason}</span>
                {o.suggestions.map((s) => (
                  <button key={s.column} className="link small" title={`Move tags / CDM mapping / notes to ${s.column}`} onClick={() => remap(o, s.column)}>→ {s.column}</button>
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}
      {msg && <div className="muted small">{msg}</div>}
    </div>
  )
}
