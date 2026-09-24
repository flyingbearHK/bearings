import React, { useEffect, useMemo, useState } from 'react'
import { api, copy, fmt, saveFile } from '../api.js'
import { Bar } from './Charts.jsx'
import DataGrid, { Hl } from './DataGrid.jsx'

const STATUS = { same: 'good', 'case/space': 'accent', 'only left': 'warn', 'only right': 'warn' }
const refOf = (x) => `${x.schema}.${x.table}.${x.column}`

/** All code lists (low-cardinality columns) in scope: their values, and a value-by-value comparison with another list –
 *  typically the same concept in another source system (value mapping / reference data). */
export default function CodeListsView({ scope, onOpenTable }) {
  const [lists, setLists] = useState(null)
  const [f, setF] = useState('')
  const [sel, setSel] = useState(null)
  const [vals, setVals] = useState(null)
  const [other, setOther] = useState('')
  const [cmp, setCmp] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => { api.codeLists(scope).then(setLists).catch((e) => setErr(e.message)) }, [scope])
  useEffect(() => {
    if (!sel) return
    setVals(null); setCmp(null); setOther('')
    api.codeValues(sel, scope).then((r) => { setVals(r); if (r.similar?.[0]) setOther(refOf(r.similar[0])) }).catch((e) => setErr(e.message))
  }, [sel]) // eslint-disable-line
  useEffect(() => {
    if (!sel || !other) return setCmp(null)
    api.codeCompare(sel, other).then(setCmp).catch((e) => setErr(e.message))
  }, [sel, other])

  const shown = useMemo(() => (lists || []).filter((x) => !f || `${refOf(x)} ${(x.top || []).join(' ')}`.toLowerCase().includes(f.toLowerCase())), [lists, f])
  if (err && !lists) return <div className="error">{err}</div>
  if (!lists) return <div className="muted pad">Loading…</div>
  const total = vals?.values?.reduce((a, x) => a + x.n, 0) || 0
  const cur = lists.find((x) => refOf(x) === sel)
  return (
    <div className="page codes-page">
      <aside className="codes-side">
        <div className="subbar">
          <input className="grow" placeholder="Filter code lists — table, column or value…" value={f} onChange={(e) => setF(e.target.value)} />
        </div>
        <div className="muted small pad-x">{shown.length} code lists · columns with 2–200 values, captured by <code>bearings insights</code></div>
        <ul className="list codes-list">
          {shown.length === 0 && <li className="muted small pad">No code lists yet — run <code>bearings insights</code>.</li>}
          {shown.map((x) => (
            <li key={refOf(x)} className={sel === refOf(x) ? 'active' : ''} onClick={() => setSel(refOf(x))}>
              <div className="li-main"><span className="mono"><span className="muted">{x.schema}.{x.table}.</span><b><Hl text={x.column} term={f} /></b></span>
                <span className="muted small">{x.values}</span></div>
              <div className="li-sub muted small mono"><Hl text={(x.top || []).join(' · ')} term={f} /></div>
            </li>
          ))}
        </ul>
      </aside>
      <section className="codes-main">
        {!sel && <div className="muted pad">Pick a code list to see its values and compare it with another list (e.g. the same code in another system).</div>}
        {sel && (
          <>
            <div className="subbar">
              <h3 className="mono codes-title">{sel}</h3>
              {cur && <button className="link small" onClick={() => onOpenTable(cur.schema, cur.table, cur.column)}>open table</button>}
              <span className="spacer" />
              {vals && <button className="btn" onClick={() => copy(vals.values.map((x) => x.value).join('\n'), 'Values copied')}>Copy values</button>}
              {vals && <button className="btn" onClick={() => saveFile('value,rows\n' + vals.values.map((x) => `"${String(x.value).replace(/"/g, '""')}",${x.n}`).join('\n'), `${sel}.csv`, 'text/csv')}>⤓ CSV</button>}
            </div>
            <div className="codes-grid">
              <div>
                <h4>Values {vals && <span className="muted small">{vals.values.length} values · {fmt.n(total)} rows{cur?.on_sample ? ' (sample)' : ''}</span>}</h4>
                {vals && <DataGrid dense id="codeValues" rows={vals.values} columns={[
                  { key: 'value', label: 'Value', render: (x) => <span className="mono">{x.value}</span> },
                  { key: 'n', label: 'Rows', align: 'right', render: (x) => <span className="numbar"><Bar pct={total ? 100 * x.n / total : 0} width={60} />{fmt.n(x.n)}</span> },
                  { key: 'pct', label: '%', align: 'right', value: (x) => x.n, render: (x) => fmt.pct(total ? 100 * x.n / total : 0) },
                ]} />}
              </div>
              <div>
                <h4>Compare with</h4>
                <select className="codes-other" value={other} onChange={(e) => setOther(e.target.value)}>
                  <option value="">another code list…</option>
                  {vals?.similar?.length > 0 && <optgroup label="Similar values">
                    {vals.similar.map((x) => <option key={refOf(x)} value={refOf(x)}>{refOf(x)} — {Math.round(x.containment * 100)}% shared</option>)}
                  </optgroup>}
                  <optgroup label="All code lists">{lists.filter((x) => refOf(x) !== sel).map((x) => <option key={refOf(x)} value={refOf(x)}>{refOf(x)}</option>)}</optgroup>
                </select>
                {cmp && (
                  <>
                    <div className="small codes-sum">
                      <span className="chip good">{cmp.matched} in both</span> <span className="chip warn">{cmp.only_left} only left</span> <span className="chip warn">{cmp.only_right} only right</span>
                      <span className="spacer" />
                      <button className="link small" onClick={() => saveFile('left,left_rows,right,right_rows,status,suggestion\n' + cmp.rows.map((r) =>
                        [r.left, r.left_n, r.right, r.right_n, r.status, r.suggestion].map((v) => (v == null ? '' : `"${String(v).replace(/"/g, '""')}"`)).join(',')).join('\n'),
                        `mapping_${sel}_${other}.csv`, 'text/csv')} title="A starting point for the value mapping">⤓ mapping CSV</button>
                    </div>
                    <DataGrid dense id="codeCompare" rows={cmp.rows} columns={[
                      { key: 'left', label: sel.split('.').slice(-1)[0], render: (r) => r.left == null ? <span className="muted">—</span> : <span className="mono">{r.left}</span> },
                      { key: 'left_n', label: 'Rows', align: 'right', render: (r) => fmt.n(r.left_n) },
                      { key: 'right', label: other.split('.').slice(-1)[0], render: (r) => r.right == null ? <span className="muted">—</span> : <span className="mono">{r.right}</span> },
                      { key: 'right_n', label: 'Rows', align: 'right', render: (r) => fmt.n(r.right_n) },
                      { key: 'status', label: 'Status', render: (r) => <span className={`chip ${STATUS[r.status]}`}>{r.status}</span> },
                      { key: 'suggestion', label: 'Maybe', render: (r) => r.suggestion ? <span className="mono small" title="Closest unmatched value on the other side">≈ {r.suggestion}</span> : '' },
                    ]} />
                  </>
                )}
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
