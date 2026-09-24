import React, { useEffect, useRef, useState } from 'react'
import { api, fmt, store } from '../api.js'

const FORMAT_CHIP = { csv: 'CSV', parquet: 'Parquet', json: 'JSON', excel: 'Excel' }
const PHASE = { load: 'Loading', comments: 'Importing descriptions', profile: 'Profiling', relate: 'Finding relationships', insights: 'Modelling insights', done: 'Done' }
const bytes = (n) => (n == null ? '' : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MB` : `${(n / 1073741824).toFixed(2)} GB`)
const newBatch = () => `drop_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`

/** Walk a dropped DataTransfer (files and folders) → [{file, path}] with folder-relative paths. */
export async function filesFromDrop(dt) {
  const entries = [...(dt.items || [])].map((i) => i.webkitGetAsEntry?.()).filter(Boolean)
  if (!entries.length) return [...(dt.files || [])].map((f) => ({ file: f, path: f.name }))
  const out = []
  const walk = async (entry, prefix) => {
    if (entry.isFile) {
      const file = await new Promise((res, rej) => entry.file(res, rej))
      out.push({ file, path: prefix + entry.name })
    } else if (entry.isDirectory) {
      const reader = entry.createReader()
      let batch
      do {
        batch = await new Promise((res, rej) => reader.readEntries(res, rej))
        for (const e of batch) await walk(e, `${prefix}${entry.name}/`)
      } while (batch.length)
    }
  }
  for (const e of entries) await walk(e, '')
  return out.filter((f) => !/(^|\/)[._~]/.test(f.path))   // .DS_Store, _SUCCESS, ~$lock files
}

function upload(batch, { file, path }, onProgress) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest()
    x.open('POST', `/api/load/upload?batch=${encodeURIComponent(batch)}&name=${encodeURIComponent(path)}`)
    x.upload.onprogress = (e) => onProgress(e.loaded)
    x.onload = () => (x.status < 300 ? resolve(JSON.parse(x.responseText)) : reject(new Error(x.responseText || x.statusText)))
    x.onerror = () => reject(new Error('Upload failed'))
    x.send(file)
  })
}

/** "Add data": drop files / a folder, or pick a path on this computer → preview → load + profile + relate. */
export default function AddData({ onClose, onLoaded, onOpenTable, initialFiles, schemas = [] }) {
  const [step, setStep] = useState('source') // source | uploading | preview | running | done
  const [path, setPath] = useState(() => store.get('addPath', ''))
  const [browse, setBrowse] = useState(null)
  const [src, setSrc] = useState(null) // {path} | {upload}
  const [pv, setPv] = useState(null)
  const [schema, setSchema] = useState('')
  const [mode, setMode] = useState('replace')
  const [picked, setPicked] = useState(new Set())
  const [comments, setComments] = useState(new Set())
  const [opts, setOpts] = useState({ all_varchar: false, sheets: '', header_row: '', profile: true, relate: true })
  const [up, setUp] = useState(null)
  const [job, setJob] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [over, setOver] = useState(false)
  const fileRef = useRef(null)
  const dirRef = useRef(null)

  useEffect(() => { if (initialFiles?.length) uploadFiles(initialFiles) }, []) // eslint-disable-line
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape' && step !== 'running' && step !== 'uploading') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [step]) // eslint-disable-line
  useEffect(() => { // poll the load job
    if (!job || job.status !== 'running') return
    const h = setTimeout(() => api.job(job.id).then((j) => {
      setJob(j)
      if (j.status !== 'running') { setStep('done'); onLoaded?.(j) }
    }).catch((e) => setErr(e.message)), 700)
    return () => clearTimeout(h)
  }, [job]) // eslint-disable-line

  const doPreview = async (source, o = opts) => {
    setErr(null); setBusy(true)
    try {
      const r = await api.loadPreview({ ...source, sheets: o.sheets, header_row: o.header_row })
      setSrc(source); setPv(r); setStep('preview')
      setSchema((s) => (s && step === 'preview' ? s : r.suggested_schema))
      setPicked(new Set(r.items.map((i) => i.table)))
      setComments(new Set(r.comments))
      if (source.path) store.set('addPath', source.path)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const uploadFiles = async (files) => {
    if (!files.length) return
    setErr(null); setStep('uploading')
    const batch = newBatch()
    const total = files.reduce((a, f) => a + f.file.size, 0)
    let done = 0
    try {
      for (let i = 0; i < files.length; i++) {
        setUp({ i, n: files.length, name: files[i].path, sent: done, total })
        await upload(batch, files[i], (b) => setUp({ i, n: files.length, name: files[i].path, sent: done + b, total }))
        done += files[i].file.size
      }
      setUp(null)
      await doPreview({ upload: batch })
    } catch (e) { setErr(e.message); setStep('source') }
  }

  const openBrowse = async (p) => {
    setErr(null)
    try { setBrowse(await api.loadLs(p || path || undefined)) } catch (e) {
      try { setBrowse(await api.loadLs()) } catch { setErr(e.message) }
    }
  }

  const start = async () => {
    setErr(null)
    try {
      const j = await api.load({ ...src, schema: schema.trim() || 'main', mode, tables: [...picked], comments: [...comments],
        all_varchar: opts.all_varchar, sheets: opts.sheets, header_row: opts.header_row, profile: opts.profile, relate: opts.relate })
      setJob(j); setStep('running')
    } catch (e) { setErr(e.message) }
  }

  const onDrop = async (e) => { e.preventDefault(); setOver(false); uploadFiles(await filesFromDrop(e.dataTransfer)) }
  const fromInput = (e) => uploadFiles([...e.target.files].map((f) => ({ file: f, path: f.webkitRelativePath || f.name })))

  const existing = new Set(pv?.existing || [])
  const hasExcel = pv?.items.some((i) => i.format === 'excel')
  const nPicked = pv ? pv.items.filter((i) => picked.has(i.table)).length : 0
  const replacing = pv ? pv.items.filter((i) => picked.has(i.table) && existing.has(`${schema}.${i.table}`)).length : 0
  const toggle = (set, setter, k) => { const s = new Set(set); s.has(k) ? s.delete(k) : s.add(k); setter(s) }

  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget && !['running', 'uploading'].includes(step)) onClose() }}>
      <div className="modal add-data" role="dialog" aria-label="Add data">
        <div className="modal-head">
          <h3>Add data</h3>
          <span className="muted small">{step === 'preview' ? (src?.upload ? 'dropped files' : pv?.path) : 'CSV · TSV · Parquet · JSON · Excel'}</span>
          <span className="spacer" />
          {!['running', 'uploading'].includes(step) && <button className="icon-btn" onClick={onClose} title="Close (Esc)">✕</button>}
        </div>

        {err && <div className="error">{err}</div>}

        {step === 'source' && (
          <div className="modal-body">
            <div className={`dropzone ${over ? 'over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true) }}
              onDragLeave={() => setOver(false)} onDrop={onDrop}>
              <div className="dz-icon">⤓</div>
              <div><b>Drop files or a folder here</b></div>
              <div className="muted small">A folder becomes a schema; a sub-folder of part-files one table; every Excel sheet a table</div>
              <div className="dz-actions">
                <button className="btn" onClick={() => fileRef.current.click()}>Choose files…</button>
                <button className="btn" onClick={() => dirRef.current.click()}>Choose a folder…</button>
              </div>
              <input ref={fileRef} type="file" multiple hidden onChange={fromInput} accept=".csv,.tsv,.txt,.gz,.parquet,.pq,.json,.jsonl,.ndjson,.xlsx,.xlsm" />
              <input ref={dirRef} type="file" hidden webkitdirectory="" directory="" onChange={fromInput} />
            </div>
            <div className="or"><span>or load from a path on this computer (no copy is made)</span></div>
            <form className="path-row" onSubmit={(e) => { e.preventDefault(); if (path.trim()) doPreview({ path: path.trim() }) }}>
              <input className="mono grow" placeholder="~/exports/opera   or   /data/crm/customers.xlsx" value={path} onChange={(e) => setPath(e.target.value)} autoFocus />
              <button type="button" className="btn" onClick={() => (browse ? setBrowse(null) : openBrowse())}>{browse ? 'Hide' : 'Browse…'}</button>
              <button className="btn primary" disabled={!path.trim() || busy}>{busy ? 'Reading…' : 'Preview'}</button>
            </form>
            {browse && (
              <div className="browser">
                <div className="browser-head mono small">
                  {browse.parent && <button className="link" onClick={() => openBrowse(browse.parent)} title="Up one folder">↑ ..</button>}
                  <span className="muted">{browse.path}</span>
                  <span className="spacer" />
                  <button className="btn small primary" onClick={() => { setPath(browse.path); doPreview({ path: browse.path }) }}>Use this folder</button>
                </div>
                <ul className="list compact">
                  {browse.dirs.map((d) => <li key={d} className="mono" onClick={() => openBrowse(`${browse.path}/${d}`)}>📁 {d}</li>)}
                  {browse.files.map((f) => (
                    <li key={f.name} className="mono" onClick={() => { const p = `${browse.path}/${f.name}`; setPath(p); doPreview({ path: p }) }}>
                      📄 {f.name} <span className="muted small">{FORMAT_CHIP[f.format] || f.format} · {bytes(f.bytes)}</span></li>
                  ))}
                  {!browse.dirs.length && !browse.files.length && <li className="muted">Nothing loadable here</li>}
                </ul>
              </div>
            )}
          </div>
        )}

        {step === 'uploading' && up && (
          <div className="modal-body">
            <div>Uploading {up.i + 1} of {up.n}: <span className="mono">{up.name}</span></div>
            <div className="progress"><div style={{ width: `${Math.round(100 * up.sent / (up.total || 1))}%` }} /></div>
            <div className="muted small">{bytes(up.sent)} of {bytes(up.total)} · copied into the Bearings data folder (data/uploads)</div>
          </div>
        )}

        {step === 'preview' && pv && (
          <div className="modal-body">
            <div className="form-row">
              <label>Schema
                <input className="mono" list="schema-list" value={schema} onChange={(e) => setSchema(e.target.value)} placeholder="e.g. pms, crm, finance" />
                <datalist id="schema-list">{schemas.map((s) => <option key={s} value={s} />)}</datalist>
              </label>
              <div className="seg" title="Replace: recreate the tables · Append: add rows to existing tables">
                {['replace', 'append'].map((m) => <button key={m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>{m[0].toUpperCase() + m.slice(1)}</button>)}
              </div>
              <span className="spacer" />
              <label className="check" title="Keep every CSV / Excel column as text (leading zeros, odd formats)">
                <input type="checkbox" checked={opts.all_varchar} onChange={(e) => setOpts({ ...opts, all_varchar: e.target.checked })} /> all as text</label>
            </div>
            {hasExcel && (
              <form className="form-row small" onSubmit={(e) => { e.preventDefault(); doPreview(src) }}>
                <span className="muted">Excel:</span>
                <label>sheets <input value={opts.sheets} placeholder="all non-empty" onChange={(e) => setOpts({ ...opts, sheets: e.target.value })} /></label>
                <label>header row <input className="num" value={opts.header_row} placeholder="auto" onChange={(e) => setOpts({ ...opts, header_row: e.target.value.replace(/\D/g, '') })} /></label>
                <button className="btn small">Apply</button>
              </form>
            )}
            <div className="pv-table">
              <div className="pv-head">
                <input type="checkbox" checked={nPicked === pv.items.length && nPicked > 0}
                  ref={(el) => el && (el.indeterminate = nPicked > 0 && nPicked < pv.items.length)}
                  onChange={() => setPicked(nPicked === pv.items.length ? new Set() : new Set(pv.items.map((i) => i.table)))} />
                <b>{pv.items.length} table{pv.items.length === 1 ? '' : 's'} found</b>
                {replacing > 0 && mode === 'replace' && <span className="chip warn">{replacing} will be replaced</span>}
              </div>
              <ul className="list">
                {pv.items.map((i) => (
                  <li key={i.table} className={picked.has(i.table) ? '' : 'off'} onClick={() => toggle(picked, setPicked, i.table)}>
                    <div className="li-main">
                      <input type="checkbox" checked={picked.has(i.table)} readOnly />
                      <span className="mono"><span className="muted">{schema || 'main'}.</span><b>{i.table}</b></span>
                      <span className="chip">{FORMAT_CHIP[i.format] || i.format}</span>
                      {existing.has(`${schema}.${i.table}`) && <span className="chip warn" title="A table with this name exists in the schema">exists</span>}
                      <span className="spacer" />
                      <span className="muted small">{i.files > 1 ? `${i.files} files · ` : ''}{bytes(i.bytes)}</span>
                    </div>
                    <div className="li-ex mono">{i.label}</div>
                  </li>
                ))}
                {pv.items.length === 0 && <li className="muted">No loadable files ({pv.messages?.join(' · ') || 'CSV, Parquet, JSON or Excel'})</li>}
              </ul>
              {pv.comments.length > 0 && (
                <div className="pv-comments">
                  <div className="muted small">Description files (table_name, column_name, comment) – imported as searchable comments:</div>
                  {pv.comments.map((c, k) => (
                    <label key={c} className="check"><input type="checkbox" checked={comments.has(c)} onChange={() => toggle(comments, setComments, c)} />
                      <span className="mono">{(pv.comments_display || pv.comments)[k]}</span></label>
                  ))}
                </div>
              )}
              {pv.messages?.length > 0 && pv.items.length > 0 && <div className="muted small pad-x">{pv.messages.join(' · ')}</div>}
            </div>
            <div className="form-row">
              <label className="check"><input type="checkbox" checked={opts.profile} onChange={(e) => setOpts({ ...opts, profile: e.target.checked })} /> profile after loading</label>
              <label className="check" title="Name similarity + value overlap between the new tables and everything already loaded">
                <input type="checkbox" checked={opts.relate && opts.profile} disabled={!opts.profile} onChange={(e) => setOpts({ ...opts, relate: e.target.checked })} /> find relationships</label>
              <span className="spacer" />
              <button className="btn" onClick={() => { setStep('source'); setPv(null) }}>Back</button>
              <button className="btn primary" disabled={!nPicked && !comments.size} onClick={start}>
                Load {nPicked} table{nPicked === 1 ? '' : 's'}{comments.size ? ` + ${comments.size} description file${comments.size > 1 ? 's' : ''}` : ''}</button>
            </div>
          </div>
        )}

        {(step === 'running' || step === 'done') && job && (
          <div className="modal-body">
            {step === 'running' && (
              <>
                <div><b>{PHASE[job.phase] || 'Working'}</b> {job.current && <span className="mono">{job.current}</span>}</div>
                <div className="progress"><div style={{ width: `${job.total ? Math.round(100 * (job.done || 0) / job.total) : 5}%` }} /></div>
                <div className="muted small">{job.done || 0} of {job.total || '…'} · you can keep exploring; the app refreshes when it's done</div>
              </>
            )}
            {step === 'done' && (
              <>
                <div className={`notice ${job.status === 'done' ? 'good' : 'bad'}`}>
                  {job.status === 'done' ? '✓' : '⚠'} {fmt.n(job.results.length)} table{job.results.length === 1 ? '' : 's'} loaded into <b className="mono">{job.schema}</b>
                  {job.summary && <span className="muted small"> · {job.summary.profiled} profiled · {job.summary.relationships} relationships{job.summary.comments ? ` · ${job.summary.comments} descriptions` : ''} · {job.summary.seconds}s</span>}
                </div>
                <ul className="list compact done-list">
                  {job.results.map((r) => (
                    <li key={r.table} onClick={() => { onOpenTable(r.schema, r.table); onClose() }} title="Open">
                      <span className="mono">{r.schema}.<b>{r.table}</b></span> <span className="muted small">{fmt.n(r.rows)} rows · {r.columns} cols
                        {r.candidate_keys?.length ? ` · key: ${r.candidate_keys.slice(0, 2).join(', ')}` : ''}</span>
                    </li>
                  ))}
                  {job.errors.map((e, k) => <li key={`e${k}`} className="error small"><span className="mono">{e.table}</span> {e.error}</li>)}
                </ul>
                <div className="form-row">
                  <span className="spacer" />
                  <button className="btn" onClick={() => { setStep('source'); setPv(null); setJob(null) }}>Add more</button>
                  {job.results[0] && <button className="btn primary" onClick={() => { onOpenTable(job.results[0].schema, job.results[0].table); onClose() }}>Open {job.results[0].table}</button>}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
