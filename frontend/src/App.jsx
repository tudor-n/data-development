import React, { useState, useCallback } from 'react'
import { ArrowLeft, Download, Undo, Redo, Wand2 } from 'lucide-react'

import DragAndDrop from './first_window/dragAndDrop'
import LoginButtons from './first_window/loginButtons'
import CsvTable from './second_window/csvTable'
import InfoPanel from './second_window/info'

import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/analyze'

function parseCSV(csv) {
  const lines = []
  let current = ''
  let inQuotes = false
  
  for (let i = 0; i < csv.length; i++) {
    const char = csv[i]
    const nextChar = csv[i + 1]
    
    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (char === '\n' && !inQuotes) {
      if (current.trim()) {
        lines.push(current)
      }
      current = ''
    } else {
      current += char
    }
  }
  
  if (current.trim()) {
    lines.push(current)
  }
  
  return lines
}

function parseCSVLine(line) {
  const fields = []
  let current = ''
  let inQuotes = false
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    const nextChar = line[i + 1]
    
    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (char === ',' && !inQuotes) {
      fields.push(current)
      current = ''
    } else {
      current += char
    }
  }
  
  fields.push(current)
  return fields.map(f => f.replace(/^"|"$/g, '').trim())
}

function encodeCSVLine(fields) {
  return fields.map(f => {
    const s = String(f || '')
    return s.includes(',') || s.includes('"') || s.includes('\n') 
      ? `"${s.replace(/"/g, '""')}"` 
      : s
  }).join(',')
}

function App() {
  const [step, setStep] = useState('upload')
  const [csvRows, setCsvRows] = useState([])
  const [csvHeaders, setCsvHeaders] = useState([])
  const [fileName, setFileName] = useState('')
  const [analysisData, setAnalysisData] = useState(null)
  const [originalScore, setOriginalScore] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isFixing, setIsFixing] = useState(false)
  const [history, setHistory] = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false)
  const [focusedRow, setFocusedRow] = useState(null)
  const [pendingChanges, setPendingChanges] = useState([])
  const [isAnimatingScore, setIsAnimatingScore] = useState(false)

  const pushHistory = useCallback((rows, hist, idx) => {
    const newHist = hist.slice(0, idx + 1)
    newHist.push(rows)
    return { newHist, newIdx: newHist.length - 1 }
  }, [])

  const handleFileAccepted = async (csvData, name) => {
    setIsLoading(true)
    try {
      let textChunk = ''
      let fullFile = null
      if (typeof csvData === 'string') {
        textChunk = csvData
        const blob = new Blob([csvData], { type: 'text/csv' })
        fullFile = new File([blob], name, { type: 'text/csv' })
      } else {
        textChunk = await csvData.text()
        fullFile = csvData
      }
      
      const lines = parseCSV(textChunk)
      if (lines.length === 0) { 
        alert('CSV file is empty')
        setIsLoading(false)
        return 
      }
      
      const headers = parseCSVLine(lines[0])
      const rows = lines.slice(1).map(line => {
        const values = parseCSVLine(line)
        const obj = {}
        headers.forEach((h, i) => { obj[h] = values[i] || '' })
        return obj
      })
      
      setCsvHeaders(headers)
      setCsvRows(rows)
      setHistory([rows])
      setHistoryIndex(0)
      setFileName(name)
      setPendingChanges([])
      setStep('preview')
      
      try {
        const fd = new FormData()
        fd.append('file', fullFile)
        const res = await fetch(API_URL, { method: 'POST', body: fd })
        if (res.ok) {
          setAnalysisData(await res.json())
        }
      } catch (e) {
        console.log('Backend unavailable for initial analysis')
      }
    } catch (err) { 
      alert('Error: ' + err.message)
    } finally { 
      setIsLoading(false) 
    }
  }

  const handleCellEdit = (rowIndex, col, newValue) => {
    const updated = [...csvRows]
    updated[rowIndex] = { ...updated[rowIndex], [col]: newValue }
    setCsvRows(updated)
    setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
    setHistory(newHist)
    setHistoryIndex(newIdx)
  }

  const handleBack = () => {
    setStep('upload')
    setCsvRows([])
    setCsvHeaders([])
    setFileName('')
    setAnalysisData(null)
    setOriginalScore(null)
    setHasUnsavedEdits(false)
    setHistory([])
    setHistoryIndex(-1)
    setFocusedRow(null)
    setPendingChanges([])
    setIsAnimatingScore(false)
  }

  const handleUndo = () => {
    if (historyIndex > 0) {
      const i = historyIndex - 1
      setHistoryIndex(i)
      setCsvRows(history[i])
      setHasUnsavedEdits(true)
    }
  }

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const i = historyIndex + 1
      setHistoryIndex(i)
      setCsvRows(history[i])
      setHasUnsavedEdits(true)
    }
  }

  const handleReAnalyze = async () => {
    setIsLoading(true)
    try {
      const csvLines = [encodeCSVLine(csvHeaders), ...csvRows.map(r => encodeCSVLine(csvHeaders.map(h => r[h] || '')))]
      const csv = csvLines.join('\n')
      const fd = new FormData()
      fd.append('file', new File([new Blob([csv], {type:'text/csv'})], fileName, {type:'text/csv'}))
      const res = await fetch(API_URL, { method: 'POST', body: fd })
      if (res.ok) {
        setAnalysisData(await res.json())
        setHasUnsavedEdits(false)
        setOriginalScore(null)
        setPendingChanges([])
      } else {
        alert('Failed to re-analyze.')
      }
    } catch (err) { 
      alert('Error: ' + err.message) 
    } finally { 
      setIsLoading(false) 
    }
  }

  const handleAutoFix = async () => {
    setIsFixing(true)
    setIsAnimatingScore(true)
    const preFixScore = analysisData?.overall_quality_score ?? null
    try {
      const csvLines = [encodeCSVLine(csvHeaders), ...csvRows.map(r => encodeCSVLine(csvHeaders.map(h => r[h] || '')))]
      const csv = csvLines.join('\n')
      const fd = new FormData()
      fd.append('file', new File([new Blob([csv], {type:'text/csv'})], fileName, {type:'text/csv'}))
      const autofixUrl = API_URL.replace('/analyze', '/autofix')
      const res = await fetch(autofixUrl, { method: 'POST', body: fd })
      
      if (!res.ok) {
        const errorText = await res.text()
        throw new Error(`Backend error: ${res.status} - ${errorText}`)
      }
      
      const result = await res.json()
      const { cleaned_csv, changes } = result

      const lines = parseCSV(cleaned_csv)
      if (lines.length === 0) {
        throw new Error('Empty response from server')
      }
      
      const newHeaders = parseCSVLine(lines[0])
      const newRows = lines.slice(1).map(line => {
        const vals = parseCSVLine(line)
        const obj = {}
        newHeaders.forEach((h, i) => { obj[h] = vals[i] || '' })
        return obj
      })

      setCsvHeaders(newHeaders)
      setCsvRows(newRows)
      setPendingChanges(changes || [])
      const { newHist, newIdx } = pushHistory(newRows, history, historyIndex)
      setHistory(newHist)
      setHistoryIndex(newIdx)

      try {
        const cfd = new FormData()
        cfd.append('file', new File([new Blob([cleaned_csv], {type:'text/csv'})], fileName, {type:'text/csv'}))
        const ar = await fetch(API_URL, { method: 'POST', body: cfd })
        if (ar.ok) {
          const newAnalysis = await ar.json()
          setAnalysisData(newAnalysis)
          setOriginalScore(preFixScore)
          
          setTimeout(() => {
            setIsAnimatingScore(false)
          }, 1500)
        }
      } catch (e) {
        console.error('Auto-reanalyze failed:', e)
        setIsAnimatingScore(false)
      }
    } catch (err) {
      alert('Auto-Fix Error: ' + err.message)
      setIsAnimatingScore(false)
    } finally {
      setIsFixing(false)
    }
  }

  const handleAcceptChange = useCallback((change) => {
    if (change.kind === 'critical' || change.new_value === '') {
      setPendingChanges(prev => prev.filter(c => !(c.row === change.row && c.column === change.column)))
      return
    }
    const updated = [...csvRows]
    if (updated[change.row]) {
      updated[change.row] = { ...updated[change.row], [change.column]: change.new_value }
      setCsvRows(updated)
      setHasUnsavedEdits(true)
      const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
      setHistory(newHist)
      setHistoryIndex(newIdx)
    }
    setPendingChanges(prev => prev.filter(c => !(c.row === change.row && c.column === change.column)))
  }, [csvRows, history, historyIndex, pushHistory])

  const handleDenyChange = useCallback((change) => {
    const updated = [...csvRows]
    if (updated[change.row]) {
      updated[change.row] = { ...updated[change.row], [change.column]: change.old_value }
      setCsvRows(updated)
      setHasUnsavedEdits(true)
      const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
      setHistory(newHist)
      setHistoryIndex(newIdx)
    }
    setPendingChanges(prev => prev.filter(c => !(c.row === change.row && c.column === change.column)))
  }, [csvRows, history, historyIndex, pushHistory])

  const handleAcceptAllChanges = useCallback(() => {
    let updated = [...csvRows]
    for (const change of pendingChanges) {
      if (change.kind === 'critical' || change.new_value === '') continue
      if (updated[change.row]) {
        updated[change.row] = { ...updated[change.row], [change.column]: change.new_value }
      }
    }
    setCsvRows(updated)
    setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
    setHistory(newHist)
    setHistoryIndex(newIdx)
    setPendingChanges([])
  }, [csvRows, history, historyIndex, pushHistory, pendingChanges])

  const handleDenyAllChanges = useCallback(() => {
    let updated = [...csvRows]
    for (const change of pendingChanges) {
      if (updated[change.row]) {
        updated[change.row] = { ...updated[change.row], [change.column]: change.old_value }
      }
    }
    setCsvRows(updated)
    setHasUnsavedEdits(true)
    const { newHist, newIdx } = pushHistory(updated, history, historyIndex)
    setHistory(newHist)
    setHistoryIndex(newIdx)
    setPendingChanges([])
  }, [csvRows, history, historyIndex, pushHistory, pendingChanges])

  const handleExport = () => {
    const csvLines = [encodeCSVLine(csvHeaders), ...csvRows.map(r => encodeCSVLine(csvHeaders.map(h => r[h] || '')))]
    const csv = csvLines.join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `Cleaned_${fileName}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  if (step === 'upload') {
    return (
      <div className="app-page">
        <div className="app-header"><LoginButtons /></div>
        <DragAndDrop onFileAccepted={handleFileAccepted} />
        {isLoading && <div className="loading-indicator">Processing file…</div>}
      </div>
    )
  }

  return (
    <div className="app-page preview-page">
      <div className="preview-topbar">
        <button className="back-btn" onClick={handleBack}><ArrowLeft size={18} /> Back</button>
        <h1 className="preview-title">Clarifi.ai</h1>
        <div className="preview-meta">{fileName} &bull; {csvHeaders.length} columns</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.05)', padding: '4px', borderRadius: '8px' }}>
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
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', borderRadius: '8px', border: '1px solid #8b5cf6', cursor: (isFixing || isLoading) ? 'not-allowed' : 'pointer', fontWeight: 'bold', backgroundColor: 'rgba(139,92,246,0.1)', color: '#c4b5fd', transition: 'all 0.2s' }}>
            <Wand2 size={16} className={isFixing ? 'spin' : ''} />
            {isFixing ? 'Fixing...' : 'Auto-Fix All'}
          </button>
          <button onClick={handleReAnalyze} disabled={isLoading || isFixing}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', borderRadius: '8px', border: 'none', cursor: (isLoading || isFixing) ? 'not-allowed' : 'pointer', fontWeight: 'bold', backgroundColor: hasUnsavedEdits ? '#3b82f6' : 'rgba(255,255,255,0.1)', color: hasUnsavedEdits ? '#fff' : '#94a3b8', transition: 'all 0.2s' }}>
            <Redo size={16} className={isLoading ? 'spin' : ''} />
            {isLoading ? 'Analyzing...' : 'Re-Analyze'}
          </button>
          <button onClick={handleExport}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', backgroundColor: '#10b981', color: '#fff' }}>
            <Download size={16} /> Export Clean CSV
          </button>
        </div>
      </div>
      <div className="preview-body">
        <div className="preview-table-area">
          <CsvTable
            csvRows={csvRows}
            headers={csvHeaders}
            issues={analysisData?.issues || []}
            pendingChanges={pendingChanges}
            onCellEdit={handleCellEdit}
            focusedRow={focusedRow}
            onAcceptChange={handleAcceptChange}
            onDenyChange={handleDenyChange}
          />
        </div>
        <div className="preview-sidebar-area">
          <InfoPanel
            fileName={fileName}
            headers={csvHeaders}
            rowCount={csvRows.length}
            analysisData={analysisData}
            originalScore={originalScore}
            pendingChanges={pendingChanges}
            onIssueClick={(rowIndex) => setFocusedRow(rowIndex)}
            onAcceptAllChanges={handleAcceptAllChanges}
            onDenyAllChanges={handleDenyAllChanges}
            isAnimatingScore={isAnimatingScore}
          />
        </div>
      </div>
    </div>
  )
}

export default App