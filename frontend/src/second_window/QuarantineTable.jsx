import React, { useState, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Check, X, Merge, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'

const TBD = 'TO_BE_DETERMINED'

const REASON_COL = '_issue_reason'
const ID_COL     = '_row_id'

/* ─── helpers ─────────────────────────────────────────────────────────────── */

function cellStyle(value) {
  if (value === TBD)
    return { background: 'rgba(239,68,68,0.15)', color: '#fca5a5', fontWeight: 700 }
  return {}
}

/* ─── ReasonBadge ──────────────────────────────────────────────────────────── */
function ReasonBadge({ reason }) {
  const parts = reason ? reason.split(';').map(r => r.trim()).filter(Boolean) : []
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: 350 }}>
      {parts.map((p, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'flex-start', gap: 6,
          background: 'rgba(239,68,68,0.08)', color: '#fca5a5',
          fontSize: 11, padding: '6px 8px', borderRadius: 6,
          lineHeight: '1.4', whiteSpace: 'normal', // Allows text to wrap nicely
        }}>
          <AlertTriangle size={12} style={{ marginTop: '2px', flexShrink: 0 }} /> 
          <span>{p}</span>
        </div>
      ))}
    </div>
  )
}

/* ─── QuarantineTable ──────────────────────────────────────────────────────── */
export default function QuarantineTable({
  rows,
  headers,           // includes _row_id and _issue_reason from backend
  onMergeSelected,
  onMergeAll,
  onCellEdit,        // (rowIndex, col, value) — edits quarantine rows
}) {
  const [selected, setSelected]   = useState(new Set())
  const parentRef                 = useRef(null)

  /* derive display headers */
  const dataHeaders = headers.filter(h => h !== ID_COL && h !== REASON_COL)

  const rowVirtualizer = useVirtualizer({
    count:           rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize:    () => 44,
    overscan:        8,
  })
  const virtualItems = rowVirtualizer.getVirtualItems()
  const paddingTop   = virtualItems.length > 0 ? virtualItems[0].start : 0
  const paddingBottom = virtualItems.length > 0
    ? rowVirtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end
    : 0

  /* selection helpers */
  const toggleRow = (idx) => setSelected(prev => {
    const next = new Set(prev)
    next.has(idx) ? next.delete(idx) : next.add(idx)
    return next
  })
  const allSelected   = rows.length > 0 && selected.size === rows.length
  const toggleAll     = () => setSelected(allSelected ? new Set() : new Set(rows.map((_, i) => i)))
  const selectedCount = selected.size

  if (!rows || rows.length === 0) {
    return (
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: 10, color: '#64748b',
        background: 'linear-gradient(180deg,#0d1526 0%,#111b2e 100%)',
        borderRadius: 12, border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <Check size={36} color="#10b981" />
        <div style={{ fontSize: 16, fontWeight: 700, color: '#10b981' }}>No quarantined rows</div>
        <div style={{ fontSize: 13 }}>All rows passed auto-fix checks.</div>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'linear-gradient(180deg,#1a0d0d 0%,#1c1018 100%)',
      borderRadius: 12, border: '1px solid rgba(239,68,68,0.18)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.35)', padding: 16, gap: 10,
    }}>

      {/* toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <AlertTriangle size={16} color="#ef4444" />
        <span style={{ fontWeight: 700, color: '#fca5a5', fontSize: 14 }}>
          Quarantined — {rows.length} row{rows.length !== 1 ? 's' : ''} need attention
        </span>
        <div style={{ flex: 1 }} />

        {selectedCount > 0 && (
          <button
            onClick={() => { onMergeSelected([...selected]); setSelected(new Set()) }}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 8,
              border: '1px solid #8b5cf6', cursor: 'pointer', fontWeight: 700,
              background: 'rgba(139,92,246,0.15)', color: '#c4b5fd', fontSize: 12,
            }}
          >
            <Merge size={13} /> Merge {selectedCount} selected
          </button>
        )}

        <button
          onClick={onMergeAll}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 8,
            border: '1px solid #10b981', cursor: 'pointer', fontWeight: 700,
            background: 'rgba(16,185,129,0.12)', color: '#6ee7b7', fontSize: 12,
          }}
        >
          <Check size={13} /> Merge All into Clean
        </button>
      </div>

      {/* note */}
      <div style={{
        fontSize: 11, color: '#94a3b8', background: 'rgba(239,68,68,0.06)',
        borderRadius: 6, padding: '6px 10px', flexShrink: 0,
      }}>
        Cells showing <span style={{ color: '#fca5a5', fontWeight: 700 }}>TO_BE_DETERMINED</span> must
        be filled before merging back.  Edit them directly in the table below, then click Merge.
      </div>

      {/* virtualised table */}
      <div ref={parentRef} style={{
        flex: 1, overflow: 'auto', borderRadius: 8,
        border: '1px solid rgba(255,255,255,0.04)',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, color: '#cbd5e1' }}>
          <thead>
            <tr>
              {/* select-all */}
              <th style={thStyle}>
                <input type="checkbox" checked={allSelected} onChange={toggleAll}
                  style={{ accentColor: '#8b5cf6', cursor: 'pointer' }} />
              </th>
              <th style={{ ...thStyle, width: 36 }}>#</th>
              <th style={{ ...thStyle, minWidth: 200, background: 'rgba(239,68,68,0.12)', color: '#fca5a5' }}>
                Issue Reason
              </th>
              {dataHeaders.map(col => (
                <th key={col} style={thStyle}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paddingTop > 0 && (
              <tr><td colSpan={dataHeaders.length + 3}
                style={{ height: paddingTop, padding: 0, border: 0 }} /></tr>
            )}
            {virtualItems.map(vr => {
              const rowIdx = vr.index
              const row    = rows[rowIdx]
              const isSel  = selected.has(rowIdx)
              return (
                <tr
                  key={vr.key}
                  data-index={vr.index}
                  ref={rowVirtualizer.measureElement}
                  style={{
                    background: isSel
                      ? 'rgba(139,92,246,0.1)'
                      : rowIdx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                    borderLeft: '3px solid rgba(239,68,68,0.4)',
                    cursor: 'pointer',
                    transition: 'background 120ms',
                  }}
                  onClick={() => toggleRow(rowIdx)}
                >
                  {/* checkbox */}
                  <td style={tdStyle} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={isSel}
                      onChange={() => toggleRow(rowIdx)}
                      style={{ accentColor: '#8b5cf6', cursor: 'pointer' }} />
                  </td>
                  {/* row number */}
                  <td style={{ ...tdStyle, color: '#475569', fontSize: 10, textAlign: 'center' }}>
                    {rowIdx + 1}
                  </td>
                  {/* reason column */}
                  <td style={{ ...tdStyle, background: 'rgba(239,68,68,0.05)' }}
                    onClick={e => e.stopPropagation()}>
                    <ReasonBadge reason={row[REASON_COL]} />
                  </td>
                  {/* data cells */}
                  {dataHeaders.map((col, ci) => {
                    const val   = row[col] ?? ''
                    const isTbd = val === TBD
                    return (
                      <td key={ci} style={{ ...tdStyle, ...cellStyle(val) }}
                        onClick={e => e.stopPropagation()}>
                        <input
                          type="text"
                          value={val}
                          onChange={e => onCellEdit && onCellEdit(rowIdx, col, e.target.value)}
                          placeholder={isTbd ? '← fill me in' : ''}
                          style={{
                            background: 'transparent', border: 'none',
                            color: isTbd ? '#fca5a5' : 'inherit',
                            fontWeight: isTbd ? 700 : 'inherit',
                            width: '100%', outline: 'none',
                            fontSize: 'inherit', fontFamily: 'inherit',
                          }}
                        />
                      </td>
                    )
                  })}
                </tr>
              )
            })}
            {paddingBottom > 0 && (
              <tr><td colSpan={dataHeaders.length + 3}
                style={{ height: paddingBottom, padding: 0, border: 0 }} /></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const thStyle = {
  position: 'sticky', top: 0, zIndex: 2,
  background: '#1a0d0d',
  padding: '8px 10px', textAlign: 'left',
  fontSize: 11, fontWeight: 700, color: '#94a3b8',
  textTransform: 'uppercase', letterSpacing: '0.5px',
  borderBottom: '2px solid rgba(239,68,68,0.3)',
  whiteSpace: 'nowrap',
}

const tdStyle = {
  padding: '10px 12px', // Increased padding for breathability
  borderBottom: '1px solid rgba(255,255,255,0.06)',
  maxWidth: 250, 
  overflow: 'hidden',
  textOverflow: 'ellipsis', 
  // Change to 'normal' to allow wrapping, or keep 'nowrap' if you prefer a strict grid
  whiteSpace: 'normal', 
  verticalAlign: 'top', // Align to top because reason badges might be tall
  lineHeight: '1.5',
}
