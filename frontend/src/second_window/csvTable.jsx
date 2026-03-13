import React, { useRef, useEffect } from 'react'
import { FileJson, Check, X } from 'lucide-react'
import { useVirtualizer } from '@tanstack/react-virtual'
import './csvTable.css'

const KIND_BG = {
  fixed:    'rgba(16,185,129,0.13)',
  warning:  'rgba(245,158,11,0.13)',
  critical: 'rgba(239,68,68,0.13)',
}
const KIND_BORDER = {
  fixed:    '#10b981',
  warning:  '#f59e0b',
  critical: '#ef4444',
}
const KIND_TEXT = {
  fixed:    '#10b981',
  warning:  '#f59e0b',
  critical: '#ef4444',
}

const ISSUE_BG = {
  critical: 'rgba(239,68,68,0.09)',
  error:    'rgba(239,68,68,0.09)',
  warning:  'rgba(245,158,11,0.09)',
  info:     'rgba(6,182,212,0.09)',
}
const ISSUE_TEXT = {
  critical: '#ef4444',
  error:    '#ef4444',
  warning:  '#f59e0b',
  info:     '#06b6d4',
}

function severityRank(s) {
  if (s === 'critical') return 4
  if (s === 'error') return 3
  if (s === 'warning') return 2
  return 1
}

function CsvTable({ csvRows, headers, issues = [], pendingChanges = [], onCellEdit, focusedRow, onAcceptChange, onDenyChange, searchQuery }) {
  // 1. New Ref specifically for the scrolling container
  const parentRef = useRef(null)

  useEffect(() => {
    // If a focused row is selected, tell the virtualizer to scroll to it
    if (focusedRow !== null && rowVirtualizer) {
      rowVirtualizer.scrollToIndex(focusedRow, { align: 'center', behavior: 'smooth' })
    }
  }, [focusedRow])

  if (!csvRows || csvRows.length === 0) {
    return (
      <div className="csv-table-card">
        <h3 className="csv-table-heading"><FileJson size={18} /> Dataset Editor</h3>
        <div className="csv-table-empty"><div className="csv-table-empty-title">No data loaded</div></div>
      </div>
    )
  }

  const cellIssueMap = {}
  for (const issue of issues) {
    if (!issue.affected_cells) continue
    for (const cell of issue.affected_cells) {
      const key = `${cell.column}::${cell.row}`
      if (!cellIssueMap[key] || severityRank(issue.severity) > severityRank(cellIssueMap[key])) {
        cellIssueMap[key] = issue.severity
      }
    }
  }

  const changeMap = {}
  for (const ch of pendingChanges) {
    const key = `${ch.column}::${ch.row}`
    changeMap[key] = ch
  }

  const rowHasChange = {}
  for (const ch of pendingChanges) {
    rowHasChange[ch.row] = rowHasChange[ch.row] || ch.kind
    if (ch.kind === 'critical') rowHasChange[ch.row] = 'critical'
    else if (ch.kind === 'warning' && rowHasChange[ch.row] !== 'critical') rowHasChange[ch.row] = 'warning'
    else if (!rowHasChange[ch.row]) rowHasChange[ch.row] = 'fixed'
  }

  // 2. Filter the rows before passing to virtualizer
  const filteredRows = csvRows.filter(row => {
    if (!searchQuery) return true
    return Object.values(row).some(value => {
      if (value === null || value === undefined) return false
      return String(value).toLowerCase().includes(searchQuery.toLowerCase())
    })
  })

  // 3. Initialize the Virtualizer Engine
  const rowVirtualizer = useVirtualizer({
    count: filteredRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40, // Estimated pixel height of one row
    overscan: 10,           // Render 10 invisible rows above/below for smooth scrolling
  })

  const virtualItems = rowVirtualizer.getVirtualItems()
  
  // 4. Calculate spacer heights to perfectly mimic the native scrollbar
  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0
  const paddingBottom = virtualItems.length > 0 
    ? rowVirtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end 
    : 0

  return (
    <div className="csv-table-card">
      <h3 className="csv-table-heading">
        <FileJson size={18} /> Dataset Editor ({csvRows.length} rows)
        {pendingChanges.length > 0 && (
          <span style={{ marginLeft: '12px', fontSize: '11px', fontWeight: 600, color: '#f59e0b', background: 'rgba(245,158,11,0.12)', padding: '2px 8px', borderRadius: '4px' }}>
            {pendingChanges.length} pending changes
          </span>
        )}
      </h3>
      
      {/* 5. Attach the parentRef to the scrollable div */}
      <div className="csv-table-scroll" ref={parentRef}>
        <table className="csv-table">
          <thead>
            <tr>
              <th className="csv-th csv-th-actions"></th>
              <th className="csv-th csv-th-idx">#</th>
              {headers.map(col => <th key={col} className="csv-th">{col}</th>)}
            </tr>
          </thead>
          <tbody>
            
            {/* Top Spacer Row (Pushes the visible rows down into the viewport) */}
            {paddingTop > 0 && (
              <tr><td style={{ height: paddingTop, padding: 0, border: 0 }} colSpan={headers.length + 2} /></tr>
            )}

            {/* 6. Map over virtualItems instead of all rows */}
            {virtualItems.map((virtualRow) => {
              const rowIdx = virtualRow.index
              const row = filteredRows[rowIdx]
              const rowKind = rowHasChange[rowIdx]
              const rowChanges = pendingChanges.filter(c => c.row === rowIdx)

              return (
                <tr
                  key={virtualRow.key}
                  className="csv-tr"
                  data-index={virtualRow.index}
                  ref={rowVirtualizer.measureElement} // Crucial: Measures row height dynamically
                  style={{
                    ...(focusedRow === rowIdx ? { outline: '2px solid #3b82f6', outlineOffset: '-2px', backgroundColor: 'rgba(59,130,246,0.1)' } : {}),
                    ...(rowKind ? { borderLeft: `3px solid ${KIND_BORDER[rowKind]}` } : {}),
                  }}
                >
                  <td className="csv-td csv-td-actions">
                    {rowChanges.length > 0 && (
                      <div className="row-action-btns">
                        <button className="row-accept-btn" title="Keep all changes on this row" onClick={() => rowChanges.forEach(c => onAcceptChange && onAcceptChange(c))}><Check size={11} /></button>
                        <button className="row-deny-btn" title="Deny all changes on this row" onClick={() => rowChanges.forEach(c => onDenyChange && onDenyChange(c))}><X size={11} /></button>
                      </div>
                    )}
                  </td>
                  <td className="csv-td csv-td-idx">{rowIdx + 1}</td>
                  {headers.map((col, vidx) => {
                    const change = changeMap[`${col}::${rowIdx}`]
                    const issueSev = cellIssueMap[`${col}::${rowIdx}`]
                    const bg = change ? KIND_BG[change.kind] : (issueSev ? ISSUE_BG[issueSev] : undefined)

                    return (
                      <td key={vidx} className="csv-td" style={bg ? { background: bg } : undefined}>
                        {change ? (
                          <div className="cell-change-wrap">
                            <div className="cell-change-inner">
                              {change.kind !== 'critical' && change.new_value !== '' && (
                                <div className="cell-change-values">
                                  {change.old_value !== '' && <span className="cell-old-val">{change.old_value}</span>}
                                  <span className="cell-arrow">→</span>
                                  <span className="cell-new-val" style={{ color: KIND_TEXT[change.kind] }}>{change.new_value}</span>
                                </div>
                              )}
                              {(change.kind === 'critical' || change.new_value === '') && (
                                <div className="cell-change-values">
                                  <span className="cell-old-val" style={{ color: '#ef4444' }}>{change.old_value || row[col] || '—'}</span>
                                  <span style={{ fontSize: '9px', color: '#ef4444', marginLeft: '4px', fontWeight: 700 }}>⚠ REVIEW</span>
                                </div>
                              )}
                              <div className="cell-change-actions">
                                {(change.kind !== 'critical' && change.new_value !== '') && (
                                  <button className="cell-accept-btn" title="Keep change" onClick={() => onAcceptChange && onAcceptChange(change)}><Check size={10} /></button>
                                )}
                                <button className="cell-deny-btn" title="Deny change" onClick={() => onDenyChange && onDenyChange(change)}><X size={10} /></button>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <input
                              type="text"
                              value={row[col] || ''}
                              onChange={(e) => onCellEdit && onCellEdit(rowIdx, col, e.target.value)}
                              style={{ background: 'transparent', border: 'none', color: 'inherit', width: '100%', outline: 'none', fontSize: 'inherit', fontFamily: 'inherit' }}
                            />
                            {issueSev && <span className="csv-cell-badge" style={{ color: ISSUE_TEXT[issueSev], flexShrink: 0 }}>{issueSev}</span>}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}

            {/* Bottom Spacer Row (Fools the browser into rendering a giant scrollbar) */}
            {paddingBottom > 0 && (
              <tr><td style={{ height: paddingBottom, padding: 0, border: 0 }} colSpan={headers.length + 2} /></tr>
            )}

          </tbody>
        </table>
      </div>
    </div>
  )
}

export default CsvTable