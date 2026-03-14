import React, { useState, useCallback, useEffect } from 'react'
import {
  ArrowLeft, Download, Undo, Redo, Wand2, Save,
  AlertTriangle, CheckCircle, FileDown, Layers,
} from 'lucide-react'

import DragAndDrop    from './first_window/dragAndDrop'
import LoginButtons   from './first_window/loginButtons'
import AuthModal      from './first_window/AuthModal'
import CsvTable       from './second_window/csvTable'
import QuarantineTable from './second_window/QuarantineTable'
import InfoPanel      from './second_window/info'
import SearchBar      from './second_window/SearchBar'
import './App.css'

const API_BASE = '/api/v1'

/* ─── CSV helpers ──────────────────────────────────────────────────────────── */
function parseCSV(csv) {
  const normalized = csv.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = []
  let current = '', inQuotes = false
  for (let i = 0; i < normalized.length; i++) {
    const char = normalized[i], next = normalized[i + 1]
    if (char === '"') {
      if (inQuotes && next === '"') { current += '"'; i++ }
      else inQuotes = !inQuotes
    } else if (char === '\n' && !inQuotes) {
      if (current.trim()) lines.push(current)
      current = ''
    } else { current += char }
  }
  if (current.trim()) lines.push(current)
  return lines
}

function parseCSVLine(line) {
  const fields = []
  let current = '', inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const char = line[i], next = line[i + 1]
    if (char === '"') {
      if (inQuotes && next === '"') { current += '"'; i++ }
      else inQuotes = !inQuotes
    } else if (char === ',' && !inQuotes) {
      fields.push(current); current = ''
    } else { current += char }
  }
  fields.push(current)
  return fields.map(f => f.replace(/^"|"$/g, '').trim())
}

function encodeCSVLine(fields) {
  return fields.map(f => {
    const s = String(f || '')
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"` : s
  }).join(',')
}

function triggerDownload(content, filename, mimeType = 'text/csv;charset=utf-8;') {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a); a.click()
  document.body.removeChild(a); URL.revokeObjectURL(url)
}

/* ─── Sheet Tab component ──────────────────────────────────────────────────── */
function SheetTab({ label, count, active, variant = 'clean', onClick }) {
  const colors = {
    clean:      { active: '#10b981', inactive: '#475569', bg: 'rgba(16,185,129,0.12)' },
    quarantine: { active: '#ef4444', inactive: '#475569', bg: 'rgba(239,68,68,0.12)' },
  }
  const c = colors[variant]
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '8px 20px', border: 'none', cursor: 'pointer',
        fontWeight: active ? 800 : 600, fontSize: 13,
        color: active ? c.active : c.inactive,
        background: active ? c.bg : 'transparent',
        borderTop: active ? `2px solid ${c.active}` : '2px solid transparent',
        borderLeft: '1px solid rgba(255,255,255,0.06)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        borderBottom: 'none',
        transition: 'all 160ms ease',
        borderRadius: '8px 8px 0 0',
      }}
    >
      {variant === 'clean'
        ? <CheckCircle size={14} />
        : <AlertTriangle size={14} />}
      {label}
      <span style={{
        background: active ? c.active : 'rgba(255,255,255,0.1)',
        color: active ? '#fff' : '#64748b',
        fontSize: 10, fontWeight: 700,
        padding: '1px 7px', borderRadius: 10,
        minWidth: 20, textAlign: 'center',
      }}>
        {count}
      </span>
    </button>
  )
}

/* ─── App ──────────────────────────────────────────────────────────────────── */
export default function App() {
  const [step, setStep]                 = useState('upload')
  const [csvRows, setCsvRows]           = useState([])
  const [csvHeaders, setCsvHeaders]     = useState([])
  const [fileName, setFileName]         = useState('')
  const [analysisData, setAnalysisData] = useState(null)
  const [originalScore, setOriginalScore] = useState(null)
  const [isLoading, setIsLoading]       = useState(false)
  const [isFixing, setIsFixing]         = useState(false)
  const [history, setHistory]           = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false)
  const [focusedRow, setFocusedRow]     = useState(null)
  const [pendingChanges, setPendingChanges] = useState([])
  const [isAnimatingScore, setIsAnimatingScore] = useState(false)
  const [searchQuery, setSearchQuery]   = useState('')

  // Sheet / quarantine state
  const [activeTab, setActiveTab]             = useState('clean')  // 'clean' | 'quarantine'
  const [quarantineRows, setQuarantineRows]   = useState([])
  const [quarantineHeaders, setQuarantineHeaders] = useState([])
  const [quarantineCSV, setQuarantineCSV]     = useState('')

  // Auth
  const [currentUser, setCurrentUser]     = useState(null)
  const [accessToken, setAccessToken]     = useState(null)
  const [authModalMode, setAuthModalMode] = useState(null)
  const [userHistory, setUserHistory]     = useState([])

  const authHeaders = useCallback(t => t ? { Authorization: `Bearer ${t}` } : {}, [])

  /* ── session restore ─────────────────────────────────────────────────────── */
  useEffect(() => {
    const tryRefresh = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
        if (!res.ok) return
        const { access_token } = await res.json()
        const meRes = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${access_token}` } })
        if (meRes.ok) { setCurrentUser(await meRes.json()); setAccessToken(access_token) }
      } catch { /**/ }
    }
    tryRefresh()
  }, [])

  const fetchUserHistory = useCallback(async (token) => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/history?limit=10`, { headers: authHeaders(token) })
      if (res.ok) setUserHistory(await res.json())
    } catch { /**/ }
  }, [authHeaders])

  useEffect(() => { if (accessToken) fetchUserHistory(accessToken) }, [accessToken, fetchUserHistory])

  const saveToHistory = useCallback(async (filename, content, rowCount, colCount) => {
    if (!accessToken) return
    try {
      await fetch(`${API_BASE}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders(accessToken) },
        body: JSON.stringify({
          filename, original_format: filename.split('.').pop().toLowerCase(),
          row_count: rowCount, column_count: colCount, file_content: content,
        }),
      })
      fetchUserHistory(accessToken)
    } catch { /**/ }
  }, [accessToken, authHeaders, fetchUserHistory])

  /* ── undo / redo ─────────────────────────────────────────────────────────── */
  const pushHistory = useCallback((rows, hist, idx) => {
    const newHist = hist.slice(0, idx + 1)
    newHist.push(rows)
    return { newHist, newIdx: newHist.length - 1 }
  }, [])

  const handleUndo = () => {
    if (historyIndex > 0) {
      const i = historyIndex - 1; setHistoryIndex(i); setCsvRows(history[i]); setHasUnsavedEdits(true)
    }
  }
  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const i = historyIndex + 1; setHistoryIndex(i); setCsvRows(history[i]); setHasUnsavedEdits(true)
    }
  }

  /* ── CSV reconstruction ──────────────────────────────────────────────────── */
  const buildCSVFile = () => {
    const csv = [encodeCSVLine(csvHeaders), ...csvRows.map(r => encodeCSVLine(csvHeaders.map(h => r[h] || '')))].join('\n')
    return { csv, file: new File([new Blob([csv], { type: 'text/csv' })], fileName, { type: 'text/csv' }) }
  }

  /* ── file accepted ───────────────────────────────────────────────────────── */
  const handleFileAccepted = async (fileOrContent, name, fromHistory = false) => {
    setIsLoading(true)
    const resetQuarantine = () => {
      setQuarantineRows([]); setQuarantineHeaders([]); setQuarantineCSV(''); setActiveTab('clean')
    }
    try {
      const ext   = name.split('.').pop().toLowerCase()
      const isCsv = ext === 'csv'

      const applyParsed = (headers, rows, csvText) => {
        setCsvHeaders(headers); setCsvRows(rows)
        setHistory([rows]); setHistoryIndex(0)
        setFileName(name); setPendingChanges([])
        resetQuarantine(); setStep('preview')
        if (!fromHistory) saveToHistory(name, csvText, rows.length, headers.length)
      }

      if (typeof fileOrContent === 'string') {
        const lines = parseCSV(fileOrContent)
        if (!lines.length) { alert('File is empty'); return }
        const headers = parseCSVLine(lines[0])
        const rows = lines.slice(1).map(line => {
          const vals = parseCSVLine(line); const obj = {}
          headers.forEach((h, i) => { obj[h] = vals[i] || '' }); return obj
        })
        applyParsed(headers, rows, fileOrContent)
        try {
          const fd = new FormData()
          fd.append('file', new File([fileOrContent], name, { type: 'text/csv' }))
          const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd })
          if (res.ok) setAnalysisData(await res.json())
        } catch { /**/ }
        return
      }

      if (isCsv) {
        const text    = await fileOrContent.text()
        const lines   = parseCSV(text)
        if (!lines.length) { alert('CSV file is empty'); return }
        const headers = parseCSVLine(lines[0])
        const rows = lines.slice(1).map(line => {
          const vals = parseCSVLine(line); const obj = {}
          headers.forEach((h, i) => { obj[h] = vals[i] || '' }); return obj
        })
        applyParsed(headers, rows, text)
        try {
          const fd = new FormData(); fd.append('file', fileOrContent)
          const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd })
          if (res.ok) setAnalysisData(await res.json())
        } catch { /**/ }
      } else {
        const fd = new FormData(); fd.append('file', fileOrContent)
        const parseRes = await fetch(`${API_BASE}/parse`, { method: 'POST', body: fd })
        if (!parseRes.ok) throw new Error(`Parse error: ${await parseRes.text()}`)
        const { headers, rows } = await parseRes.json()
        if (!headers?.length) { alert('File is empty or could not be parsed'); return }
        applyParsed(headers, rows, '')
        try {
          const fd2 = new FormData(); fd2.append('file', fileOrContent)
          const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd2 })
          if (res.ok) setAnalysisData(await res.json())
        } catch { /**/ }
      }
    } catch (err) {
      alert('Error: ' + err.message)
    } finally { setIsLoading(false) }
  }

  const handleHistoryItemClick = async (item) => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API_BASE}/history/${item.id}`, { headers: authHeaders(accessToken) })
      if (res.ok) {
        const detail = await res.json()
        if (detail.file_content) handleFileAccepted(detail.file_content, item.filename, true)
      }
    } catch { /**/ }
  }

  const handleBack = () => {
    setStep('upload'); setCsvRows([]); setCsvHeaders([]); setFileName('')
    setAnalysisData(null); setOriginalScore(null); setHasUnsavedEdits(false)
    setHistory([]); setHistoryIndex(-1); setFocusedRow(null); setPendingChanges([])
    setQuarantineRows([]); setQuarantineHeaders([]); setQuarantineCSV('')
    setActiveTab('clean'); setIsAnimatingScore(false)
  }

  /* ── cell edit ───────────────────────────────────────────────────────────── */
  const handleCellEdit = (rowIndex, col, newValue) => {
    const updated = [...csvRows]
    updated[rowIndex] = { ...updated[rowIndex], [col]: newValue }
    setCsvRows(updated); setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
    setHistory(newHist); setHistoryIndex(newIdx)
  }

  const handleQuarantineCellEdit = (rowIndex, col, newValue) => {
    const updated = [...quarantineRows]
    updated[rowIndex] = { ...updated[rowIndex], [col]: newValue }
    setQuarantineRows(updated)
  }

  /* ── re-analyse ──────────────────────────────────────────────────────────── */
  const handleReAnalyze = async () => {
    setIsLoading(true)
    try {
      const { file } = buildCSVFile()
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd })
      if (res.ok) {
        setAnalysisData(await res.json()); setHasUnsavedEdits(false)
        setOriginalScore(null); setPendingChanges([])
      } else { alert('Failed to re-analyse.') }
    } catch (err) { alert('Error: ' + err.message) } finally { setIsLoading(false) }
  }

  /* ── AUTO-FIX ────────────────────────────────────────────────────────────── */
  const handleAutoFix = async () => {
    setIsFixing(true); setIsAnimatingScore(true)
    const preFixScore = analysisData?.overall_quality_score ?? null
    try {
      const { file } = buildCSVFile()
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API_BASE}/autofix`, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Backend error: ${res.status} – ${await res.text()}`)

      const {
        cleaned_csv, changes,
        quarantine_csv, quarantine_count,
        quarantine_headers: qHeaders,
        quarantine_rows:    qRows,
      } = await res.json()

      // Apply clean rows
      const lines      = parseCSV(cleaned_csv)
      if (!lines.length) throw new Error('Empty response from server')
      const newHeaders = parseCSVLine(lines[0])
      const newRows    = lines.slice(1).map(line => {
        const vals = parseCSVLine(line); const obj = {}
        newHeaders.forEach((h, i) => { obj[h] = vals[i] || '' }); return obj
      })
      setCsvHeaders(newHeaders); setCsvRows(newRows)
      setPendingChanges(changes || [])
      const { newHist, newIdx } = pushHistory(newRows, history, historyIndex)
      setHistory(newHist); setHistoryIndex(newIdx)

      // Apply quarantine
      const hasQuarantine = quarantine_count > 0
      setQuarantineRows(qRows || [])
      setQuarantineHeaders(qHeaders || [])
      setQuarantineCSV(quarantine_csv || '')

      // Auto-switch to quarantine tab if there are quarantined rows
      if (hasQuarantine) setActiveTab('quarantine')

      // Re-analyse clean output
      try {
        const cfd = new FormData()
        cfd.append('file', new File([new Blob([cleaned_csv], { type: 'text/csv' })], fileName, { type: 'text/csv' }))
        const ar = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: cfd })
        if (ar.ok) {
          setAnalysisData(await ar.json()); setOriginalScore(preFixScore)
          setTimeout(() => setIsAnimatingScore(false), 1500)
        }
      } catch { setIsAnimatingScore(false) }
    } catch (err) {
      alert('Auto-Fix Error: ' + err.message); setIsAnimatingScore(false)
    } finally { setIsFixing(false) }
  }

  /* ── MERGE operations ────────────────────────────────────────────────────── */
  const _stripInternalCols = (row) => {
    const clean = { ...row }
    delete clean._row_id
    delete clean._issue_reason
    return clean
  }

  const handleMergeAll = useCallback(() => {
    const toMerge  = quarantineRows.map(_stripInternalCols)
    const merged   = [...csvRows, ...toMerge]
    setCsvRows(merged)
    setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(merged, history, historyIndex)
    setHistory(newHist); setHistoryIndex(newIdx)
    setQuarantineRows([]); setQuarantineHeaders([]); setQuarantineCSV('')
    setActiveTab('clean')
  }, [csvRows, quarantineRows, history, historyIndex, pushHistory])

  const handleMergeSelected = useCallback((selectedIndices) => {
    const idxSet  = new Set(selectedIndices)
    const toMerge = selectedIndices.map(i => _stripInternalCols(quarantineRows[i]))
    const remaining = quarantineRows.filter((_, i) => !idxSet.has(i))
    const merged    = [...csvRows, ...toMerge]

    setCsvRows(merged); setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(merged, history, historyIndex)
    setHistory(newHist); setHistoryIndex(newIdx)
    setQuarantineRows(remaining)

    // Rebuild quarantine CSV from remaining
    if (remaining.length > 0) {
      const dataHeaders = quarantineHeaders.filter(h => h !== '_row_id')
      const csv = [
        encodeCSVLine(dataHeaders),
        ...remaining.map(r => encodeCSVLine(dataHeaders.map(h => r[h] || ''))),
      ].join('\n')
      setQuarantineCSV(csv)
    } else {
      setQuarantineCSV(''); setActiveTab('clean')
    }
  }, [csvRows, quarantineRows, quarantineHeaders, history, historyIndex, pushHistory])

  /* ── change acceptance ───────────────────────────────────────────────────── */
  const handleAcceptChange = useCallback((change) => {
    if (change.kind === 'critical' || change.new_value === '') {
      setPendingChanges(prev => prev.filter(c => !(c.row === change.row && c.column === change.column)))
      return
    }
    const updated = [...csvRows]
    if (updated[change.row]) {
      updated[change.row] = { ...updated[change.row], [change.column]: change.new_value }
      setCsvRows(updated); setHasUnsavedEdits(true)
      const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
      setHistory(newHist); setHistoryIndex(newIdx)
    }
    setPendingChanges(prev => prev.filter(c => !(c.row === change.row && c.column === change.column)))
  }, [csvRows, history, historyIndex, pushHistory])

  const handleDenyChange = useCallback((change) => {
    const updated = [...csvRows]
    if (updated[change.row]) {
      updated[change.row] = { ...updated[change.row], [change.column]: change.old_value }
      setCsvRows(updated); setHasUnsavedEdits(true)
      const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
      setHistory(newHist); setHistoryIndex(newIdx)
    }
    setPendingChanges(prev => prev.filter(c => !(c.row === change.row && c.column === change.column)))
  }, [csvRows, history, historyIndex, pushHistory])

  const handleAcceptAllChanges = useCallback(() => {
    let updated = [...csvRows]
    for (const ch of pendingChanges) {
      if (ch.kind === 'critical' || ch.new_value === '') continue
      if (updated[ch.row]) updated[ch.row] = { ...updated[ch.row], [ch.column]: ch.new_value }
    }
    setCsvRows(updated); setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
    setHistory(newHist); setHistoryIndex(newIdx); setPendingChanges([])
  }, [csvRows, history, historyIndex, pushHistory, pendingChanges])

  const handleDenyAllChanges = useCallback(() => {
    let updated = [...csvRows]
    for (const ch of pendingChanges) {
      if (updated[ch.row]) updated[ch.row] = { ...updated[ch.row], [ch.column]: ch.old_value }
    }
    setCsvRows(updated); setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
    setHistory(newHist); setHistoryIndex(newIdx); setPendingChanges([])
  }, [csvRows, history, historyIndex, pushHistory, pendingChanges])

  /* ── exports ─────────────────────────────────────────────────────────────── */
  const handleExportClean = () => {
    const { csv } = buildCSVFile()
    triggerDownload('\ufeff' + csv, `Clean_${fileName}`)
  }

  const handleExportQuarantine = () => {
    if (!quarantineCSV) return
    triggerDownload('\ufeff' + quarantineCSV, `Quarantine_${fileName}`)
  }

  const handleExportFull = () => {
    // Combine clean + quarantine rows (strip internal cols from quarantine)
    const qDataHeaders = quarantineHeaders.filter(h => h !== '_row_id' && h !== '_issue_reason')
    const allHeaders   = csvHeaders  // assume same schema

    const cleanLines = csvRows.map(r => encodeCSVLine(allHeaders.map(h => r[h] || '')))
    const qLines = quarantineRows.map(r => {
      const clean = _stripInternalCols(r)
      return encodeCSVLine(allHeaders.map(h => clean[h] || ''))
    })
    const full = [encodeCSVLine(allHeaders), ...cleanLines, ...qLines].join('\n')
    triggerDownload('\ufeff' + full, `Full_${fileName}`)
  }

  const handleSaveCurrentToHistory = async () => {
    if (!accessToken) return
    const { csv } = buildCSVFile()
    await saveToHistory(fileName, csv, csvRows.length, csvHeaders.length)
    setHasUnsavedEdits(false)
  }

  /* ─────────────────────────────────────────────────────────────────────────── */
  /*  UPLOAD SCREEN                                                               */
  /* ─────────────────────────────────────────────────────────────────────────── */
  if (step === 'upload') {
    return (
      <div className="app-page">
        <div className="app-header">
          {currentUser ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>Welcome, <strong>{currentUser.username}</strong>!</span>
              <button onClick={async () => {
                try { await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' }) } catch { /**/ }
                setCurrentUser(null); setAccessToken(null); setUserHistory([])
              }} style={{ background: 'transparent', border: '1px solid #475569', color: '#94a3b8', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', marginLeft: 12 }}>
                Logout
              </button>
            </div>
          ) : (
            <LoginButtons onLogin={() => setAuthModalMode('login')} onSignup={() => setAuthModalMode('signup')} />
          )}
        </div>

        <div style={{ display: 'flex', width: '100%', maxWidth: 1000, gap: 32, alignItems: 'flex-start', marginTop: 40 }}>
          {currentUser && (
            <div style={{ flex: '0 0 300px', background: '#1e293b', padding: 24, borderRadius: 12, border: '1px solid #334155' }}>
              <h3 style={{ marginTop: 0, marginBottom: 16, color: '#f8fafc', fontSize: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Undo size={18} /> Recent Files
              </h3>
              {userHistory.length === 0
                ? <div style={{ color: '#64748b', fontSize: 14, fontStyle: 'italic' }}>No history yet.</div>
                : <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {userHistory.map(item => (
                    <div key={item.id} onClick={() => handleHistoryItemClick(item)}
                      style={{ background: '#0f172a', padding: 12, borderRadius: 8, cursor: 'pointer', border: '1px solid transparent', transition: 'all 0.2s' }}
                      onMouseEnter={e => e.currentTarget.style.borderColor = '#8b5cf6'}
                      onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}>
                      <div style={{ color: '#e2e8f0', fontWeight: 500, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.filename}</div>
                      <div style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>{new Date(item.created_at).toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              }
            </div>
          )}
          <div style={{ flex: 1 }}>
            <DragAndDrop onFileAccepted={handleFileAccepted} />
            {isLoading && <div className="loading-indicator">Processing file…</div>}
          </div>
        </div>

        {authModalMode && (
          <AuthModal initialMode={authModalMode} onClose={() => setAuthModalMode(null)} onSuccess={(u, t) => { setCurrentUser(u); setAccessToken(t); setAuthModalMode(null) }} />
        )}
      </div>
    )
  }

  /* ─────────────────────────────────────────────────────────────────────────── */
  /*  PREVIEW / EDITOR SCREEN                                                     */
  /* ─────────────────────────────────────────────────────────────────────────── */
  const quarantineCount = quarantineRows.length

  return (
    <div className="app-page preview-page">

      {/* ── topbar ─────────────────────────────────────────────────────────── */}
      <div className="preview-topbar">
        <button className="back-btn" onClick={handleBack}><ArrowLeft size={18} /> Back</button>
        <h1 className="preview-title">Clarifi.ai</h1>

        <div style={{ flex: 1, display: 'flex', justifyContent: 'center', padding: '0 16px' }}>
          {activeTab === 'clean' && <SearchBar onSearch={setSearchQuery} />}
        </div>

        <div style={{ display: 'flex', gap: 10, flexShrink: 0, alignItems: 'center' }}>
          {/* undo / redo */}
          <div style={{ display: 'flex', gap: 2, background: 'rgba(255,255,255,0.05)', padding: 4, borderRadius: 8 }}>
            <button onClick={handleUndo} disabled={historyIndex <= 0} title="Undo"
              style={{ background: 'transparent', border: 'none', color: historyIndex > 0 ? '#e2e8f0' : '#475569', cursor: historyIndex > 0 ? 'pointer' : 'not-allowed', padding: '4px 8px' }}>
              <Undo size={18} />
            </button>
            <button onClick={handleRedo} disabled={historyIndex >= history.length - 1} title="Redo"
              style={{ background: 'transparent', border: 'none', color: historyIndex < history.length - 1 ? '#e2e8f0' : '#475569', cursor: historyIndex < history.length - 1 ? 'pointer' : 'not-allowed', padding: '4px 8px' }}>
              <Redo size={18} />
            </button>
          </div>

          {/* auto-fix */}
          <button onClick={handleAutoFix} disabled={isFixing || isLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: '1px solid #8b5cf6', cursor: (isFixing || isLoading) ? 'not-allowed' : 'pointer', fontWeight: 'bold', background: 'rgba(139,92,246,0.1)', color: '#c4b5fd', transition: 'all 0.2s' }}>
            <Wand2 size={16} className={isFixing ? 'spin' : ''} />
            {isFixing ? 'Fixing…' : 'Auto-Fix All'}
          </button>

          {/* re-analyse */}
          <button onClick={handleReAnalyze} disabled={isLoading || isFixing}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: 'none', cursor: (isLoading || isFixing) ? 'not-allowed' : 'pointer', fontWeight: 'bold', background: hasUnsavedEdits ? '#3b82f6' : 'rgba(255,255,255,0.1)', color: hasUnsavedEdits ? '#fff' : '#94a3b8', transition: 'all 0.2s' }}>
            <Redo size={16} className={isLoading ? 'spin' : ''} />
            {isLoading ? 'Analysing…' : 'Re-Analyse'}
          </button>

          {/* save */}
          {currentUser && (
            <button onClick={handleSaveCurrentToHistory} disabled={isLoading || isFixing}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: '1px solid #f59e0b', cursor: (isLoading || isFixing) ? 'not-allowed' : 'pointer', fontWeight: 'bold', background: hasUnsavedEdits ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.05)', color: hasUnsavedEdits ? '#fbbf24' : '#94a3b8' }}>
              <Save size={16} />
              {hasUnsavedEdits ? 'Save *' : 'Saved'}
            </button>
          )}

          {/* export dropdown zone */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={handleExportClean}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '8px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 'bold', background: '#10b981', color: '#fff', fontSize: 12 }}>
              <Download size={14} /> Clean
            </button>
            {quarantineCount > 0 && (
              <button onClick={handleExportQuarantine}
                style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '8px 14px', borderRadius: 8, border: '1px solid #ef4444', cursor: 'pointer', fontWeight: 'bold', background: 'rgba(239,68,68,0.12)', color: '#fca5a5', fontSize: 12 }}>
                <FileDown size={14} /> Quarantine
              </button>
            )}
            {quarantineCount > 0 && (
              <button onClick={handleExportFull}
                style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '8px 14px', borderRadius: 8, border: '1px solid #64748b', cursor: 'pointer', fontWeight: 'bold', background: 'rgba(255,255,255,0.05)', color: '#94a3b8', fontSize: 12 }}>
                <Layers size={14} /> Full
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── sheet tabs (Excel-style) ─────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'flex-end', gap: 0,
        paddingLeft: 20, paddingRight: 20, paddingTop: 8,
        background: 'rgba(13,21,38,0.6)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
      }}>
        <SheetTab
          label="Clean Data"
          count={csvRows.length}
          active={activeTab === 'clean'}
          variant="clean"
          onClick={() => setActiveTab('clean')}
        />
        <SheetTab
          label={quarantineCount > 0 ? 'Quarantined' : 'Quarantine'}
          count={quarantineCount}
          active={activeTab === 'quarantine'}
          variant="quarantine"
          onClick={() => setActiveTab('quarantine')}
        />
        {quarantineCount === 0 && (
          <span style={{ marginLeft: 10, fontSize: 11, color: '#475569', alignSelf: 'center' }}>
            Run Auto-Fix to populate the quarantine sheet
          </span>
        )}
      </div>

      {/* ── body ────────────────────────────────────────────────────────────── */}
      <div className="preview-body">

        {/* table / quarantine area */}
        <div className="preview-table-area">
          <div style={{ textAlign: 'center', fontSize: 12, color: '#475569', fontWeight: 600, marginBottom: 8, letterSpacing: '0.3px' }}>
            {activeTab === 'clean'
              ? <>{csvHeaders.length} columns&nbsp;•&nbsp;{csvRows.length} rows{quarantineCount > 0 && <span style={{ color: '#f59e0b', marginLeft: 10 }}>• {quarantineCount} quarantined</span>}</>
              : <>{quarantineCount} row{quarantineCount !== 1 ? 's' : ''} need human attention</>
            }
          </div>

          {activeTab === 'clean' ? (
            <CsvTable
              csvRows={csvRows}
              headers={csvHeaders}
              issues={analysisData?.issues || []}
              pendingChanges={pendingChanges}
              onCellEdit={handleCellEdit}
              focusedRow={focusedRow}
              onAcceptChange={handleAcceptChange}
              onDenyChange={handleDenyChange}
              searchQuery={searchQuery}
            />
          ) : (
            <QuarantineTable
              rows={quarantineRows}
              headers={quarantineHeaders}
              onMergeSelected={handleMergeSelected}
              onMergeAll={handleMergeAll}
              onCellEdit={handleQuarantineCellEdit}
            />
          )}
        </div>

        {/* sidebar */}
        <div className="preview-sidebar-area">
          <InfoPanel
            fileName={fileName}
            headers={csvHeaders}
            rowCount={csvRows.length}
            analysisData={analysisData}
            originalScore={originalScore}
            pendingChanges={pendingChanges}
            onIssueClick={(rowIndex) => { setActiveTab('clean'); setFocusedRow(rowIndex) }}
            onAcceptAllChanges={handleAcceptAllChanges}
            onDenyAllChanges={handleDenyAllChanges}
            isAnimatingScore={isAnimatingScore}
            quarantineCount={quarantineCount}
            onViewQuarantine={() => setActiveTab('quarantine')}
          />
        </div>
      </div>
    </div>
  )
}