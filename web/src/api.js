async function req(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail || msg } catch { /* not json */ }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  const ct = r.headers.get('content-type') || ''
  return ct.includes('json') ? r.json() : r.text()
}
const enc = encodeURIComponent
const qs = (o) => Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => `${k}=${enc(v)}`).join('&')

export const api = {
  stats: (schemas) => req(`/api/stats?${qs({ schemas })}`),
  tables: (schemas) => req(`/api/tables?${qs({ schemas })}`),
  search: (q, mode, o = {}) => req(`/api/search?${qs({ q, mode, exact: o.exact ? 'true' : undefined, match: o.match, columns_only: o.columns_only ? 'true' : undefined, schemas: o.schemas, remote: o.remote ? 'true' : undefined })}`),
  lookup: (targets, op, value, limit, remote) => req('/api/lookup', { method: 'POST', body: JSON.stringify({ targets, op, value, limit, remote }) }),
  table: (s, t) => req(`/api/table/${enc(s)}/${enc(t)}`),
  sample: (s, t, o) => req(`/api/table/${enc(s)}/${enc(t)}/sample?${qs(o)}`),
  profile: (s, t, o = {}) => req(`/api/table/${enc(s)}/${enc(t)}/profile?${qs(o)}`),
  uniqueness: (s, t, columns, remote) => req(`/api/table/${enc(s)}/${enc(t)}/uniqueness`, { method: 'POST', body: JSON.stringify({ columns, remote }) }),
  markdown: (s, t) => req(`/api/table/${enc(s)}/${enc(t)}/export.md`),
  relationships: (o = {}) => req(`/api/relationships?${qs(o)}`),
  overlap: (left, right) => req(`/api/overlap?${qs({ left, right })}`),
  annotations: (schemas) => req(`/api/annotations?${qs({ schemas })}`),
  saveAnnotation: (a) => req('/api/annotations', { method: 'PUT', body: JSON.stringify(a) }),
  sql: (sql, limit, engine) => req('/api/sql', { method: 'POST', body: JSON.stringify({ sql, limit, engine }) }),
  // remote sources (connectors: Databricks, …)
  remote: () => req('/api/remote'),
  remoteSync: (body) => req('/api/remote/sync', { method: 'POST', body: JSON.stringify(body) }),
  remoteJob: (id) => req(`/api/remote/jobs/${enc(id)}`),
  remoteWarm: (connection) => req('/api/remote/warm', { method: 'POST', body: JSON.stringify({ connection }) }),
  remoteWarmStatus: () => req('/api/remote/warm'),
  remotePull: (body) => req('/api/remote/pull', { method: 'POST', body: JSON.stringify(body) }),
  remoteProfile: (body) => req('/api/remote/profile', { method: 'POST', body: JSON.stringify(body) }),
  remoteChanges: (alias, limit) => req(`/api/remote/changes?${qs({ alias, limit })}`),
  // jobs + adding local data
  job: (id) => req(`/api/jobs/${enc(id)}`),
  loadFormats: () => req('/api/load/formats'),
  loadLs: (path) => req(`/api/load/ls?${qs({ path })}`),
  loadPreview: (body) => req('/api/load/preview', { method: 'POST', body: JSON.stringify(body) }),
  load: (body) => req('/api/load', { method: 'POST', body: JSON.stringify(body) }),
  orphans: (schemas) => req(`/api/annotations/orphans?${qs({ schemas })}`),
  remap: (body) => req('/api/annotations/remap', { method: 'POST', body: JSON.stringify(body) }),
}

export const exportUrl = (fmt, schemas) => `/api/export/catalog.${fmt}${schemas ? `?schemas=${enc(schemas)}` : ''}`

export const store = {
  get(k, d) { try { const v = localStorage.getItem('dm:' + k); return v == null ? d : JSON.parse(v) } catch { return d } },
  set(k, v) { try { localStorage.setItem('dm:' + k, JSON.stringify(v)) } catch { /* ignore */ } },
}

export const fmt = {
  n: (v) => (v == null ? '' : Number(v).toLocaleString()),
  pct: (v) => (v == null ? '' : v > 0 && v < 0.1 ? '<0.1%' : `${Number(v).toFixed(v < 10 && v > 0 ? 1 : 0)}%`),
}

export const isPII = (col) => {
  const flags = col?.flags || col?.profile?.flags || []
  const tags = (col?.tags ?? col?.annotation?.tags ?? '') || ''
  return flags.some((f) => f.startsWith('pii_')) || /\bpii\b/i.test(tags)
}

/** '2026-09-19T13:05:00' → '5 min ago' */
export const ago = (ts) => {
  if (!ts) return 'never'
  const d = (Date.now() - new Date(ts.replace(' ', 'T')).getTime()) / 1000
  if (!isFinite(d)) return ts
  if (d < 60) return 'just now'
  if (d < 3600) return `${Math.round(d / 60)} min ago`
  if (d < 86400) return `${Math.round(d / 3600)} h ago`
  return `${Math.round(d / 86400)} d ago`
}

/** Where a table's rows live: local (loaded file), cached (complete local copy of a remote table),
 *  sample (local sample, whole table remote), remote (remote only, e.g. Databricks). */
export const STORAGE = {
  cached: { chip: 'good', label: '● cached', title: 'Complete local copy of the remote table: queries run locally' },
  sample: { chip: 'warn', label: '◐ remote/cached', title: 'A random sample is cached locally (queries run on it); the whole table is remote – tick ⚡ Remote for it' },
  remote: { chip: 'cloud', label: '☁ remote', title: 'Not cached: queries run live on the remote source (e.g. the Databricks SQL warehouse)' },
}
export const sourceNote = (r) => r?.source === 'remote' ? `⚡ live from ${r.platform || 'the remote source'}${r.elapsed_ms != null ? ` in ${fmt.n(r.elapsed_ms)} ms` : ''}`
  : r?.source === 'sample' ? `from the cached sample${r.cached_rows ? ` (${fmt.n(r.cached_rows)} of ${fmt.n(r.total_rows)} rows)` : ''}`
    : r?.source === 'cached' ? 'from the local cache' : ''

/** Copy text to the clipboard and show a short confirmation. */
export const copy = (text, what = 'Copied') => {
  const done = () => window.dispatchEvent(new CustomEvent('bearings:toast', { detail: `${what}: ${String(text).slice(0, 60)}` }))
  try { navigator.clipboard.writeText(String(text)).then(done, done) } catch { done() }
}

/** Recently opened tables (most recent first), kept in the browser. */
export const recent = {
  get: () => store.get('recent', []),
  add(schema, table) {
    const k = `${schema}.${table}`
    store.set('recent', [k, ...recent.get().filter((x) => x !== k)].slice(0, 12))
  },
}

/** Split text around case-insensitive matches of `term` → [{t, hit}] (for <mark> highlighting). */
export const splitHits = (text, term) => {
  if (!term || text == null) return [{ t: String(text ?? ''), hit: false }]
  const s = String(text), low = s.toLowerCase(), q = String(term).toLowerCase()
  if (!q || !low.includes(q)) return [{ t: s, hit: false }]
  const out = []
  let i = 0, j
  while ((j = low.indexOf(q, i)) !== -1) {
    if (j > i) out.push({ t: s.slice(i, j), hit: false })
    out.push({ t: s.slice(j, j + q.length), hit: true })
    i = j + q.length
  }
  if (i < s.length) out.push({ t: s.slice(i), hit: false })
  return out
}
