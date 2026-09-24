import React, { useEffect, useMemo, useState } from 'react'
import { api, fmt, isPII, saveFile } from '../api.js'
import DataGrid, { Cell } from './DataGrid.jsx'

const ROLE_LABEL = { email: 'E-mail', phone: 'Phone', dob: 'Birth date', first_name: 'First name', last_name: 'Last name', name: 'Full / company name', postcode: 'Postcode' }
const RULE_LABEL = { not_null: 'not null', not_empty: 'not empty', unique: 'unique', unique_combo: 'unique together', in_list: 'allowed values',
  regex: 'format', non_negative: 'not negative', range: 'within range', not_in_future: 'not in the future', valid_date: 'valid date',
  foreign_key: 'exists in parent', filled_when: 'filled when…' }

/** Data quality of one table: outliers and negative amounts, near-duplicate records, and suggested DQ rules to export. */
export default function QualityPanel({ t, workshop, onOpenColumn }) {
  return (
    <div className="insights">
      <Outliers t={t} onOpenColumn={onOpenColumn} />
      <Duplicates t={t} workshop={workshop} />
      <Rules t={t} />
    </div>
  )
}

function Outliers({ t, onOpenColumn }) {
  const cols = t.columns.filter((c) => c.profile && (c.profile.outlier_count || c.profile.flags?.includes('negatives')))
  return (
    <section className="card">
      <h4>Outliers and negative values <span className="muted small">— far-out values (beyond 3 × IQR) and a few negatives in mostly positive numbers</span></h4>
      {!t.table_profile ? <div className="ins-body muted">Not profiled yet.</div>
        : cols.length === 0 ? <div className="ins-body muted">None found.</div> : (
          <table className="grid ins-time">
            <thead><tr><th>Column</th><th className="r">Far-out values</th><th>Typical range</th><th>Most extreme</th><th className="r">Negative values</th></tr></thead>
            <tbody>{cols.map((c) => { const p = c.profile; return (
              <tr key={c.column}>
                <td><button className="link mono" onClick={() => onOpenColumn(c.column)}>{c.column}</button></td>
                <td className="r">{p.outlier_count ? <span className="warn-text">{fmt.n(p.outlier_count)}</span> : 0}</td>
                <td className="mono small">{p.outlier_low != null ? `${fmt.n(p.outlier_low)} … ${fmt.n(p.outlier_high)}` : ''}</td>
                <td className="mono small">{(p.outlier_values || []).slice(0, 4).map((x) => fmt.n(x.v)).join(', ')}</td>
                <td className="r">{p.negative_count ? <span className={p.flags?.includes('negatives') ? 'warn-text' : ''}>{fmt.n(p.negative_count)}</span> : 0}</td>
              </tr>) })}</tbody>
          </table>)}
    </section>
  )
}

function Duplicates({ t, workshop }) {
  const [roles, setRoles] = useState(null)
  const [map, setMap] = useState({})
  const [threshold, setThreshold] = useState(0.9)
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  useEffect(() => {
    if (t.kind === 'remote') return
    api.duplicateRoles(t.schema, t.table).then((r) => { setRoles(r); setMap(r.roles) }).catch((e) => setErr(e.message))
  }, [t.schema, t.table, t.kind])
  const run = async () => {
    setBusy(true); setErr(null)
    try { setRes(await api.duplicates(t.schema, t.table, { columns: map, threshold, limit: 100 })) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const colMeta = Object.fromEntries(t.columns.map((c) => [c.column, c]))
  const half = res?.example_columns ? (res.example_columns.length - 1) / 2 : 0
  const rows = useMemo(() => (res?.examples || []).flatMap((r, i) => [
    { k: `${i}a`, pair: i + 1, score: r[0], side: 'a', vals: r.slice(1, 1 + half) },
    { k: `${i}b`, pair: i + 1, score: r[0], side: 'b', vals: r.slice(1 + half) },
  ]), [res, half])
  return (
    <section className="card">
      <h4>Possible duplicates <span className="muted small">— the same person or company captured twice with small differences</span></h4>
      {t.kind === 'remote' ? <div className="ins-body muted">Needs the rows: cache the table locally first.</div> : (
        <div className="ins-body">
          <div className="dup-roles">
            {(roles?.all_roles || []).map((r) => (
              <label key={r} className="small">{ROLE_LABEL[r] || r}
                <select value={map[r] || ''} onChange={(e) => setMap((m) => { const n = { ...m }; if (e.target.value) n[r] = e.target.value; else delete n[r]; return n })}>
                  <option value="">—</option>
                  {(roles?.columns || []).map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            ))}
            <label className="small">min similarity
              <select value={threshold} onChange={(e) => setThreshold(Number(e.target.value))}>{[0.8, 0.85, 0.9, 0.95, 1].map((x) => <option key={x} value={x}>{x}</option>)}</select></label>
            <button className="btn primary" disabled={busy || Object.keys(map).length < 2} onClick={run}>{busy ? 'Searching…' : 'Find duplicates'}</button>
          </div>
          {roles && Object.keys(roles.roles || {}).length < 2 && <div className="muted small">No name, e-mail, phone or birth-date columns recognised – pick at least two if this table holds people or companies.</div>}
          <div className="muted small">Rows sharing an e-mail, phone, name, or birth date + start of the last name are compared; e-mail, phone and dates must match exactly, names are compared with Jaro-Winkler similarity.</div>
          {err && <div className="error">{err}</div>}
          {res?.error && <div className="notice">{res.error}</div>}
          {res && !res.error && (
            <>
              <div className="ins-sentence">
                {res.pairs ? <><b>{fmt.n(res.pairs)}</b> likely duplicate pairs in <b>{fmt.n(res.groups)}</b> groups — {fmt.n(res.rows_in_groups)} of {fmt.n(res.rows)} rows
                  ({fmt.pct(100 * res.rows_in_groups / res.rows)}){res.largest_group > 2 ? `; the largest group has ${res.largest_group} rows` : ''}.</>
                  : 'No likely duplicates at this similarity.'}
                <span className="muted small"> · {res.elapsed_ms} ms</span>
              </div>
              {rows.length > 0 && <DataGrid dense id="dups" rows={rows} rowKey={(r) => r.k} rowClass={(r) => (r.pair % 2 ? 'pair-odd' : '')} columns={[
                { key: 'pair', label: '#', width: 40, render: (r) => r.side === 'a' ? r.pair : '' },
                { key: 'score', label: 'Similarity', align: 'right', render: (r) => r.side === 'a' ? r.score.toFixed(3) : '' },
                ...res.shown_columns.map((c, i) => ({ key: c, label: c, value: (r) => r.vals[i],
                  render: (r) => <Cell v={r.vals[i]} masked={workshop && isPII(colMeta[c])} /> })),
              ]} />}
            </>
          )}
        </div>
      )}
    </section>
  )
}

function Rules({ t }) {
  const [rules, setRules] = useState(null)
  const [off, setOff] = useState(new Set())
  const [err, setErr] = useState(null)
  useEffect(() => { api.dqRules({ tables: `${t.schema}.${t.table}` }).then(setRules).catch((e) => setErr(e.message)) }, [t.schema, t.table])
  const ids = (rules || []).filter((r) => !off.has(r.id)).map((r) => r.id)
  const exp = async (format) => {
    try { const { blob, name } = await api.dqExport({ tables: [`${t.schema}.${t.table}`], ids, format }); saveFile(blob, name) } catch (e) { setErr(e.message) }
  }
  const toggle = (id) => setOff((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  return (
    <section className="card">
      <h4>Suggested data-quality rules <span className="muted small">— from the profile, insights and relationships: untick what doesn't apply, then export</span></h4>
      {err && <div className="error">{err}</div>}
      {!rules ? <div className="ins-body muted">Loading…</div> : rules.length === 0 ? <div className="ins-body muted">No rules (profile the table first).</div> : (
        <>
          <div className="subbar">
            <span className="muted small">{ids.length} of {rules.length} selected · {rules.filter((r) => r.criticality === 'warn').length} describe a problem found today (warn)</span>
            <button className="link small" onClick={() => setOff(new Set())}>all</button>
            <button className="link small" onClick={() => setOff(new Set(rules.filter((r) => r.criticality === 'warn').map((r) => r.id)))}>errors only</button>
            <span className="spacer" />
            <button className="btn" disabled={!ids.length} onClick={() => exp('dqx')} title="Databricks DQX checks (YAML)">⤓ DQX .yml</button>
            <button className="btn" disabled={!ids.length} onClick={() => exp('gx')} title="Great Expectations 1.x expectation suite (JSON)">⤓ GX .json</button>
            <button className="btn" disabled={!ids.length} onClick={() => exp('csv')} title="Microsoft Purview Data Quality: rule type and setting per rule (to key in)">⤓ Purview .csv</button>
            <button className="btn" disabled={!ids.length} onClick={() => exp('zip')} title="All three">⤓ all (.zip)</button>
          </div>
          <DataGrid dense id="dqRules" rows={rules} rowKey={(r) => r.id} rowClass={(r) => (off.has(r.id) ? 'off' : '')} columns={[
            { key: 'on', label: '', width: 30, render: (r) => <input type="checkbox" checked={!off.has(r.id)} onChange={() => toggle(r.id)} /> },
            { key: 'columns', label: 'Column(s)', value: (r) => r.columns.join(' + '), render: (r) => <span className="mono">{r.columns.join(' + ')}</span> },
            { key: 'rule', label: 'Rule', value: (r) => RULE_LABEL[r.rule] || r.rule, render: (r) => RULE_LABEL[r.rule] || r.rule },
            { key: 'detail', label: 'Detail', value: (r) => JSON.stringify(r.args), render: (r) => <span className="mono small">{detail(r)}</span> },
            { key: 'criticality', label: 'Level', render: (r) => <span className={`chip ${r.criticality === 'error' ? 'accent' : 'warn'}`}>{r.criticality}</span> },
            { key: 'passing_pct', label: 'Pass today', align: 'right', render: (r) => r.passing_pct == null ? '100%' : `${r.passing_pct >= 99.95 && r.passing_pct < 100 ? '99.9' : +r.passing_pct.toFixed(1)}%` },
            { key: 'reason', label: 'Why', render: (r) => <span className="small">{r.reason}</span> },
            { key: 'purview_rule_type', label: 'Purview rule type', render: (r) => <span className="muted small">{r.purview_rule_type}</span> },
          ]} />
        </>
      )}
    </section>
  )
}

const detail = (r) => {
  const a = r.args || {}
  switch (r.rule) {
    case 'in_list': return `${a.allowed.slice(0, 6).join(', ')}${a.allowed.length > 6 ? ` … (${a.allowed.length})` : ''}`
    case 'regex': return a.regex
    case 'range': return `${a.min_limit} … ${a.max_limit}`
    case 'valid_date': return a.date_format
    case 'foreign_key': return `→ ${a.ref_table}.${a.ref_columns?.[0]}`
    case 'filled_when': return r.filter
    case 'non_negative': return '≥ 0'
    default: return ''
  }
}
