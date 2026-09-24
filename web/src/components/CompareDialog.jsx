import React, { useEffect, useState } from 'react'
import { api, fmt } from '../api.js'
import DataGrid, { Cell } from './DataGrid.jsx'

/** Compare the attributes of records linked by a key (e.g. crm.customer.PmsGuestCode → pms.guest.guest_code). */
export default function CompareDialog({ left, right, onClose, onOpenSql }) {
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pairs, setPairs] = useState(null)
  const [add, setAdd] = useState(['', ''])
  const [diff, setDiff] = useState(null)

  const run = async (p) => {
    setBusy(true); setErr(null); setDiff(null)
    try { const r = await api.compare({ left, right, pairs: p || undefined }); setRes(r); setPairs(r.pairs.map((x) => [x.left, x.right])) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  useEffect(() => { run(null) }, [left, right]) // eslint-disable-line
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  const showDiff = async (p) => {
    if (diff?.key === p.left + p.right) return setDiff(null)
    setDiff({ key: p.left + p.right, loading: true })
    try { setDiff({ key: p.left + p.right, ...(await api.compareDiffs({ left, right, left_column: p.left, right_column: p.right, limit: 200 })) }) } catch (e) { setDiff({ key: p.left + p.right, error: e.message }) }
  }
  const lt = left.split('.').slice(0, 2).join('.'), rt = right.split('.').slice(0, 2).join('.')
  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal cmp-modal" role="dialog" aria-label="Compare attributes">
        <div className="modal-head">
          <h3>Compare attributes</h3>
          <span className="muted small mono">{left} = {right}</span>
          <span className="spacer" />
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {err && <div className="error">{err}</div>}
          {busy && <div className="muted">Comparing…</div>}
          {res && (
            <>
              <div className="small">
                <b>{fmt.n(res.joined_rows)}</b> joined rows ({fmt.n(res.joined_keys)} keys) · {lt} {fmt.n(res.left_rows)} rows · {rt} {fmt.n(res.right_rows)} rows
                <span className="muted"> · values compared after normalising (case, spaces, date formats, placeholders)</span>
              </div>
              <DataGrid dense id="cmpPairs" rows={res.pairs} rowKey={(p) => p.left + '|' + p.right} onRowClick={showDiff} columns={[
                { key: 'left', label: lt, render: (p) => <span className="mono">{p.left}</span> },
                { key: 'right', label: rt, render: (p) => <span className="mono">{p.right}</span> },
                { key: 'agree_pct', label: 'Agree', align: 'right', render: (p) => p.agree_pct == null ? '' : <b className={p.agree_pct < 95 ? 'warn-text' : ''}>{p.agree_pct}%</b> },
                { key: 'differ', label: 'Differ', align: 'right', render: (p) => p.differ ? <span className="warn-text">{fmt.n(p.differ)}</span> : '0' },
                { key: 'only_left', label: `Only in ${lt.split('.')[1]}`, align: 'right', render: (p) => fmt.n(p.only_left) },
                { key: 'only_right', label: `Only in ${rt.split('.')[1]}`, align: 'right', render: (p) => fmt.n(p.only_right) },
                { key: 'fill', label: 'Filled (left / right)', render: (p) => `${fmt.pct(p.left_filled_pct)} / ${fmt.pct(p.right_filled_pct)}` },
                { key: 'note', label: '', render: (p) => p.equal < p.equal_normalised ? <span className="chip accent" title={`${fmt.n(p.equal_normalised - p.equal)} values only match after normalising`}>format differs</span> : '' },
              ]} />
              <div className="muted small">Click a pair for the rows that differ. Left unpaired: {res.unpaired_left.join(', ') || '—'} · right unpaired: {res.unpaired_right.join(', ') || '—'}</div>
              <div className="subbar">
                <span className="small">Add a pair</span>
                <select value={add[0]} onChange={(e) => setAdd([e.target.value, add[1]])}><option value="">{lt}…</option>{res.left_columns.map((c) => <option key={c}>{c}</option>)}</select>
                <span>=</span>
                <select value={add[1]} onChange={(e) => setAdd([add[0], e.target.value])}><option value="">{rt}…</option>{res.right_columns.map((c) => <option key={c}>{c}</option>)}</select>
                <button className="btn" disabled={!add[0] || !add[1]} onClick={() => { const p = [...(pairs || []), add]; setAdd(['', '']); run(p) }}>Compare</button>
              </div>
              {diff && (
                <div className="exc">
                  {diff.loading && <div className="muted small">Loading…</div>}
                  {diff.error && <div className="error">{diff.error}</div>}
                  {diff.rows && (
                    <>
                      <div className="subbar"><span className="muted small">{diff.rows.length} rows where the values differ (or one side is empty)</span><span className="spacer" />
                        {onOpenSql && <button className="btn" onClick={() => { onClose(); onOpenSql(diff.sql) }}>Open in SQL</button>}</div>
                      <DataGrid dense id="cmpDiff" rows={diff.rows} columns={diff.columns.map((c, i) => ({ key: String(i), label: c, value: (r) => r[i], render: (r) => <Cell v={r[i]} /> }))} />
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
