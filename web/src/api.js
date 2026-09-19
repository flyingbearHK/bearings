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
  search: (q, mode, o = {}) => req(`/api/search?${qs({ q, mode, exact: o.exact ? 'true' : undefined, match: o.match, columns_only: o.columns_only ? 'true' : undefined, schemas: o.schemas })}`),
  lookup: (targets, op, value, limit) => req('/api/lookup', { method: 'POST', body: JSON.stringify({ targets, op, value, limit }) }),
  table: (s, t) => req(`/api/table/${enc(s)}/${enc(t)}`),
  sample: (s, t, o) => req(`/api/table/${enc(s)}/${enc(t)}/sample?${qs(o)}`),
  profile: (s, t, o = {}) => req(`/api/table/${enc(s)}/${enc(t)}/profile?${qs(o)}`),
  uniqueness: (s, t, columns) => req(`/api/table/${enc(s)}/${enc(t)}/uniqueness`, { method: 'POST', body: JSON.stringify({ columns }) }),
  markdown: (s, t) => req(`/api/table/${enc(s)}/${enc(t)}/export.md`),
  relationships: (o = {}) => req(`/api/relationships?${qs(o)}`),
  overlap: (left, right) => req(`/api/overlap?${qs({ left, right })}`),
  annotations: (schemas) => req(`/api/annotations?${qs({ schemas })}`),
  saveAnnotation: (a) => req('/api/annotations', { method: 'PUT', body: JSON.stringify(a) }),
  sql: (sql, limit) => req('/api/sql', { method: 'POST', body: JSON.stringify({ sql, limit }) }),
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
