import React, { useState } from 'react'
import { ArrowLeft, Upload, RefreshCw, Download, Undo, Redo, Wand2 } from 'lucide-react'

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
  const [isFixing, setIsFixing] = useState(false)
  
  // History state for Undo/Redo
  const [history, setHistory] = useState([]) 
  const [historyIndex, setHistoryIndex] = useState(-1)
  
  // State to track if there are unsaved edits and auto-scroll focus
  const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false)
  const [focusedRow, setFocusedRow] = useState(null)

  const handleFileAccepted = async (csvData, name) => {
    setIsLoading(true)
    try {
      let textChunk = "";
      let fullFile = null;

      if (typeof csvData === 'string') {
        textChunk = csvData; // Read the whole string for the demo
        const blob = new Blob([csvData], { type: 'text/csv' });
        fullFile = new File([blob], name, { type: 'text/csv' });
      } else {
        textChunk = await csvData.text(); // Read the whole file for the demo
        fullFile = csvData;
      }

      // Parse the CSV for the UI
      const lines = textChunk.split('\n').filter(l => l.trim())
      if (lines.length === 0) {
        alert('CSV file is empty or unreadable')
        return
      }

      const headers = lines[0].split(',').map(h => h.trim())
      
      // Map all rows for the demo so they can all be edited
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
      
      // Initialize history with the raw uploaded data
      setHistory([rows])
      setHistoryIndex(0)
      
      setFileName(name)
      setStep('preview') // Jump to the second window instantly

      // Send the file to the backend
      try {
        const formData = new FormData()
        formData.append('file', fullFile)

        const response = await fetch(API_URL, {
          method: 'POST',
          body: formData,
        })

        if (response.ok) {
          const data = await response.json()
          setAnalysisData(data) 
        }
      } catch {
        console.log('Backend not available, showing CSV preview without analysis.')
      }
    } catch (err) {
      alert('Error processing CSV: ' + err.message)
    } finally {
      setIsLoading(false)
    }
  }

  // Handle User Typing into the table
  const handleCellEdit = (rowIndex, columnName, newValue) => {
    const updatedRows = [...csvRows];
    updatedRows[rowIndex] = { ...updatedRows[rowIndex], [columnName]: newValue };
    
    setCsvRows(updatedRows);
    setHasUnsavedEdits(true);

    // Save to history
    const newHistory = history.slice(0, historyIndex + 1); // Drop future states if we went back
    newHistory.push(updatedRows);
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
  };

  const handleBack = () => {
    setStep('upload')
    setCsvRows([])
    setCsvHeaders([])
    setFileName('')
    setAnalysisData(null)
    setHasUnsavedEdits(false)
    setHistory([])
    setHistoryIndex(-1)
    setFocusedRow(null)
  }

  const handleUndo = () => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      setHistoryIndex(newIndex);
      setCsvRows(history[newIndex]);
      setHasUnsavedEdits(true); // Treat rolling back as an unsaved edit
    }
  };

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      setHistoryIndex(newIndex);
      setCsvRows(history[newIndex]);
      setHasUnsavedEdits(true);
    }
  };

  // Convert current table back to CSV and Re-Analyze
  const handleReAnalyze = async () => {
    setIsLoading(true);
    try {
      // Convert JSON rows back to a CSV string
      const headerRow = csvHeaders.join(',');
      const dataRows = csvRows.map(row => 
        csvHeaders.map(header => `"${(row[header] || '').toString().replace(/"/g, '""')}"`).join(',')
      );
      const csvString = [headerRow, ...dataRows].join('\n');

      const blob = new Blob([csvString], { type: 'text/csv' });
      const file = new File([blob], fileName, { type: 'text/csv' });

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(API_URL, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysisData(data);
        setHasUnsavedEdits(false); // Reset edit state
      } else {
        alert("Failed to re-analyze data.");
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAutoFix = async () => {
    setIsFixing(true);
    try {
      // 1. Convert current table to CSV string
      const headerRow = csvHeaders.join(',');
      const dataRows = csvRows.map(row => 
        csvHeaders.map(header => `"${(row[header] || '').toString().replace(/"/g, '""')}"`).join(',')
      );
      const csvString = [headerRow, ...dataRows].join('\n');

      const blob = new Blob([csvString], { type: 'text/csv' });
      const file = new File([blob], fileName, { type: 'text/csv' });
      const formData = new FormData();
      formData.append('file', file);

      // 2. Send to the new /autofix endpoint
      const autofixUrl = API_URL.replace('/analyze', '/autofix');
      const response = await fetch(autofixUrl, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to auto-fix data. Backend returned an error.");
      }

      // 3. Receive and parse the cleaned CSV text
      const cleanedCsvText = await response.text();
      const lines = cleanedCsvText.split('\n').filter(l => l.trim());
      
      if (lines.length === 0) throw new Error("Received empty data from AI");

      // Smart regex split to handle commas inside quotes
      const newHeaders = lines[0].split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map(h => h.replace(/^"|"$/g, '').trim());
      
      const newRows = lines.slice(1).map(line => {
        const values = line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map(v => v.replace(/^"|"$/g, '').trim());
        const obj = {};
        newHeaders.forEach((header, idx) => {
          obj[header] = values[idx] || '';
        });
        return obj;
      });

      // 4. Update the UI and save to History so we can Undo!
      setCsvHeaders(newHeaders);
      setCsvRows(newRows);
      
      const newHistory = history.slice(0, historyIndex + 1);
      newHistory.push(newRows);
      setHistory(newHistory);
      setHistoryIndex(newHistory.length - 1);

      // --- NEW: 5. Automatically Re-Analyze the clean data! ---
      const cleanBlob = new Blob([cleanedCsvText], { type: 'text/csv' });
      const cleanFile = new File([cleanBlob], fileName, { type: 'text/csv' });
      const analyzeFormData = new FormData();
      analyzeFormData.append('file', cleanFile);

      const analyzeResponse = await fetch(API_URL, {
        method: 'POST',
        body: analyzeFormData,
      });

      if (analyzeResponse.ok) {
        const newAnalysisData = await analyzeResponse.json();
        setAnalysisData(newAnalysisData);
        setHasUnsavedEdits(false);
      } else {
        console.error("Auto-fix succeeded, but auto-reanalyze failed.");
        setHasUnsavedEdits(true); 
      }

    } catch (err) {
      alert("Auto-Fix Error: " + err.message);
    } finally {
      setIsFixing(false);
    }
  };

  const handleExport = () => {
    const headerRow = csvHeaders.join(',');
    const dataRows = csvRows.map(row => 
      csvHeaders.map(header => `"${(row[header] || '').toString().replace(/"/g, '""')}"`).join(',')
    );
    const csvString = [headerRow, ...dataRows].join('\n');
    
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Cleaned_${fileName}`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (step === 'upload') {
    return (
      <div className="app-page">
        <div className="app-header">
          <LoginButtons />
        </div>
        <DragAndDrop onFileAccepted={handleFileAccepted} />
        {isLoading && (
          <div className="loading-indicator">Processing file preview…</div>
        )}
      </div>
    )
  }

  return (
    <div className="app-page preview-page">
      <div className="preview-topbar">
        <button className="back-btn" onClick={handleBack}>
          <ArrowLeft size={18} />
          Back
        </button>
        <h1 className="preview-title">
          Data Quality Dashboard
        </h1>
        <div className="preview-meta">
          {fileName} &bull; {csvHeaders.length} columns
        </div>

        {/* --- ACTION BUTTONS --- */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
            
            {/* UNDO / REDO BUTTONS */}
            <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.05)', padding: '4px', borderRadius: '8px' }}>
                <button 
                  onClick={handleUndo} 
                  disabled={historyIndex <= 0}
                  style={{
                    background: 'transparent', border: 'none', color: historyIndex > 0 ? '#e2e8f0' : '#475569',
                    cursor: historyIndex > 0 ? 'pointer' : 'not-allowed', padding: '4px 8px'
                  }}
                  title="Undo"
                >
                  <Undo size={18} />
                </button>
                <button 
                  onClick={handleRedo} 
                  disabled={historyIndex >= history.length - 1}
                  style={{
                    background: 'transparent', border: 'none', color: historyIndex < history.length - 1 ? '#e2e8f0' : '#475569',
                    cursor: historyIndex < history.length - 1 ? 'pointer' : 'not-allowed', padding: '4px 8px'
                  }}
                  title="Redo"
                >
                  <Redo size={18} />
                </button>
            </div>

            {/* AI AUTO-FIX BUTTON */}
            <button 
                onClick={handleAutoFix} 
                disabled={isFixing || isLoading}
                style={{
                    display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px',
                    borderRadius: '8px', border: '1px solid #8b5cf6', cursor: (isFixing || isLoading) ? 'not-allowed' : 'pointer', fontWeight: 'bold',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)', color: '#c4b5fd',
                    transition: 'all 0.2s'
                }}
            >
                <Wand2 size={16} className={isFixing ? "spin" : ""} />
                {isFixing ? "Fixing..." : "Auto-Fix All"}
            </button>

            {/* RE-ANALYZE BUTTON */}
            <button 
                onClick={handleReAnalyze} 
                disabled={isLoading || isFixing}
                style={{
                    display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px',
                    borderRadius: '8px', border: 'none', cursor: (isLoading || isFixing) ? 'not-allowed' : 'pointer', fontWeight: 'bold',
                    backgroundColor: hasUnsavedEdits ? '#3b82f6' : 'rgba(255,255,255,0.1)',
                    color: hasUnsavedEdits ? '#fff' : '#94a3b8',
                    transition: 'all 0.2s'
                }}
            >
                <RefreshCw size={16} className={isLoading ? "spin" : ""} />
                {isLoading ? "Analyzing..." : "Re-Analyze"}
            </button>

            {/* EXPORT BUTTON */}
            <button 
                onClick={handleExport}
                style={{
                    display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px',
                    borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold',
                    backgroundColor: '#10b981', color: '#fff'
                }}
            >
                <Download size={16} />
                Export Clean CSV
            </button>
        </div>
      </div>

      <div className="preview-body">
        <div className="preview-table-area">
          <CsvTable
            csvRows={csvRows}
            headers={csvHeaders}
            issues={analysisData?.issues || []}
            onCellEdit={handleCellEdit} 
            focusedRow={focusedRow}
          />
        </div>
        <div className="preview-sidebar-area">
          <InfoPanel
            fileName={fileName}
            headers={csvHeaders}
            rowCount={csvRows.length}
            analysisData={analysisData}
            onIssueClick={(rowIndex) => setFocusedRow(rowIndex)}
          />
        </div>
      </div>
    </div>
  )
}

export default App