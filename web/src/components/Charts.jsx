import React from 'react'

export function Bar({ pct, tone = 'accent', width = 60 }) {
  const p = Math.max(0, Math.min(100, pct || 0))
  return (
    <span className="bar" style={{ width }}>
      <span className={`bar-fill ${tone}`} style={{ width: `${p}%` }} />
    </span>
  )
}

export function Histogram({ bins }) {
  if (!bins?.length) return null
  const max = Math.max(...bins.map((b) => b.n)) || 1
  const W = 360, H = 90, bw = W / bins.length
  return (
    <div className="hist">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img" aria-label="Value distribution">
        {bins.map((b, i) => {
          const h = Math.max(b.n ? 2 : 0, (b.n / max) * (H - 4))
          return (
            <rect key={i} x={i * bw + 1} y={H - h} width={bw - 2} height={h} rx="1.5" className="hist-bar">
              <title>{`${b.lo} – ${b.hi}: ${b.n.toLocaleString()}`}</title>
            </rect>
          )
        })}
      </svg>
      <div className="hist-axis"><span>{String(bins[0].lo)}</span><span>{String(bins[bins.length - 1].hi)}</span></div>
    </div>
  )
}

export function FreqList({ items, total, onPick, labelKey = 'v', mono }) {
  if (!items?.length) return <div className="muted small">—</div>
  const max = Math.max(...items.map((x) => x.n)) || 1
  return (
    <ul className="freq">
      {items.map((x, i) => (
        <li key={i} onClick={onPick ? () => onPick(x[labelKey]) : undefined} className={onPick ? 'clickable' : ''}
            title={onPick ? 'Search this value across all tables' : undefined}>
          <span className={`freq-label ${mono ? 'mono' : ''}`}>{x[labelKey] === '' ? "''" : String(x[labelKey])}</span>
          <span className="freq-bar"><span style={{ width: `${(x.n / max) * 100}%` }} /></span>
          <span className="freq-n">{x.n.toLocaleString()}{total ? <span className="muted"> · {((x.n / total) * 100).toFixed(1)}%</span> : null}</span>
        </li>
      ))}
    </ul>
  )
}

const FLAG_INFO = {
  candidate_pk: ['PK?', 'Unique and never null — candidate key', 'good'],
  unique: ['unique', 'Unique and never null (non-key type)', 'info'],
  unique_with_nulls: ['unique*', 'Unique among non-null values, but has nulls', 'info'],
  all_null: ['all null', 'Every value is null', 'bad'],
  constant: ['constant', 'Only one distinct value', 'warn'],
  high_null: ['≥50% null', 'At least half the values are null', 'warn'],
  pii_email: ['PII email', 'Values look like email addresses', 'pii'],
  pii_phone: ['PII phone', 'Values look like phone numbers', 'pii'],
  pii_name_hint: ['PII?', 'Column name suggests personal data', 'pii'],
  mixed_format: ['mixed fmt', 'Several different value shapes', 'warn'],
  has_blanks: ['blanks', 'Contains empty / whitespace strings', 'warn'],
}

export function Flags({ flags }) {
  if (!flags?.length) return null
  return (
    <span className="flags">
      {flags.map((f) => {
        const [l, t, tone] = FLAG_INFO[f] || [f, f, 'info']
        return <span key={f} className={`chip ${tone}`} title={t}>{l}</span>
      })}
    </span>
  )
}

export function Tags({ tags }) {
  if (!tags) return null
  return <span className="flags">{tags.split(',').map((t) => t.trim()).filter(Boolean).map((t) => <span key={t} className="chip tag">{t}</span>)}</span>
}
