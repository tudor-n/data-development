import React, { useState, useCallback, useEffect } from 'react'
import {
  ArrowLeft, Download, Undo, Redo, Wand2, Save,
  AlertTriangle, CheckCircle, FileDown, Layers, Trash2 
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

  const [activeTab, setActiveTab]             = useState('clean')
  const [quarantineRows, setQuarantineRows]   = useState([])
  const [quarantineHeaders, setQuarantineHeaders] = useState([])
  const [quarantineCSV, setQuarantineCSV]     = useState('')

  const [currentUser, setCurrentUser]     = useState(null)
  const [accessToken, setAccessToken]     = useState(null)
  const [authModalMode, setAuthModalMode] = useState(null)
  const [userHistory, setUserHistory]     = useState([])

  const authHeaders = useCallback(t => t ? { Authorization: `Bearer ${t}` } : {}, [])

  useEffect(() => {
    const tryRefresh = async () => {
      try {
        const savedToken = localStorage.getItem('accessToken') || sessionStorage.getItem('accessToken')
        
        if (savedToken) {
          const meRes = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${savedToken}` } })
          if (meRes.ok) { 
            setCurrentUser(await meRes.json())
            setAccessToken(savedToken)
            return
          } else {
            localStorage.removeItem('accessToken')
            sessionStorage.removeItem('accessToken')
          }
        }

        const res = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
        if (!res.ok) return
        const { access_token } = await res.json()
        const meRes = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${access_token}` } })
        if (meRes.ok) { setCurrentUser(await meRes.json()); setAccessToken(access_token) }
      } catch { }
    }
    tryRefresh()
  }, [])

  useEffect(() => {
    const savedWs = sessionStorage.getItem('clarifi_workspace')
    if (savedWs) {
      try {
        const ws = JSON.parse(savedWs)
        setCsvRows(ws.csvRows || [])
        setCsvHeaders(ws.csvHeaders || [])
        setFileName(ws.fileName || '')
        setAnalysisData(ws.analysisData || null)
        setOriginalScore(ws.originalScore || null)
        setHistory(ws.history || [])
        setHistoryIndex(ws.historyIndex ?? -1)
        setHasUnsavedEdits(ws.hasUnsavedEdits || false)
        setPendingChanges(ws.pendingChanges || [])
        setActiveTab(ws.activeTab || 'clean')
        setQuarantineRows(ws.quarantineRows || [])
        setQuarantineHeaders(ws.quarantineHeaders || [])
        setQuarantineCSV(ws.quarantineCSV || '')
        setStep(ws.step || 'upload')
      } catch (e) {
        sessionStorage.removeItem('clarifi_workspace')
      }
    }
  }, [])

  useEffect(() => {
    if (step === 'preview') {
      try {
        sessionStorage.setItem('clarifi_workspace', JSON.stringify({
          step, csvRows, csvHeaders, fileName, analysisData, originalScore,
          history, historyIndex, hasUnsavedEdits, pendingChanges,
          activeTab, quarantineRows, quarantineHeaders, quarantineCSV
        }))
      } catch (e) {
        sessionStorage.removeItem('clarifi_workspace')
      }
    } else {
      sessionStorage.removeItem('clarifi_workspace')
    }
  }, [
    step, csvRows, csvHeaders, fileName, analysisData, originalScore,
    history, historyIndex, hasUnsavedEdits, pendingChanges,
    activeTab, quarantineRows, quarantineHeaders, quarantineCSV
  ])

  const fetchUserHistory = useCallback(async (token) => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/history?limit=10`, { headers: authHeaders(token) })
      if (res.ok) setUserHistory(await res.json())
    } catch { }
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
    } catch { }
  }, [accessToken, authHeaders, fetchUserHistory])

  const pushHistory = useCallback((rows, hist, idx) => {
    const newHist = hist.slice(0, idx + 1)
    newHist.push(rows)
    return { newHist, newIdx: newHist.length - 1 }
  }, [])

  const handleUndo = () => {
    if (historyIndex > 0) {
      const i = historyIndex - 1
      setHistoryIndex(i)
      setCsvRows(history[i])
      setHasUnsavedEdits(true)
      setPendingChanges([])
    }
  }

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const i = historyIndex + 1
      setHistoryIndex(i)
      setCsvRows(history[i])
      setHasUnsavedEdits(true)
      setPendingChanges([])
    }
  }

  const buildCSVFile = () => {
    const csv = [encodeCSVLine(csvHeaders), ...csvRows.map(r => encodeCSVLine(csvHeaders.map(h => r[h] || '')))].join('\n')
    const safeFileName = fileName.replace(/\.[^/.]+$/, "") + ".csv"
    return { csv, file: new File([new Blob([csv], { type: 'text/csv' })], safeFileName, { type: 'text/csv' }) }
  }

  const handleFileAccepted = async (fileOrContent, name, fromHistory = false) => {
    setIsLoading(true)
    try {
      let fileToUpload
      if (typeof fileOrContent === 'string') {
        const safeName = name.replace(/\.[^/.]+$/, "") + ".csv"
        fileToUpload = new File([fileOrContent], safeName, { type: 'text/csv' })
      } else {
        fileToUpload = fileOrContent
      }

      const fd = new FormData()
      fd.append('file', fileToUpload)
      const parseRes = await fetch(`${API_BASE}/parse`, { method: 'POST', body: fd })
      if (!parseRes.ok) throw new Error(`Parse error: ${await parseRes.text()}`)
      const { headers, rows } = await parseRes.json()

      if (!headers?.length) { alert('File is empty or could not be parsed'); return }

      setCsvHeaders(headers)
      setCsvRows(rows)
      setHistory([rows])
      setHistoryIndex(0)
      setFileName(name) 
      setPendingChanges([])
      resetQuarantine()
      setStep('preview')

      if (!fromHistory) {
        const rawContent = typeof fileOrContent === 'string' 
          ? fileOrContent 
          : [encodeCSVLine(headers), ...rows.map(r => encodeCSVLine(headers.map(h => r[h] || '')))].join('\n')
        saveToHistory(name, rawContent, rows.length, headers.length)
      }

      try {
        const fd2 = new FormData()
        fd2.append('file', fileToUpload)
        const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd2 })
        if (res.ok) setAnalysisData(await res.json())
      } catch { }
    } catch (err) {
      alert('Error: ' + err.message)
    } finally { setIsLoading(false) }
  }

  const resetQuarantine = () => {
    setQuarantineRows([]); setQuarantineHeaders([]); setQuarantineCSV(''); setActiveTab('clean')
  }

  const handleHistoryItemClick = async (item) => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API_BASE}/history/${item.id}`, { headers: authHeaders(accessToken) })
      if (res.ok) {
        const detail = await res.json()
        if (detail.file_content) handleFileAccepted(detail.file_content, item.filename, true)
      }
    } catch { }
  }

  const deleteHistoryItem = async (e, entryId) => {
    e.stopPropagation() 
    if (!accessToken) return

    try {
      const res = await fetch(`${API_BASE}/history/${entryId}`, {
        method: 'DELETE',
        headers: authHeaders(accessToken)
      })
      if (!res.ok) throw new Error('Failed to delete project')
      
      setUserHistory(prev => prev.filter(item => item.id !== entryId))
    } catch (err) {
      console.error(err)
      alert(err.message)
    }
  }

  const handleBack = () => {
    setStep('upload'); setCsvRows([]); setCsvHeaders([]); setFileName('')
    setAnalysisData(null); setOriginalScore(null); setHasUnsavedEdits(false)
    setHistory([]); setHistoryIndex(-1); setFocusedRow(null); setPendingChanges([])
    setQuarantineRows([]); setQuarantineHeaders([]); setQuarantineCSV('')
    setActiveTab('clean'); setIsAnimatingScore(false)
  }

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

  const handleAutoFix = async () => {
    setIsFixing(true); setIsAnimatingScore(true)
    const preFixScore = analysisData?.overall_quality_score ?? null
    try {
      const { file } = buildCSVFile()
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API_BASE}/autofix`, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Backend error: ${res.status} – ${await res.text()}`)

      const {
        headers: newHeaders,
        rows:    newRows,
        changes,
        quarantine_count,
        quarantine_headers: qHeaders,
        quarantine_rows:    qRows,
        quarantine_csv,
      } = await res.json()

      setCsvHeaders(newHeaders)
      setCsvRows(newRows)
      setPendingChanges(changes || [])
      const { newHist, newIdx } = pushHistory(newRows, history, historyIndex)
      setHistory(newHist); setHistoryIndex(newIdx)

      const hasQuarantine = quarantine_count > 0
      setQuarantineRows(qRows || [])
      setQuarantineHeaders(qHeaders || [])
      setQuarantineCSV(quarantine_csv || '')

      if (hasQuarantine) setActiveTab('quarantine')

      try {
        const cleanedCsv = [encodeCSVLine(newHeaders), ...newRows.map(r => encodeCSVLine(newHeaders.map(h => r[h] || '')))].join('\n')
        const cfd = new FormData()
        
        const safeFileName = fileName.replace(/\.[^/.]+$/, "") + ".csv"
        cfd.append('file', new File([new Blob([cleanedCsv], { type: 'text/csv' })], safeFileName, { type: 'text/csv' }))
        
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

const handleExport = async (dataRows, prefix) => {
    try {
      const res = await fetch(`${API_BASE}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: `${prefix}_${fileName}`,
          headers: csvHeaders,
          rows: dataRows
        })
      })
      if (!res.ok) throw new Error('Export failed')
      
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${prefix}_${fileName}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert('Export error: ' + err.message)
    }
  }

  const handleExportClean = () => handleExport(csvRows, 'Clean')
  
  const handleExportQuarantine = () => {
    if (quarantineRows.length === 0) return
    const qRows = quarantineRows.map(_stripInternalCols)
    handleExport(qRows, 'Quarantine')
  }

  const handleExportFull = () => {
    const qRows = quarantineRows.map(_stripInternalCols)
    handleExport([...csvRows, ...qRows], 'Full')
  }

  const handleSaveCurrentToHistory = async () => {
    if (!accessToken) return
    const { csv } = buildCSVFile()
    await saveToHistory(fileName, csv, csvRows.length, csvHeaders.length)
    setHasUnsavedEdits(false)
  }

  if (step === 'upload') {
    return (
      <div className="app-page" style={{ 
        display: 'flex', 
        flexDirection: 'row',     
        alignItems: 'stretch',    
        height: '100vh', 
        width: '100%',            // FIX: Using 100% instead of 100vw prevents right-edge clipping
        maxWidth: 'none',         
        margin: 0,                
        padding: '40px 56px 40px 40px', // FIX: Added extra padding on the right side
        gap: '56px',              // FIX: Increased gap between History and Drag&Drop
        boxSizing: 'border-box',
        overflow: 'hidden'        
      }}>
        
        {/* === LEFT COLUMN: RECENT FILES === */}
        {currentUser && (
          <div style={{ 
            flex: '0 0 300px', 
            background: '#1e293b', 
            padding: '24px', 
            borderRadius: '12px', 
            border: '1px solid #334155', 
            display: 'flex', 
            flexDirection: 'column', 
            height: '100%', 
            boxSizing: 'border-box'
          }}>
            <h3 style={{ marginTop: 0, marginBottom: 16, color: '#f8fafc', fontSize: 18, display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <Undo size={18} /> Recent Files
            </h3>
            {userHistory.length === 0
              ? <div style={{ color: '#64748b', fontSize: 14, fontStyle: 'italic' }}>No history yet.</div>
              : <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', paddingRight: 4, flex: 1 }}> 
                {userHistory.map(item => (
                  <div key={item.id} onClick={() => handleHistoryItemClick(item)}
                    style={{ 
                      background: '#0f172a', padding: 12, borderRadius: 8, cursor: 'pointer', 
                      border: '1px solid transparent', transition: 'all 0.2s',
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                    }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = '#8b5cf6'}
                    onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}>
                    
                    <div style={{ overflow: 'hidden' }}>
                      <div style={{ color: '#e2e8f0', fontWeight: 500, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.filename}</div>
                      <div style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>{new Date(item.created_at).toLocaleString()}</div>
                    </div>

                    <button 
                      onClick={(e) => deleteHistoryItem(e, item.id)}
                      style={{
                        background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer',
                        padding: '6px', borderRadius: '4px', display: 'flex', flexShrink: 0
                      }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; }}
                      onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.background = 'transparent'; }}
                      title="Delete project"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            }
          </div>
        )}

        {/* === RIGHT COLUMN: HEADER & DRAG/DROP === */}
        <div style={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '32px',
          height: '100%',
          minWidth: 0 
        }}>
          
          {/* HEADER */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', flexShrink: 0 }}>
            {currentUser ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>Welcome, <strong>{currentUser.username}</strong>!</span>
                <button onClick={async () => {
                  try { await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' }) } catch { }
                  localStorage.removeItem('accessToken')
                  sessionStorage.removeItem('accessToken')
                  setCurrentUser(null); setAccessToken(null); setUserHistory([])
                }} style={{ background: 'transparent', border: '1px solid #475569', color: '#94a3b8', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', marginLeft: 12 }}>
                  Logout
                </button>
              </div>
            ) : (
              <LoginButtons onLogin={() => setAuthModalMode('login')} onSignup={() => setAuthModalMode('signup')} />
            )}
          </div>

          {/* DRAG AND DROP */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, width: '100%' }}>
            <div style={{ flex: 1, width: '100%', display: 'flex' }}>
              <div style={{ width: '100%', height: '100%' }}>
                <DragAndDrop onFileAccepted={handleFileAccepted} />
              </div>
            </div>
            {isLoading && <div className="loading-indicator" style={{ marginTop: '16px', textAlign: 'center' }}>Processing file…</div>}
          </div>

        </div>

        {/* Auth Modal Overlay */}
        {authModalMode && (
          <AuthModal initialMode={authModalMode} onClose={() => setAuthModalMode(null)} onSuccess={(u, t) => { setCurrentUser(u); setAccessToken(t); setAuthModalMode(null) }} />
        )}
      </div>
    )
  }

  const quarantineCount = quarantineRows.length

  return (
    <div className="app-page preview-page">
      <div className="preview-topbar">
        <button className="back-btn" onClick={handleBack}><ArrowLeft size={18} /> Back</button>
        <h1 className="preview-title">Clarifi.ai</h1>

        <div style={{ flex: 1, display: 'flex', justifyContent: 'center', padding: '0 16px' }}>
          {activeTab === 'clean' && <SearchBar onSearch={setSearchQuery} />}
        </div>

        <div style={{ display: 'flex', gap: 10, flexShrink: 0, alignItems: 'center' }}>
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

          <button onClick={handleAutoFix} disabled={isFixing || isLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: '1px solid #8b5cf6', cursor: (isFixing || isLoading) ? 'not-allowed' : 'pointer', fontWeight: 'bold', background: 'rgba(139,92,246,0.1)', color: '#c4b5fd', transition: 'all 0.2s' }}>
            <Wand2 size={16} className={isFixing ? 'spin' : ''} />
            {isFixing ? 'Fixing…' : 'Auto-Fix All'}
          </button>

          <button onClick={handleReAnalyze} disabled={isLoading || isFixing}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: 'none', cursor: (isLoading || isFixing) ? 'not-allowed' : 'pointer', fontWeight: 'bold', background: hasUnsavedEdits ? '#3b82f6' : 'rgba(255,255,255,0.1)', color: hasUnsavedEdits ? '#fff' : '#94a3b8', transition: 'all 0.2s' }}>
            <Redo size={16} className={isLoading ? 'spin' : ''} />
            {isLoading ? 'Analysing…' : 'Re-Analyse'}
          </button>

          {currentUser && (
            <button onClick={handleSaveCurrentToHistory} disabled={isLoading || isFixing}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: '1px solid #f59e0b', cursor: (isLoading || isFixing) ? 'not-allowed' : 'pointer', fontWeight: 'bold', background: hasUnsavedEdits ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.05)', color: hasUnsavedEdits ? '#fbbf24' : '#94a3b8' }}>
              <Save size={16} />
              {hasUnsavedEdits ? 'Save *' : 'Saved'}
            </button>
          )}

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

      <div className="preview-body">
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