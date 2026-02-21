import React, { useState } from 'react'
import { ArrowLeft, Upload } from 'lucide-react'

import DragAndDrop from './first_window/dragAndDrop'
import LoginButtons from './first_window/loginButtons'
import CsvTable from './second_window/csvTable'
import InfoPanel from './second_window/info'

import './App.css'

// API Configuration
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/analyze'

function App() {
  const [step, setStep] = useState('upload') // 'upload' | 'preview'
  const [csvRows, setCsvRows] = useState([])
  const [csvHeaders, setCsvHeaders] = useState([])
  const [fileName, setFileName] = useState('')
  const [analysisData, setAnalysisData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleFileAccepted = async (csvText, name) => {
    setIsLoading(true)
    try {
      // Parse CSV
      const lines = csvText.split('\n').filter(l => l.trim())
      if (lines.length === 0) {
        alert('CSV file is empty')
        return
      }

      const headers = lines[0].split(',').map(h => h.trim())
      const rows = lines.slice(1).map(line => {
        const values = line.split(',').map(v => v.trim())
        const obj = {}
        headers.forEach((header, idx) => {
          obj[header] = values[idx] || ''
        })
        return obj
      })

      setCsvHeaders(headers)
      setCsvRows(rows)
      setFileName(name)

      // Try to send to backend for analysis (optional — don't block on failure)
      try {
        const blob = new Blob([csvText], { type: 'text/csv' })
        const file = new File([blob], name, { type: 'text/csv' })
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(API_URL, {
          method: 'POST',
          body: formData,
        })

        if (response.ok) {
          const data = await response.json()
          setAnalysisData(data)
        }
      } catch {
        // Backend unavailable — that's fine, we still show the table
        console.log('Backend not available, showing CSV preview without analysis.')
      }

      setStep('preview')
    } catch (err) {
      alert('Error processing CSV: ' + err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleBack = () => {
    setStep('upload')
    setCsvRows([])
    setCsvHeaders([])
    setFileName('')
    setAnalysisData(null)
  }

  // ── First window: upload ──
  if (step === 'upload') {
    return (
      <div className="app-page">
        <div className="app-header">
          <LoginButtons />
        </div>
        <DragAndDrop onFileAccepted={handleFileAccepted} />
        {isLoading && (
          <div className="loading-indicator">Analyzing file…</div>
        )}
      </div>
    )
  }

  // ── Second window: preview dashboard ──
  return (
    <div className="app-page preview-page">
      {/* Top bar */}
      <div className="preview-topbar">
        <button className="back-btn" onClick={handleBack}>
          <ArrowLeft size={18} />
          Back
        </button>
        <h1 className="preview-title">
          Data Quality Dashboard
        </h1>
        <div className="preview-meta">
          {fileName} &bull; {csvRows.length.toLocaleString()} rows &bull; {csvHeaders.length} columns
        </div>
      </div>

      {/* Main layout: 80% table | 20% sidebar */}
      <div className="preview-body">
        <div className="preview-table-area">
          <CsvTable
            csvRows={csvRows}
            headers={csvHeaders}
            issues={analysisData?.issues || []}
          />
        </div>
        <div className="preview-sidebar-area">
          <InfoPanel
            fileName={fileName}
            headers={csvHeaders}
            rowCount={csvRows.length}
            analysisData={analysisData}
          />
        </div>
      </div>
    </div>
  )
}

export default App