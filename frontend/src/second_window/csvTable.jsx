import React, { useRef, useEffect } from 'react';
import { FileJson } from 'lucide-react';
import './csvTable.css';

const SEVERITY_COLORS = {
    critical: 'rgba(239,68,68,0.15)',
    error: 'rgba(239,68,68,0.15)',
    warning: 'rgba(245,158,11,0.15)',
    info: 'rgba(6,182,212,0.15)',
};

const SEVERITY_TEXT = {
    critical: '#ef4444',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#06b6d4',
};

function CsvTable({ csvRows, headers, issues = [], onCellEdit, focusedRow }) {
    // Reference object to store all our HTML rows for auto-scrolling
    const rowRefs = useRef({});

    // Watch for changes to focusedRow and trigger scroll
    useEffect(() => {
        if (focusedRow !== null && rowRefs.current[focusedRow]) {
            rowRefs.current[focusedRow].scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
            });
        }
    }, [focusedRow]);

    if (!csvRows || csvRows.length === 0) {
        return (
            <div className="csv-table-card">
                <h3 className="csv-table-heading">
                    <FileJson size={18} /> Dataset Editor
                </h3>
                <div className="csv-table-empty">
                    <div className="csv-table-empty-title">No data loaded</div>
                </div>
            </div>
        );
    }

    // Build a lookup map for highlighting specific cells
    const cellSeverityMap = {};
    if (issues.length > 0) {
        for (const issue of issues) {
            if (issue.affected_cells && issue.affected_cells.length > 0) {
                for (const cell of issue.affected_cells) {
                    const key = `${cell.column}::${cell.row}`;
                    if (!cellSeverityMap[key] || severityRank(issue.severity) > severityRank(cellSeverityMap[key])) {
                        cellSeverityMap[key] = issue.severity;
                    }
                }
            }
        }
    }

    return (
        <div className="csv-table-card">
            <h3 className="csv-table-heading">
                <FileJson size={18} /> Dataset Editor ({csvRows.length} rows)
            </h3>
            <div className="csv-table-scroll">
                <table className="csv-table">
                    <thead>
                        <tr>
                            <th className="csv-th csv-th-idx">#</th>
                            {headers.map(col => (
                                <th key={col} className="csv-th">{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {csvRows.map((row, idx) => (
                            <tr 
                                key={idx} 
                                className="csv-tr"
                                ref={(el) => (rowRefs.current[idx] = el)} 
                                style={focusedRow === idx ? { outline: '2px solid #3b82f6', outlineOffset: '-2px', backgroundColor: 'rgba(59, 130, 246, 0.1)' } : {}} 
                            >
                                <td className="csv-td csv-td-idx">{idx + 1}</td>
                                {headers.map((col, vidx) => {
                                    const severity = cellSeverityMap[`${col}::${idx}`] || null;
                                    return (
                                        <td
                                            key={vidx}
                                            className="csv-td"
                                            style={severity ? { background: SEVERITY_COLORS[severity] } : undefined}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                <input 
                                                    type="text"
                                                    value={row[col] || ''}
                                                    onChange={(e) => onCellEdit && onCellEdit(idx, col, e.target.value)}
                                                    style={{
                                                        background: 'transparent',
                                                        border: 'none',
                                                        color: 'inherit',
                                                        width: '100%',
                                                        outline: 'none',
                                                        fontSize: 'inherit',
                                                        fontFamily: 'inherit'
                                                    }}
                                                />
                                                {severity && (
                                                    <span className="csv-cell-badge" style={{ color: SEVERITY_TEXT[severity], flexShrink: 0 }}>
                                                        {severity}
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function severityRank(s) {
    if (s === 'critical') return 4;
    if (s === 'warning') return 2;
    if (s === 'info') return 1;
    return 0;
}

export default CsvTable;