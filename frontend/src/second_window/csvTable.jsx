import React, { useRef, useEffect } from 'react'
import { FileJson, Check, X } from 'lucide-react'
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

function CsvTable({ csvRows, headers, issues = [], pendingChanges = [], onCellEdit, focusedRow, onAcceptChange, onDenyChange }) {
  const rowRefs = useRef({})

  useEffect(() => {
    if (focusedRow !== null && rowRefs.current[focusedRow]) {
      rowRefs.current[focusedRow].scrollIntoView({ behavior: 'smooth', block: 'center' })
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
      <div className="csv-table-scroll">
        <table className="csv-table">
          <thead>
            <tr>
              <th className="csv-th csv-th-actions"></th>
              <th className="csv-th csv-th-idx">#</th>
              {headers.map(col => <th key={col} className="csv-th">{col}</th>)}
            </tr>
          </thead>
          <tbody>
            {csvRows.map((row, idx) => {
              const rowKind = rowHasChange[idx]
              const rowChanges = pendingChanges.filter(c => c.row === idx)
              return (
                <tr
                  key={idx}
                  className="csv-tr"
                  ref={(el) => (rowRefs.current[idx] = el)}
                  style={{
                    ...(focusedRow === idx ? { outline: '2px solid #3b82f6', outlineOffset: '-2px', backgroundColor: 'rgba(59,130,246,0.1)' } : {}),
                    ...(rowKind ? { borderLeft: `3px solid ${KIND_BORDER[rowKind]}` } : {}),
                  }}
                >
                  <td className="csv-td csv-td-actions">
                    {rowChanges.length > 0 && (
                      <div className="row-action-btns">
                        <button
                          className="row-accept-btn"
                          title="Keep all changes on this row"
                          onClick={() => rowChanges.forEach(c => onAcceptChange && onAcceptChange(c))}
                        >
                          <Check size={11} />
                        </button>
                        <button
                          className="row-deny-btn"
                          title="Deny all changes on this row"
                          onClick={() => rowChanges.forEach(c => onDenyChange && onDenyChange(c))}
                        >
                          <X size={11} />
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="csv-td csv-td-idx">{idx + 1}</td>
                  {headers.map((col, vidx) => {
                    const change = changeMap[`${col}::${idx}`]
                    const issueSev = cellIssueMap[`${col}::${idx}`]
                    const bg = change ? KIND_BG[change.kind] : (issueSev ? ISSUE_BG[issueSev] : undefined)

                    return (
                      <td key={vidx} className="csv-td" style={bg ? { background: bg } : undefined}>
                        {change ? (
                          <div className="cell-change-wrap">
                            <div className="cell-change-inner">
                              {change.kind !== 'critical' && change.new_value !== '' && (
                                <div className="cell-change-values">
                                  {change.old_value !== '' && (
                                    <span className="cell-old-val">{change.old_value}</span>
                                  )}
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
                              onChange={(e) => onCellEdit && onCellEdit(idx, col, e.target.value)}
                              style={{ background: 'transparent', border: 'none', color: 'inherit', width: '100%', outline: 'none', fontSize: 'inherit', fontFamily: 'inherit' }}
                            />
                            {issueSev && (
                              <span className="csv-cell-badge" style={{ color: ISSUE_TEXT[issueSev], flexShrink: 0 }}>{issueSev}</span>
                            )}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default CsvTable