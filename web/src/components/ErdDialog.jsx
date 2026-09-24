import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, copy, fmt } from '../api.js'

const key = (s, t) => `${s}.${t}`
const AUTO_MAX = 40   // regenerate automatically up to this many entities; above it, click Generate

let mermaidP = null
const loadMermaid = () => {
  if (!mermaidP) {
    mermaidP = Promise.all([import('mermaid'), import('@mermaid-js/layout-elk')]).then(([{ default: m }, { default: elk }]) => {
      m.registerLayoutLoaders(elk)
      const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
      m.initialize({ startOnLoad: false, securityLevel: 'strict', theme: dark ? 'dark' : 'default', maxTextSize: 2000000,
        maxEdges: 5000, er: { useMaxWidth: false } })
      return m
    })
  }
  return mermaidP
}

/** Layout settings travel inside the Mermaid text (front matter + direction), so the downloaded .mmd draws the same. */
const LAYOUTS = {
  elk: { label: 'Tidy (ELK)', title: 'Layered layout that routes the lines around the boxes' },
  dagre: { label: 'Classic', title: "Mermaid's default layout" },
}
const compose = (text, layout, dir) => {
  const body = text.replace(/^erDiagram\n/, `erDiagram\n    direction ${dir}\n`)
  if (layout !== 'elk') return body
  return `---\nconfig:\n  layout: elk\n  elk:\n    nodePlacementStrategy: BRANDES_KOEPF\n    mergeEdges: false\n---\n${body}`
}

const download = (text, name, type) => {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type }))
  a.download = name
  a.click()
}

const esc = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** draw.io (diagrams.net) file of the model, with each entity where the rendered diagram placed it – boxes can then be
 *  moved by hand and the connectors follow. */
export const toDrawio = (model, svgEl, title = 'ERD') => {
  const HEAD = 30, ROW = 24
  const pos = {}
  svgEl?.querySelectorAll('g.node').forEach((g) => {
    const m = /-entity-(.+)-\d+$/.exec(g.id || '')
    if (!m) return
    const t = /translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)/.exec(g.getAttribute('transform') || '')
    const bb = g.getBBox()
    const cx = t ? +t[1] : bb.x + bb.width / 2, cy = t ? +t[2] : bb.y + bb.height / 2
    pos[m[1]] = { x: cx - bb.width / 2, y: cy - bb.height / 2, w: bb.width }
  })
  const cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
  model.entities.forEach((e, i) => {
    const p = pos[e.id] || { x: 40 + (i % 5) * 280, y: 40 + Math.floor(i / 5) * 260, w: 220 }
    const w = Math.max(180, Math.round(p.w))
    const h = HEAD + ROW * Math.max(1, e.attributes.length)
    cells.push(`<mxCell id="e_${esc(e.id)}" value="${esc(e.table)}" style="swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;startSize=${HEAD};horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=1;marginBottom=0;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">`
      + `<mxGeometry x="${Math.round(p.x)}" y="${Math.round(p.y)}" width="${w}" height="${h}" as="geometry"/></mxCell>`)
    e.attributes.forEach((a, j) => {
      cells.push(`<mxCell id="e_${esc(e.id)}_${j}" value="${esc(`${a.key}  ${a.name} : ${a.type}`)}" style="text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=6;spacingRight=4;overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;html=1;${a.key === 'PK' ? 'fontStyle=1;' : ''}" vertex="1" parent="e_${esc(e.id)}">`
        + `<mxGeometry y="${HEAD + j * ROW}" width="${w}" height="${ROW}" as="geometry"/></mxCell>`)
    })
  })
  model.links.forEach((l, i) => {
    cells.push(`<mxCell id="l_${i}" value="${esc(l.label)}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;fontSize=10;startArrow=${l.parent_arrow};endArrow=${l.child_arrow};startFill=0;endFill=0;" edge="1" parent="1" source="e_${esc(l.parent)}" target="e_${esc(l.child)}">`
      + `<mxGeometry relative="1" as="geometry"/></mxCell>`)
  })
  return `<mxfile host="Bearings"><diagram name="${esc(title)}" id="erd"><mxGraphModel grid="1" gridSize="10" guides="1" connect="1" arrows="1" fold="1" page="0"><root>${cells.join('')}</root></mxGraphModel></diagram></mxfile>\n`
}

/** ER diagram builder: pick the entities (tables) to draw, preview the Mermaid diagram, download .mmd / .svg.
 *  rels: the relationships to choose from (e.g. the filtered rows of the Relationships tab).
 *  focus: "schema.table" – start from this table and its neighbours (1 or 2 hops); rels are then loaded here. */
export default function ErdDialog({ rels: relsIn, focus, scope, minConfidence = 0.8, onClose, onOpenTable }) {
  const [allRels, setAllRels] = useState(relsIn || null)
  const [minConf, setMinConf] = useState(minConfidence)
  const [depth, setDepth] = useState(1)
  const [excluded, setExcluded] = useState(() => new Set())
  const [f, setF] = useState('')
  const [res, setRes] = useState(null)       // {mermaid, entities, links}
  const [svg, setSvg] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [dirty, setDirty] = useState(true)
  const [layout, setLayout] = useState('elk')
  const [dir, setDir] = useState('TB')
  const seq = useRef(0)
  const canvas = useRef(null)
  const drawio = () => download(toDrawio(res.model, canvas.current?.querySelector('svg'), base), `${base}.drawio`, 'application/xml')
  const fit = () => {
    const el = canvas.current?.querySelector('svg')
    if (!el || !canvas.current) return
    const vb = el.viewBox?.baseVal
    const w = (vb && vb.width) || el.getBoundingClientRect().width / zoom
    const h = (vb && vb.height) || el.getBoundingClientRect().height / zoom
    if (!w || !h) return
    const z = Math.min(1, (canvas.current.clientWidth - 32) / w, Math.max(0.35, (canvas.current.clientHeight - 32) / h))
    setZoom(+Math.max(0.2, z).toFixed(2))
  }
  useEffect(() => { if (svg) requestAnimationFrame(fit) }, [svg]) // eslint-disable-line

  useEffect(() => { if (!relsIn) api.relationships(scope ? { schemas: scope } : {}).then(setAllRels).catch((e) => setErr(e.message)) }, []) // eslint-disable-line
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const rels = useMemo(() => (allRels || []).filter((r) => (r.confidence || 0) >= minConf), [allRels, minConf])

  // candidate entities: every end of the given links, or the neighbourhood of the focus table
  const candidates = useMemo(() => {
    const links = new Map()
    const add = (a, b) => { links.set(a, (links.get(a) || 0) + (b ? 1 : 0)) }
    if (!focus) {
      for (const r of rels) { add(key(r.from_schema, r.from_table), 1); add(key(r.to_schema, r.to_table), 1) }
      return [...links.entries()].map(([k, n]) => ({ k, n })).sort((a, b) => a.k.localeCompare(b.k))
    }
    const hop = new Map([[focus, 0]])
    let frontier = [focus]
    for (let d = 1; d <= depth; d++) {
      const next = []
      for (const r of rels) {
        const a = key(r.from_schema, r.from_table), b = key(r.to_schema, r.to_table)
        for (const [x, y] of [[a, b], [b, a]]) {
          if (frontier.includes(x) && !hop.has(y)) { hop.set(y, d); next.push(y) }
        }
      }
      frontier = next
    }
    for (const r of rels) {
      const a = key(r.from_schema, r.from_table), b = key(r.to_schema, r.to_table)
      if (hop.has(a) && hop.has(b)) { add(a, 1); add(b, 1) }
    }
    return [...hop.entries()].map(([k, h]) => ({ k, n: links.get(k) || 0, hop: h }))
      .sort((a, b) => a.hop - b.hop || a.k.localeCompare(b.k))
  }, [rels, focus, depth])

  const selected = candidates.filter((c) => !excluded.has(c.k)).map((c) => c.k)
  const selKey = selected.join('|')
  const shownList = candidates.filter((c) => !f || c.k.toLowerCase().includes(f.toLowerCase()))

  const generate = async () => {
    const id = ++seq.current
    setBusy(true); setErr(null); setDirty(false)
    try {
      const r = await api.erdBuild({ tables: selected, min_confidence: minConf })
      if (id !== seq.current) return
      const text = compose(r.mermaid, layout, dir)
      setRes({ ...r, text })
      const m = await loadMermaid()
      const out = await m.render(`erd-svg-${id}`, text)
      if (id === seq.current) setSvg(out.svg)
    } catch (e) {
      if (id === seq.current) { setErr(e.message || String(e)); setSvg('') }
    } finally { if (id === seq.current) setBusy(false) }
  }
  useEffect(() => {
    setDirty(true)
    if (!allRels || selected.length === 0 || selected.length > AUTO_MAX) return
    const h = setTimeout(generate, 300)
    return () => clearTimeout(h)
  }, [selKey, minConf, allRels, layout, dir]) // eslint-disable-line

  const toggle = (k) => setExcluded((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })
  const setMany = (keys, on) => setExcluded((s) => { const n = new Set(s); keys.forEach((k) => (on ? n.delete(k) : n.add(k))); return n })
  const base = `erd_${focus ? focus.replace(/\./g, '_') : (scope || 'selection').replace(/,/g, '_')}`

  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal erd-modal" role="dialog" aria-label="ER diagram">
        <div className="modal-head">
          <h3>ER diagram</h3>
          <span className="muted small">{focus ? <>around <span className="mono">{focus}</span></> : 'from the relationships shown'} · crow's-foot ends from the measured cardinality</span>
          <span className="spacer" />
          <button className="icon-btn" onClick={onClose} title="Close (Esc)">✕</button>
        </div>
        <div className="erd-layout">
          <aside className="erd-side">
            {focus && (
              <div className="seg" title="How far from the table to go">
                {[1, 2].map((d) => <button key={d} className={depth === d ? 'active' : ''} onClick={() => setDepth(d)}>{d === 1 ? 'Direct links' : '2 hops'}</button>)}
              </div>
            )}
            <label className="check small">min confidence
              <select value={minConf} onChange={(e) => setMinConf(Number(e.target.value))}>{[0, 0.6, 0.7, 0.8, 0.9].map((x) => <option key={x} value={x}>{x}</option>)}</select></label>
            <input placeholder="Filter entities…" value={f} onChange={(e) => setF(e.target.value)} />
            <div className="small erd-sel">
              <b>{selected.length}</b> of {candidates.length} entities
              <span className="spacer" />
              <button className="link small" onClick={() => setMany(shownList.map((c) => c.k), true)}>all{f ? ' shown' : ''}</button>
              <button className="link small" onClick={() => setMany(shownList.filter((c) => c.k !== focus).map((c) => c.k), false)}>none</button>
            </div>
            <ul className="erd-list">
              {!allRels && <li className="muted small">Loading relationships…</li>}
              {allRels && candidates.length === 0 && <li className="muted small">No relationships at this confidence.</li>}
              {shownList.map((c) => (
                <li key={c.k} className={excluded.has(c.k) ? 'off' : ''}>
                  <label className="check">
                    <input type="checkbox" checked={!excluded.has(c.k)} onChange={() => toggle(c.k)} />
                    <span className="mono">{c.k}</span>
                  </label>
                  <span className="muted small" title="Links to other entities in the list">{c.k === focus ? '★' : c.hop === 2 ? '2 hops · ' : ''}{c.n}</span>
                  {onOpenTable && <button className="link small" title="Open this table" onClick={() => { const [s, t] = c.k.split('.'); onClose(); onOpenTable(s, t) }}>open</button>}
                </li>
              ))}
            </ul>
          </aside>
          <section className="erd-main">
            <div className="subbar">
              <button className="btn primary" onClick={generate} disabled={busy || selected.length === 0}>{busy ? 'Drawing…' : dirty && svg ? 'Update diagram' : 'Generate'}</button>
              {res && <span className="muted small">{fmt.n(res.entities)} entities · {fmt.n(res.links)} links{dirty && svg ? ' · selection changed' : ''}</span>}
              {selected.length > AUTO_MAX && dirty && <span className="muted small">{selected.length} entities – click Generate (large diagrams take a moment)</span>}
              <span className="spacer" />
              <div className="seg">
                {Object.entries(LAYOUTS).map(([k, v]) => <button key={k} title={v.title} className={layout === k ? 'active' : ''} onClick={() => setLayout(k)}>{v.label}</button>)}
              </div>
              <div className="seg" title="Direction">
                {[['TB', '↓'], ['LR', '→']].map(([k, l]) => <button key={k} title={k === 'TB' ? 'Top to bottom' : 'Left to right'} className={dir === k ? 'active' : ''} onClick={() => setDir(k)}>{l}</button>)}
              </div>
              <div className="seg" title="Zoom">
                <button onClick={() => setZoom((z) => Math.max(0.2, +(z / 1.25).toFixed(2)))}>−</button>
                <button onClick={() => setZoom(1)} title="100%">{Math.round(zoom * 100)}%</button>
                <button onClick={fit} title="Fit to the window">fit</button>
                <button onClick={() => setZoom((z) => Math.min(4, +(z * 1.25).toFixed(2)))}>+</button>
              </div>
              <button className="btn" disabled={!res} onClick={() => download(res.text, `${base}.mmd`, 'text/plain')} title="Mermaid source: paste into Markdown, Mermaid Live, a wiki or a whiteboard">⤓ .mmd</button>
              <button className="btn" disabled={!svg} onClick={() => download(svg, `${base}.svg`, 'image/svg+xml')} title="The picture, for slides and documents">⤓ .svg</button>
              <button className="btn" disabled={!svg || !res?.model} onClick={drawio}
                title="Editable diagram for draw.io / diagrams.net (also the VS Code and Confluence plugins): same layout, move boxes by hand and the lines follow">⤓ draw.io</button>
              <button className="link small" disabled={!res} onClick={() => copy(res.text, 'Mermaid ER diagram copied')}>copy Mermaid</button>
            </div>
            {err && <div className="error">{err}</div>}
            <div className="erd-canvas" ref={canvas}>
              {svg ? <div className="erd-svg" style={{ zoom }} dangerouslySetInnerHTML={{ __html: svg }} />
                : <div className="muted pad">{busy ? 'Drawing…' : selected.length ? 'Click Generate to draw the diagram.' : 'Tick the entities to include.'}</div>}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
