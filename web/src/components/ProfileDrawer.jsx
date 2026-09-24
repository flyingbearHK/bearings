import React, { useEffect, useState } from 'react'
import { api, fmt } from '../api.js'
import { Flags, FreqList, Histogram } from './Charts.jsx'

/** Side drawer: full profile of one column + relationships + annotation editor. */
export default function ProfileDrawer({ target, onClose, onValueSearch, onOpenTable, onSaved }) {
  const { schema, table, column } = target
  const [p, setP] = useState(null)
  const [live, setLive] = useState(false)
  const [err, setErr] = useState(null)
  const [rels, setRels] = useState([])
  const [ann, setAnn] = useState({ tags: '', cdm_entity: '', cdm_attribute: '', notes: '' })
  const [saved, setSaved] = useState(null)
  const [byCols, setByCols] = useState([])
  const [by, setBy] = useState('')
  const [bd, setBd] = useState(null)

  useEffect(() => {
    let off = false
    setP(null); setErr(null); setSaved(null)
    api.profile(schema, table, { column }).then((r) => {
      if (off) return
      setP(r.columns[0]); setLive(!r.stored)
    }).catch((e) => !off && setErr(e.message))
    api.table(schema, table).then((t) => {
      if (off) return
      const c = t.columns.find((x) => x.column === column)
      const a = c?.annotation || {}
      setAnn({ tags: a.tags || '', cdm_entity: a.cdm_entity || '', cdm_attribute: a.cdm_attribute || '', notes: a.notes || '' })
      setByCols(t.columns.filter((x) => x.column !== column && x.profile && x.profile.distinct_count >= 2 && x.profile.distinct_count <= 50).map((x) => x.column))
      setBy(''); setBd(null)
      setRels(t.relationships.filter((r) =>
        (r.from_table === table && r.from_column === column) || (r.to_table === table && r.to_column === column)))
    })
    return () => { off = true }
  }, [schema, table, column])

  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const save = async () => {
    await api.saveAnnotation({ schema, table, column, ...ann })
    setSaved(new Date().toLocaleTimeString())
    onSaved?.()
  }

  const nn = p ? p.row_count - p.null_count : 0
  const stats = p ? [
    ['Rows', fmt.n(p.row_count)],
    ['Nulls', `${fmt.n(p.null_count)} (${fmt.pct(p.null_pct)})`],
    ['Distinct', `${fmt.n(p.distinct_count)} (${fmt.pct(p.distinct_pct)})`],
    p.blank_count != null && ['Blank strings', fmt.n(p.blank_count)],
    p.placeholder_count > 0 && ['Placeholder values', `${fmt.n(p.placeholder_count)} — ${(p.placeholder_values || []).map((x) => `${x.v === '' ? "''" : x.v} ×${fmt.n(x.n)}`).join(', ')}`],
    p.effective_null_pct != null && p.effective_null_pct - p.null_pct >= 0.05 && ['Effectively empty', `${fmt.pct(p.effective_null_pct)} (nulls + blanks + placeholders)`],
    p.type_hint && ['Type hint', `${p.type_hint.type} — ${(p.type_hint.share * 100).toFixed(1)}% of ${fmt.n(p.type_hint.checked)} values parse`
      + (p.type_hint.formats ? ` (${Object.entries(p.type_hint.formats).map(([f, s]) => `${f} ${Math.round(s * 100)}%`).join(', ')})` : '')],
    p.leading_zero_count > 0 && ['Leading zeros', `${fmt.n(p.leading_zero_count)} values (keep as text)`],
    p.outlier_low != null && ['Typical range', `${fmt.n(p.outlier_low)} … ${fmt.n(p.outlier_high)} (3 × IQR)`],
    p.outlier_count > 0 && ['Far-out values', `${fmt.n(p.outlier_count)} — e.g. ${(p.outlier_values || []).slice(0, 3).map((x) => fmt.n(x.v)).join(', ')}`],
    p.negative_count > 0 && ['Negative values', fmt.n(p.negative_count)],
    ['Min', p.min_val], ['Max', p.max_val],
    p.mean != null && ['Mean', Number(p.mean).toLocaleString(undefined, { maximumFractionDigits: 4 })],
    p.stddev != null && ['Std dev', Number(p.stddev).toLocaleString(undefined, { maximumFractionDigits: 4 })],
    p.p50 != null && ['P25 / P50 / P75', `${p.p25} / ${p.p50} / ${p.p75}`],
    p.min_len != null && ['Length min / avg / max', `${p.min_len} / ${p.avg_len} / ${p.max_len}`],
  ].filter(Boolean) : []

  return (
    <aside className="drawer" role="dialog" aria-label={`Profile of ${column}`}>
      <div className="drawer-head">
        <div>
          <div className="muted small">{schema}.{table}</div>
          <h2 className="mono">{column}</h2>
          <div className="muted small">{p?.data_type}{live && p ? ' · computed live (not saved – run bearings profile)' : p?.profiled_at ? ` · profiled ${p.profiled_at.slice(0, 16)}` : ''}</div>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close (Esc)">✕</button>
      </div>
      <div className="drawer-body">
        {err && <div className="error">{err}</div>}
        {!p && !err && <div className="muted">Profiling…</div>}
        {p && (
          <>
            <Flags flags={p.flags} />
            <dl className="stats">
              {stats.map(([k, v]) => (<React.Fragment key={k}><dt>{k}</dt><dd className="mono">{v ?? '—'}</dd></React.Fragment>))}
            </dl>
            {p.histogram?.length > 0 && (<><h4>Distribution</h4><Histogram bins={p.histogram} /></>)}
            <h4>Top values {p.top_values?.length === 0 && nn > 0 && <span className="muted small">(all values unique)</span>}</h4>
            <FreqList items={p.top_values} total={p.row_count} onPick={onValueSearch} mono />
            {p.patterns?.length > 0 && (<><h4>Patterns <span className="muted small">A=upper a=lower 9=digit</span></h4>
              <FreqList items={p.patterns} total={nn} labelKey="p" mono /></>)}
          </>
        )}
        {byCols.length > 0 && (
          <>
            <h4>Break down by <select value={by} onChange={async (e) => {
              const v = e.target.value; setBy(v); setBd(null)
              if (v) { try { setBd(await api.breakdown(schema, table, column, v)) } catch (er) { setBd({ error: er.message }) } }
            }}><option value="">another column…</option>{byCols.map((c) => <option key={c}>{c}</option>)}</select></h4>
            {bd?.error && <div className="error">{bd.error}</div>}
            {bd?.rows && (
              <table className="grid ins-time small"><thead><tr><th>{by}</th><th className="r">Rows</th><th className="r">Filled %</th><th className="r">Distinct</th><th>Most common</th></tr></thead>
                <tbody>{bd.rows.map((x, i) => <tr key={i}><td className="mono">{x[0] ?? '(empty)'}</td><td className="r">{fmt.n(x[1])}</td><td className="r">{fmt.pct(x[3])}</td>
                  <td className="r">{fmt.n(x[4])}</td><td className="mono">{x[5] ?? ''}</td></tr>)}</tbody></table>
            )}
          </>
        )}
        <h4>Relationships</h4>
        {rels.length === 0 && <div className="muted small">None discovered (run <code>bearings relate</code>, or check a pair in the Relationships tab).</div>}
        <ul className="rel-list">
          {rels.map((r, i) => {
            const out = r.from_table === table && r.from_column === column
            return (
              <li key={i}>
                {out ? '→ references ' : '← referenced by '}
                <button className="link mono" onClick={() => onOpenTable(out ? r.to_schema : r.from_schema, out ? r.to_table : r.from_table, out ? r.to_column : r.from_column)}>
                  {out ? `${r.to_table}.${r.to_column}` : `${r.from_table}.${r.from_column}`}
                </button>
                <span className="muted small"> {r.overlap_pct}% overlap</span>
              </li>
            )
          })}
        </ul>
        <h4>Annotation</h4>
        <div className="form">
          <label>Tags <input value={ann.tags} onChange={(e) => setAnn({ ...ann, tags: e.target.value })} placeholder="e.g. PII, key, deprecated" /></label>
          <div className="row2">
            <label>CDM entity <input value={ann.cdm_entity} onChange={(e) => setAnn({ ...ann, cdm_entity: e.target.value })} placeholder="e.g. Party" /></label>
            <label>CDM attribute <input value={ann.cdm_attribute} onChange={(e) => setAnn({ ...ann, cdm_attribute: e.target.value })} placeholder="e.g. EmailAddress" /></label>
          </div>
          <label>Notes <textarea rows={3} value={ann.notes} onChange={(e) => setAnn({ ...ann, notes: e.target.value })} /></label>
          <div className="actions"><button className="btn primary" onClick={save}>Save annotation</button>{saved && <span className="muted small">Saved {saved}</span>}</div>
        </div>
      </div>
    </aside>
  )
}
