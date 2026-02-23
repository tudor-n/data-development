import React, { useState, useMemo } from 'react'
import { Database, AlertTriangle, Info as InfoIcon, ChevronLeft, ChevronRight, ArrowRight, ChevronDown, ChevronUp, Check, X } from 'lucide-react'
import './info.css'

const CATEGORY_LABELS = {
    completeness: 'Completeness',
    uniqueness: 'Uniqueness',
    consistency: 'Consistency',
    accuracy: 'Accuracy',
    format: 'Format',
}

function scoreColor(score) {
    if (score >= 80) return '#10b981'
    if (score >= 50) return '#f59e0b'
    return '#ef4444'
}

function IssueNavigatorCard({ issue, onIssueClick }) {
    const [currentIndex, setCurrentIndex] = useState(0)
    const affectedCells = issue.affected_cells || []
    const totalAffected = affectedCells.length
    const hasLinks = totalAffected > 0

    const handleCardClick = () => {
        if (hasLinks) onIssueClick(affectedCells[currentIndex].row)
    }

    const handlePrev = (e) => {
        e.stopPropagation()
        if (hasLinks) {
            const newIdx = currentIndex === 0 ? totalAffected - 1 : currentIndex - 1
            setCurrentIndex(newIdx)
            onIssueClick(affectedCells[newIdx].row)
        }
    }

    const handleNext = (e) => {
        e.stopPropagation()
        if (hasLinks) {
            const newIdx = (currentIndex + 1) % totalAffected
            setCurrentIndex(newIdx)
            onIssueClick(affectedCells[newIdx].row)
        }
    }

    const borderColor = scoreColor(issue.severity === 'critical' ? 0 : issue.severity === 'warning' ? 50 : 100)

    return (
        <div
            style={{
                background: 'rgba(255,255,255,0.03)',
                padding: '12px',
                borderRadius: '8px',
                borderLeft: `3px solid ${borderColor}`,
                cursor: hasLinks ? 'pointer' : 'default',
                transition: 'background 0.2s',
                display: 'flex',
                flexDirection: 'column'
            }}
            onClick={handleCardClick}
            onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
            onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
        >
            <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#e2e8f0', marginBottom: '4px' }}>
                {issue.inspector_name}
            </div>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '8px' }}>
                {issue.description}
            </div>
            <div style={{ fontSize: '12px', color: '#3b82f6', fontStyle: 'italic', marginBottom: hasLinks ? '12px' : '0' }}>
                💡 {issue.suggestion}
            </div>

            {hasLinks && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderTop: '1px solid rgba(255,255,255,0.1)',
                    paddingTop: '8px',
                    marginTop: 'auto'
                }}>
                    <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        Row {affectedCells[currentIndex].row + 1}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button
                            onClick={handlePrev}
                            style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '4px', color: '#fff', cursor: 'pointer', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
                            title="Previous Row"
                        >
                            <ChevronLeft size={14} />
                        </button>
                        <span style={{ fontSize: '11px', color: '#94a3b8', minWidth: '35px', textAlign: 'center' }}>
                            {currentIndex + 1} / {totalAffected}
                        </span>
                        <button
                            onClick={handleNext}
                            style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '4px', color: '#fff', cursor: 'pointer', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
                            title="Next Row"
                        >
                            <ChevronRight size={14} />
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}

function InfoPanel({ fileName, headers, rowCount, analysisData, originalScore, pendingChanges = [], onIssueClick, onAcceptAllChanges, onDenyAllChanges, isAnimatingScore }) {
    const hasAnalysis = analysisData && analysisData.overall_quality_score > 0
    const [isCategoriesExpanded, setIsCategoriesExpanded] = useState(false)

    const issueCountBySeverity = { info: 0, warning: 0, critical: 0, error: 0 }
    const uniqueAffectedRows = new Set()

    if (analysisData?.issues) {
        for (const issue of analysisData.issues) {
            if (issueCountBySeverity[issue.severity] !== undefined) {
                issueCountBySeverity[issue.severity] += (issue.count || 1)
            }

            if (issue.severity !== 'info') {
                if (issue.affected_cells) {
                    issue.affected_cells.forEach(cell => uniqueAffectedRows.add(cell.row))
                } else if (issue.row_indices) {
                    issue.row_indices.forEach(idx => uniqueAffectedRows.add(idx))
                }
            }
        }
    }

    const totalBrokenRows = uniqueAffectedRows.size
    const brokenPercentage = rowCount > 0 ? Math.round((totalBrokenRows / rowCount) * 100) : 0

    const overallScore = analysisData?.overall_quality_score ?? 0
    const circumference = 2 * Math.PI * 38
    const dashOffset = circumference - (circumference * overallScore) / 100

    const changeStats = useMemo(() => {
        let acceptableCount = 0
        let criticalCount = 0
        for (const change of pendingChanges) {
            if (change.kind === 'critical' || change.new_value === '') {
                criticalCount++
            } else {
                acceptableCount++
            }
        }
        return { acceptableCount, criticalCount }
    }, [pendingChanges])

    return (
        <div className="info-panel">
            <div className="info-card">
                <h4 className="info-card-title"><Database size={16} /> Dataset</h4>
                <div className="info-meta-grid">
                    <div className="info-meta-item">
                        <span className="info-meta-label">File</span>
                        <span className="info-meta-value" title={fileName}>{fileName || '—'}</span>
                    </div>
                    <div className="info-meta-item">
                        <span className="info-meta-label">Rows</span>
                        <span className="info-meta-value">{(rowCount ?? 0).toLocaleString()}</span>
                    </div>
                    <div className="info-meta-item">
                        <span className="info-meta-label">Columns</span>
                        <span className="info-meta-value">{(headers?.length ?? 0)}</span>
                    </div>
                </div>
            </div>

            <div className="info-card info-card-center">
                <div style={{ position: 'relative' }}>
                    <h4 className="info-card-title" style={{ justifyContent: 'center' }}>Quality Score</h4>
                    {hasAnalysis ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
                            {originalScore !== null && originalScore !== undefined && (
                                <>
                                    <div className={`info-score-ring-wrap ${isAnimatingScore ? 'animate-out' : ''}`} style={{ margin: 0 }}>
                                        <svg viewBox="0 0 90 90" className="info-score-ring">
                                            <circle cx="45" cy="45" r="38" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
                                            <circle
                                                cx="45" cy="45" r="38"
                                                fill="none"
                                                stroke={scoreColor(originalScore)}
                                                strokeWidth="6"
                                                strokeLinecap="round"
                                                strokeDasharray={circumference}
                                                strokeDashoffset={circumference - (circumference * originalScore) / 100}
                                                transform="rotate(-90 45 45)"
                                            />
                                        </svg>
                                        <div className="info-score-label" style={{ color: scoreColor(originalScore) }}>
                                            {originalScore}
                                        </div>
                                    </div>
                                    <div style={{ color: '#94a3b8', display: 'flex', animation: isAnimatingScore ? 'pulse 1.5s ease-in-out' : 'none' }}>
                                        <ArrowRight size={28} />
                                    </div>
                                </>
                            )}
                            <div className={`info-score-ring-wrap ${isAnimatingScore ? 'animate-in' : ''}`} style={{ margin: (originalScore !== null && originalScore !== undefined) ? 0 : '8px auto 4px' }}>
                                <svg viewBox="0 0 90 90" className="info-score-ring">
                                    <circle cx="45" cy="45" r="38" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
                                    <circle
                                        cx="45" cy="45" r="38"
                                        fill="none"
                                        stroke={scoreColor(overallScore)}
                                        strokeWidth="6"
                                        strokeLinecap="round"
                                        strokeDasharray={circumference}
                                        strokeDashoffset={dashOffset}
                                        transform="rotate(-90 45 45)"
                                        style={{ transition: 'stroke-dashoffset 1.5s cubic-bezier(0.34, 1.56, 0.64, 1)' }}
                                    />
                                </svg>
                                <div className="info-score-label" style={{ color: scoreColor(overallScore) }}>
                                    {overallScore}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="info-no-data">No analysis</div>
                    )}

                    {hasAnalysis && analysisData.category_breakdown && (
                        <button
                            onClick={() => setIsCategoriesExpanded(!isCategoriesExpanded)}
                            style={{
                                position: 'absolute',
                                bottom: '-8px',
                                right: '-8px',
                                background: 'transparent',
                                border: 'none',
                                color: '#94a3b8',
                                cursor: 'pointer',
                                padding: '4px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'color 0.2s'
                            }}
                            title={isCategoriesExpanded ? "Hide Categories" : "Show Categories"}
                            onMouseOver={(e) => e.currentTarget.style.color = '#e2e8f0'}
                            onMouseOut={(e) => e.currentTarget.style.color = '#94a3b8'}
                        >
                            {isCategoriesExpanded ? <ChevronUp size={24} /> : <ChevronDown size={24} />}
                        </button>
                    )}
                </div>

                {hasAnalysis && analysisData.category_breakdown && (
                    <div className={`info-categories-dropdown ${isCategoriesExpanded ? 'expanded' : ''}`} style={{ textAlign: 'left' }}>
                        <h4 className="info-card-title">Categories</h4>
                        <div className="info-category-list">
                            {Object.entries(analysisData.category_breakdown).map(([key, value]) => (
                                <div key={key} className="info-category-row">
                                    <span className="info-category-name">{CATEGORY_LABELS[key] || key}</span>
                                    <div className="info-bar-track">
                                        <div
                                            className="info-bar-fill"
                                            style={{ width: `${value}%`, background: scoreColor(value) }}
                                        />
                                    </div>
                                    <span className="info-category-val" style={{ color: scoreColor(value) }}>{value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {pendingChanges.length > 0 && (
                <div className="info-card" style={{ background: 'linear-gradient(180deg, rgba(139, 92, 246, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%)', borderColor: 'rgba(139, 92, 246, 0.3)' }}>
                    <h4 className="info-card-title" style={{ color: '#c4b5fd' }}>AI Suggestions ({pendingChanges.length})</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#94a3b8' }}>
                            <span>✓ Auto-Fixable: <strong style={{ color: '#10b981' }}>{changeStats.acceptableCount}</strong></span>
                            <span>⚠ Needs Review: <strong style={{ color: '#ef4444' }}>{changeStats.criticalCount}</strong></span>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                            onClick={onAcceptAllChanges}
                            disabled={changeStats.acceptableCount === 0}
                            style={{
                                flex: 1,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '6px',
                                padding: '10px 12px',
                                borderRadius: '8px',
                                border: 'none',
                                cursor: changeStats.acceptableCount > 0 ? 'pointer' : 'not-allowed',
                                fontWeight: 'bold',
                                backgroundColor: changeStats.acceptableCount > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.1)',
                                color: changeStats.acceptableCount > 0 ? '#10b981' : '#64748b',
                                transition: 'all 0.2s'
                            }}
                        >
                            <Check size={16} />
                            Keep All
                        </button>
                        <button
                            onClick={onDenyAllChanges}
                            style={{
                                flex: 1,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '6px',
                                padding: '10px 12px',
                                borderRadius: '8px',
                                border: 'none',
                                cursor: 'pointer',
                                fontWeight: 'bold',
                                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                color: '#ef4444',
                                transition: 'all 0.2s'
                            }}
                        >
                            <X size={16} />
                            Deny All
                        </button>
                    </div>
                </div>
            )}

            {hasAnalysis && (
                <div className="info-card">
                    <h4 className="info-card-title">Dataset Impact</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div>
                            <span style={{ fontSize: '24px', fontWeight: 'bold', color: totalBrokenRows > 0 ? '#ef4444' : '#10b981' }}>
                                {totalBrokenRows.toLocaleString()}
                            </span>
                            <span style={{ fontSize: '13px', color: '#94a3b8', marginLeft: '6px' }}>
                                / {(rowCount ?? 0).toLocaleString()} rows affected
                            </span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>
                            {brokenPercentage}% of your dataset requires cleaning.
                        </div>
                    </div>
                </div>
            )}

            {hasAnalysis && (
                <div className="info-card">
                    <h4 className="info-card-title">Detected Anomalies</h4>
                    <div className="info-issues-row">
                        <span className="info-issue-badge info-badge-error">
                            <AlertTriangle size={12} /> {issueCountBySeverity.critical + (issueCountBySeverity.error || 0)} Critical
                        </span>
                        <span className="info-issue-badge info-badge-warning">
                            <AlertTriangle size={12} /> {issueCountBySeverity.warning} Warnings
                        </span>
                        <span className="info-issue-badge info-badge-info">
                            <InfoIcon size={12} /> {issueCountBySeverity.info} Info
                        </span>
                    </div>
                </div>
            )}

            {hasAnalysis && analysisData.executive_summary && (
                <div className="info-card">
                    <h4 className="info-card-title">Summary</h4>
                    <p className="info-summary-text">{analysisData.executive_summary}</p>
                </div>
            )}

            {hasAnalysis && analysisData.issues && analysisData.issues.length > 0 && (
                <div className="info-card">
                    <h4 className="info-card-title">AI Action Plan</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
                        {analysisData.issues.map((issue, idx) => (
                            <IssueNavigatorCard
                                key={idx}
                                issue={issue}
                                onIssueClick={onIssueClick}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default InfoPanel