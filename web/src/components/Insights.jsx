import React, { useEffect, useState } from 'react'
import { ago, api, fmt, isPII, monthLabel, sourceNote, waitJob } from '../api.js'
import { Sparkline } from './Charts.jsx'
import DataGrid, { Cell } from './DataGrid.jsx'

const KIND = {
  event: ['event date', 'Business events over time (bookings, postings…): gaps and future rows matter', 'accent'],
  stamp: ['load / change stamp', 'Only 1–2 months: looks like a load or last-modified timestamp, not a business date', 'info'],
  attribute: ['attribute', 'A date that describes the row (birth date, opening date…), not an event stream', 'info'],
}

const Cols = ({ cols, onOpenColumn }) => (
  <span className="eq-cols">{cols.map((c, i) => (
    <React.Fragment key={c}>{i > 0 && <span className="muted"> = </span>}
      <button className="link mono" title="Column profile" onClick={() => onOpenColumn(c)}>{c}</button></React.Fragment>
  ))}</span>
)

/** Modelling insights of one table: grain, time coverage, candidate entities, hierarchies, dirty dependencies. */
export default function InsightsPanel({ t, workshop, onOpenSql, onOpenColumn, onChanged }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [job, setJob] = useState(null)
  const [reload, setReload] = useState(0)
  const [exc, setExc] = useState(null)     // {key, res | error | loading}
  const [names, setNames] = useState({})   // entity id → edited name
  const [keyRes, setKeyRes] = useState(null)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    let off = false
    setErr(null)
    api.insights(t.schema, t.table).then((r) => !off && setD(r)).catch((e) => !off && setErr(e.message))
    return () => { off = true }
  }, [t.schema, t.table, reload])

  const run = async () => {
    setErr(null)
    try {
      const j = await waitJob(await api.runInsights({ tables: [`${t.schema}.${t.table}`] }), setJob)
      if (j.errors?.length) setErr(j.errors[0].error)
      setJob(null); setReload((k) => k + 1); onChanged?.()
    } catch (e) { setErr(e.message); setJob(null) }
  }

  const annotation = (col) => t.columns.find((c) => c.column === col)?.annotation || {}
  const save = async (col, patch) => {
    const a = annotation(col)
    await api.saveAnnotation({ schema: t.schema, table: t.table, column: col, tags: a.tags || '', cdm_entity: a.cdm_entity || '',
      cdm_attribute: a.cdm_attribute || '', notes: a.notes || '', ...patch(a) })
  }
  const tagKey = async (cols) => {
    for (const c of cols) {
      await save(c, (a) => ({ tags: [...new Set([...(a.tags || '').split(',').map((x) => x.trim()).filter(Boolean), 'key'])].join(', ') }))
    }
    setMsg(`Tagged ${cols.join(' + ')} as key`); onChanged?.()
  }
  const mapEntity = async (e) => {
    const name = (names[e.id] ?? e.name).trim()
    if (!name) return
    const cols = [...e.columns, ...e.determines.filter((x) => !x.is_entity).flatMap((x) => x.columns)]
    for (const c of cols) await save(c, () => ({ cdm_entity: name }))
    setMsg(`Mapped ${cols.length} column${cols.length > 1 ? 's' : ''} to CDM entity ${name}`); onChanged?.(); setReload((k) => k + 1)
  }
  const hide = async (from, to) => {
    for (const a of from) for (const b of to) if (a !== b) await api.dismissInsight({ schema: t.schema, table: t.table, item: `${a}->${b}` })
    setReload((k) => k + 1)
  }
  const unhideAll = async () => {
    for (const item of d.dismissed) await api.dismissInsight({ schema: t.schema, table: t.table, item, undo: true })
    setReload((k) => k + 1)
  }
  const showExceptions = async (x) => {
    const key = `${x.determinant}->${x.dependent}`
    if (exc?.key === key) return setExc(null)
    setExc({ key, loading: true })
    try { setExc({ key, res: await api.insightExceptions(t.schema, t.table, x.determinant, x.dependent) }) } catch (e) { setExc({ key, error: e.message }) }
  }
  const checkKey = async (cols) => {
    setKeyRes({ cols, loading: true })
    try { setKeyRes({ cols, ...(await api.uniqueness(t.schema, t.table, cols)) }) } catch (e) { setKeyRes({ cols, error: e.message }) }
  }

  if (t.kind === 'remote') {
    return <div className="notice pad"><b>Insights need the rows.</b> This table is only on {t.remote?.platform || 'the remote source'}: cache it locally
      (⤓ Cache locally, or <code>bearings cache -t …</code> / <code>bearings pull {t.schema}.{t.table}</code>), then run <code>bearings insights -t {t.schema}.{t.table}</code>.</div>
  }
  if (err && !d) return <div className="error">{err}</div>
  if (!d) return <div className="muted pad">Loading…</div>
  const running = job && job.status === 'running'
  const runBtn = (label) => <button className="btn primary" onClick={run} disabled={!!running}>{running ? 'Analysing…' : label}</button>
  if (!d.profiled) return <div className="notice pad"><b>Not profiled yet.</b> Insights build on the column profile: run <code>bearings profile -t {t.schema}.{t.table}</code> first.</div>
  if (!d.computed_at) {
    return (
      <div className="notice pad">
        <b>No insights yet.</b> Find the grain, the time coverage of the date columns and the dependencies between columns (candidate entities, hierarchies,
        code ↔ description pairs). {runBtn('Compute insights')}
        <div className="muted small">Or for everything: <code>bearings insights</code>. Takes about a second per table; big tables are sampled.</div>
        {err && <div className="error">{err}</div>}
      </div>
    )
  }

  const st = d.structure
  const g = d.grain
  const colMeta = Object.fromEntries(t.columns.map((c) => [c.column, c]))
  return (
    <div className="insights">
      <div className="subbar">
        <span className="muted small">Computed {ago(d.computed_at)}{g?.on_sample ? ' on a sample' : ''}{sourceNote(d) ? ` · ${sourceNote(d)}` : ''} ·
          suggestions to review, not facts</span>
        <span className="spacer" />
        {msg && <span className="good-text small">✓ {msg}</span>}
        {d.dismissed?.length > 0 && <button className="link small" onClick={unhideAll}>show {d.dismissed.length} hidden</button>}
        <button className="btn" onClick={run} disabled={!!running} title="Recompute grain, time coverage and dependencies">{running ? 'Analysing…' : '↻ Re-run'}</button>
      </div>
      {err && <div className="error">{err}</div>}

      {/* ---------------- grain */}
      <section className="card">
        <h4>Grain <span className="muted small">— what is one row?</span></h4>
        <div className="ins-body">
          {g?.combos?.length ? (
            <>
              <div className="ins-sentence">Each row is one <b className="mono">{g.combos[0].join(' + ')}</b>
                {g.dup_rows > 0 && <span className="warn-text"> — except {fmt.n(g.dup_rows)} duplicate rows (a data-quality issue, or a column is missing)</span>}.</div>
              {g.combos.length > 1 && <div className="muted small">Also unique: {g.combos.slice(1).map((c) => c.join(' + ')).join(' · ')}</div>}
              <div className="ins-actions">
                <button className="btn" onClick={() => checkKey(g.combos[0])}>Check key</button>
                <button className="btn" onClick={() => tagKey(g.combos[0])} title="Add the tag 'key' to these columns">Tag as key</button>
              </div>
              {keyRes && (
                <div className={`notice ${keyRes.is_unique ? 'good' : keyRes.error ? 'bad' : ''}`}>
                  {keyRes.loading ? 'Checking…' : keyRes.error ? keyRes.error
                    : <><b>{keyRes.cols.join(' + ')}</b>: {keyRes.is_unique ? 'unique on the whole table ✓' : `${fmt.n(keyRes.rows - keyRes.distinct)} duplicate rows`}
                      {keyRes.rows_with_nulls > 0 && <> · {fmt.n(keyRes.rows_with_nulls)} rows with nulls</>}</>}
                  <button className="icon-btn small" onClick={() => setKeyRes(null)}>✕</button>
                </div>
              )}
            </>
          ) : g ? <div className="warn-text">No combination of up to 3 columns is unique — look for a missing sequence or line number, or duplicates.</div>
            : <div className="muted">Not computed.</div>}
        </div>
      </section>

      {/* ---------------- time coverage */}
      <section className="card">
        <h4>Time coverage <span className="muted small">— how much history, and is it complete?</span></h4>
        {d.time.length === 0 ? <div className="ins-body muted">No date columns (or text dates) in this table.</div> : (
          <table className="grid ins-time">
            <thead><tr><th>Column</th><th>Kind</th><th>From – to</th><th className="r">Months</th><th className="r">Empty months</th>
              <th className="r">Future rows</th><th className="r">Sentinel dates</th><th>Rows over time</th></tr></thead>
            <tbody>{d.time.map((x) => {
              const [kl, kt, tone] = KIND[x.kind] || [x.kind, '', 'info']
              return (
                <tr key={x.column_name}>
                  <td><button className="link mono" onClick={() => onOpenColumn(x.column_name)}>{x.column_name}</button>
                    {x.is_primary && <span className="chip good" title="Primary business date of this table"> ★ primary</span>}
                    {x.parsed_from_text && <span className="chip info" title="Stored as text, parsed with the formats found in the profile">text</span>}</td>
                  <td><span className={`chip ${tone}`} title={kt}>{kl}</span></td>
                  <td className="nowrap">{monthLabel(x.first_month)} – {monthLabel(x.last_month)}</td>
                  <td className="r">{fmt.n(x.months_present)}</td>
                  <td className="r">{x.kind === 'event' && x.empty_months > 0 ? <span className="warn-text">{fmt.n(x.empty_months)}</span> : fmt.n(x.empty_months)}</td>
                  <td className="r">{fmt.n(x.future_rows)}</td>
                  <td className="r" title="Dates in 1900 or earlier, or 9999 – placeholders for 'no date'">{x.sentinel_rows ? <span className="warn-text">{fmt.n(x.sentinel_rows)}</span> : 0}</td>
                  <td><Sparkline points={x.series?.points} width={160} height={22} title={`${x.column_name} rows per ${x.series?.grain}`} />
                    {x.series?.grain === 'year' && <span className="muted small"> per year</span>}</td>
                </tr>)
            })}</tbody>
          </table>
        )}
      </section>

      {/* ---------------- optional attributes & subtypes */}
      <section className="card">
        <h4>Optional attributes and subtypes <span className="muted small">— when are the sometimes-empty columns filled?</span></h4>
        {!(d.optional?.rules?.length || d.optional?.groups?.length) ? <div className="ins-body muted">No column is filled only for some kinds of rows.</div> : (
          <ul className="ins-notes">
            {(d.optional.groups || []).map((g, i) => (
              <li key={`g${i}`}><span className={`chip ${g.when ? 'accent' : 'info'}`}>{g.when ? 'subtype?' : 'filled together'}</span>
                <Cols cols={g.columns} onOpenColumn={onOpenColumn} /> <span>{g.sentence.slice(g.columns.join(', ').length)}</span>
                {g.when && <Breakdown t={t} column={g.columns[0]} by={g.when.by_column} />}</li>
            ))}
            {(d.optional.rules || []).filter((r) => !(d.optional.groups || []).some((g) => g.when && g.columns.includes(r.column_name))).map((r) => (
              <li key={r.column_name}><span className="chip accent">filled when</span> {r.sentence}
                <Breakdown t={t} column={r.column_name} by={r.by_column} /></li>
            ))}
          </ul>
        )}
      </section>

      {/* ---------------- code lists */}
      {d.code_lists?.length > 0 && (
        <section className="card">
          <h4>Code lists <span className="muted small">— columns with a small set of values (compare them across systems in the Code lists tab)</span></h4>
          <div className="ins-body code-chips">
            {d.code_lists.map((c) => (
              <span key={c.column} className="code-chip" title={(c.top || []).join(' · ')}>
                <button className="link mono" onClick={() => onOpenColumn(c.column)}>{c.column}</button> <span className="muted small">{c.values} values: {(c.top || []).slice(0, 4).join(', ')}{c.values > 4 ? '…' : ''}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {/* ---------------- structure */}
      <section className="card">
        <h4>Candidate entities <span className="muted small">— columns that belong together (from dependencies between columns)</span></h4>
        {st.entities.length === 0 ? (
          <div className="ins-body muted">No dependencies found: every column varies independently of the others{d.dependencies.length ? '' : ''}.</div>
        ) : (
          <div className="ins-body">
            {st.entities.map((e) => {
              const mapped = e.columns.every((c) => annotation(c).cdm_entity)
              return (
                <div key={e.id} className="entity">
                  <div className="entity-head">
                    <input className="entity-name" value={names[e.id] ?? e.name} onChange={(ev) => setNames({ ...names, [e.id]: ev.target.value })}
                      title="Entity name (edit before mapping)" />
                    {!e.suggested && <span className="chip tag" title="From an existing CDM mapping">CDM</span>}
                    <span className="muted small">{fmt.n(e.distinct)} distinct</span>
                    <span className="spacer" />
                    <button className="btn" onClick={() => mapEntity(e)} title="Set the CDM entity of the key columns and their plain attributes">{mapped ? 'Re-map' : 'Map to CDM entity'}</button>
                    <button className="link small" title="Hide this suggestion" onClick={() => hide(e.columns, [...e.columns, ...e.determines.flatMap((x) => x.columns)])}>hide</button>
                  </div>
                  <div className="entity-key">
                    <span className="muted small">{e.columns.length > 1 ? 'Key (same thing, several spellings)' : 'Key'}</span> <Cols cols={e.columns} onOpenColumn={onOpenColumn} />
                  </div>
                  {e.determines.length > 0 && (
                    <ul className="determines">
                      {e.determines.map((x) => (
                        <li key={x.id}>
                          <span className="arrow">→</span> <Cols cols={x.columns} onOpenColumn={onOpenColumn} />
                          {x.is_entity && <span className="chip accent" title="This is itself a candidate entity: a roll-up level (hierarchy)">{x.name}</span>}
                          {x.kind === 'approx' && <span className="chip warn" title={`${fmt.n(x.exceptions)} rows disagree`}>{(x.strength * 100).toFixed(1)}%</span>}
                          <button className="link small muted" onClick={() => hide(e.columns, x.columns)} title="Not a real dependency – hide it">✕</button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {workshop && <div className="ins-sentence small">Each <b>{names[e.id] ?? e.name}</b> ({e.columns[0]}) always has the same {[...e.columns.slice(1), ...e.determines.flatMap((x) => x.columns)].join(', ') || 'values'}.</div>}
                </div>
              )
            })}
          </div>
        )}
        {st.hierarchies.length > 0 && (
          <div className="ins-body">
            <div className="muted small">Hierarchies (each level determines the next)</div>
            <ul className="hier">{st.hierarchies.map((h, i) => (
              <li key={i}>{h.levels.map((lv, j) => (
                <React.Fragment key={lv.id}>{j > 0 && <span className="arrow"> → </span>}<b title={lv.columns.join(' = ')}>{lv.name}</b></React.Fragment>
              ))}</li>))}</ul>
          </div>
        )}
      </section>

      {(st.dirty.length > 0 || st.notes.length > 0) && (
        <section className="card">
          <h4>Data-quality and model notes</h4>
          <ul className="ins-notes">
            {st.dirty.map((x) => {
              const key = `${x.determinant}->${x.dependent}`
              return (
                <li key={key}>
                  <span className="chip warn">{(x.strength * 100).toFixed(1)}%</span> {x.sentence}
                  <button className="link small" onClick={() => showExceptions(x)}>{exc?.key === key ? 'hide rows' : 'show exception rows'}</button>
                  {exc?.key === key && (
                    <div className="exc">
                      {exc.loading && <div className="muted small">Loading…</div>}
                      {exc.error && <div className="error">{exc.error}</div>}
                      {exc.res && (
                        <>
                          <div className="subbar"><span className="muted small">{exc.res.rows.length} rows whose <span className="mono">{x.dependent}</span> isn't the usual value for their <span className="mono">{x.determinant}</span> (last column: the usual value)</span>
                            <span className="spacer" /><button className="btn" onClick={() => onOpenSql(exc.res.sql)}>Open in SQL</button></div>
                          <DataGrid dense hideEmptyToggle id="exceptions" rows={exc.res.rows} columns={exc.res.columns.map((c, i) => ({
                            key: String(i), label: c, value: (r) => r[i],
                            render: (r) => <Cell v={r[i]} masked={workshop && isPII(colMeta[c])} />,
                          }))} />
                        </>
                      )}
                    </div>
                  )}
                </li>)
            })}
            {st.notes.map((n, i) => <li key={i}><span className={`chip ${n.kind === 'redundant_fk' ? 'accent' : 'info'}`}>{n.kind === 'redundant_fk' ? 'redundant FK' : 'denormalised'}</span> {n.sentence}</li>)}
          </ul>
        </section>
      )}
    </div>
  )
}

/** "break down" link: how a column is filled per value of another, inline. */
function Breakdown({ t, column, by }) {
  const [r, setR] = useState(null)
  const [open, setOpen] = useState(false)
  const toggle = async () => {
    if (open) return setOpen(false)
    setOpen(true)
    if (!r) { try { setR(await api.breakdown(t.schema, t.table, column, by)) } catch (e) { setR({ error: e.message }) } }
  }
  return (
    <>
      <button className="link small" onClick={toggle}>{open ? 'hide' : `by ${by}`}</button>
      {open && (
        <div className="exc">
          {!r ? <div className="muted small">Loading…</div> : r.error ? <div className="error">{r.error}</div> : (
            <table className="grid ins-time"><thead><tr><th>{by}</th><th className="r">Rows</th><th className="r">{column} filled</th><th className="r">%</th><th className="r">Distinct</th><th>Most common</th></tr></thead>
              <tbody>{r.rows.map((x, i) => <tr key={i}><td className="mono">{x[0] ?? '(empty)'}</td><td className="r">{fmt.n(x[1])}</td><td className="r">{fmt.n(x[2])}</td>
                <td className="r">{fmt.pct(x[3])}</td><td className="r">{fmt.n(x[4])}</td><td className="mono small">{x[5] ?? ''}</td></tr>)}</tbody></table>
          )}
        </div>
      )}
    </>
  )
}
