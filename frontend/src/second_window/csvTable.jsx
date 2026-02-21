import React from 'react';
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

function CsvTable({ csvRows, headers, issues = [] }) {
    if (!csvRows || csvRows.length === 0) {
        return (
            <div className="csv-table-card">
                <h3 className="csv-table-heading">
                    <FileJson size={18} />
                    Dataset Preview
                </h3>
                <div className="csv-table-empty">
                    <div className="csv-table-empty-title">No data loaded</div>
                    <div className="csv-table-empty-sub">Upload a CSV file to see the preview.</div>
                </div>
            </div>
        );
    }

    // Build a lookup: { "col::rowIdx" => severity }
    const cellSeverityMap = {};
    if (issues.length > 0) {
        for (const issue of issues) {
            // Support affected_cells format from backend: [{row, column}]
            if (issue.affected_cells && issue.affected_cells.length > 0) {
                for (const cell of issue.affected_cells) {
                    const key = `${cell.column}::${cell.row}`;
                    if (!cellSeverityMap[key] || severityRank(issue.severity) > severityRank(cellSeverityMap[key])) {
                        cellSeverityMap[key] = issue.severity;
                    }
                }
            }
            // Fallback: column list + row_indices (legacy)
            else if (issue.column && issue.row_indices) {
                for (const col of issue.column) {
                    for (const rowIdx of issue.row_indices) {
                        const key = `${col}::${rowIdx}`;
                        if (!cellSeverityMap[key] || severityRank(issue.severity) > severityRank(cellSeverityMap[key])) {
                            cellSeverityMap[key] = issue.severity;
                        }
                    }
                }
            }
        }
    }

    return (
        <div className="csv-table-card">
            <h3 className="csv-table-heading">
                <FileJson size={18} />
                Dataset Preview ({csvRows.length} rows)
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
                        {csvRows.slice(0, 200).map((row, idx) => (
                            <tr key={idx} className="csv-tr">
                                <td className="csv-td csv-td-idx">{idx + 1}</td>
                                {headers.map((col, vidx) => {
                                    const severity = cellSeverityMap[`${col}::${idx}`] || null;
                                    return (
                                        <td
                                            key={vidx}
                                            className="csv-td"
                                            style={severity ? { background: SEVERITY_COLORS[severity] } : undefined}
                                        >
                                            <span className="csv-cell-text">{row[col] || '—'}</span>
                                            {severity && (
                                                <span className="csv-cell-badge" style={{ color: SEVERITY_TEXT[severity] }}>
                                                    {severity}
                                                </span>
                                            )}
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
    if (s === 'error') return 3;
    if (s === 'warning') return 2;
    if (s === 'info') return 1;
    return 0;
}

export default CsvTable;
