import React from 'react';
import { Database, AlertTriangle, CheckCircle, Info as InfoIcon } from 'lucide-react';
import './info.css';

const CATEGORY_LABELS = {
    completeness: 'Completeness',
    uniqueness: 'Uniqueness',
    consistency: 'Consistency',
    accuracy: 'Accuracy',
    format: 'Format',
};

function scoreColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 50) return '#f59e0b';
    return '#ef4444';
}

function InfoPanel({ fileName, headers, rowCount, analysisData }) {
    const hasAnalysis = analysisData && analysisData.overall_quality_score > 0;

    const issueCountBySeverity = { info: 0, warning: 0, critical: 0, error: 0 };
    if (analysisData?.issues) {
        for (const issue of analysisData.issues) {
            if (issueCountBySeverity[issue.severity] !== undefined) {
                issueCountBySeverity[issue.severity]++;
            }
        }
    }

    const overallScore = analysisData?.overall_quality_score ?? 0;
    const circumference = 2 * Math.PI * 38; // r=38
    const dashOffset = circumference - (circumference * overallScore) / 100;

    return (
        <div className="info-panel">
            {/* Dataset Meta */}
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

            {/* Quality Score */}
            <div className="info-card info-card-center">
                <h4 className="info-card-title">Quality Score</h4>
                {hasAnalysis ? (
                    <div className="info-score-ring-wrap">
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
                                style={{ transition: 'stroke-dashoffset 0.6s ease' }}
                            />
                        </svg>
                        <div className="info-score-label" style={{ color: scoreColor(overallScore) }}>
                            {overallScore}
                        </div>
                    </div>
                ) : (
                    <div className="info-no-data">No analysis</div>
                )}
            </div>

            {/* Category Breakdown */}
            {hasAnalysis && analysisData.category_breakdown && (
                <div className="info-card">
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

            {/* Issues Summary */}
            {hasAnalysis && (
                <div className="info-card">
                    <h4 className="info-card-title">Issues</h4>
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

            {/* Executive Summary */}
            {hasAnalysis && analysisData.executive_summary && (
                <div className="info-card">
                    <h4 className="info-card-title">Summary</h4>
                    <p className="info-summary-text">{analysisData.executive_summary}</p>
                </div>
            )}
        </div>
    );
}

export default InfoPanel;
