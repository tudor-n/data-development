import React, { useRef, useState, useEffect } from 'react';
import './dragAndDrop.css';

const ACCEPTED_EXTENSIONS = /\.(csv|xlsx|xls|json|tsv)$/i;
const ACCEPTED_MIME = ['text/csv', 'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/json', 'text/tab-separated-values', 'text/tsv'];

function DragAndDrop({ onFileAccepted }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState('');
  const [fileError, setFileError] = useState('');
  const [mounted, setMounted] = useState(false);

  const prevent = (e) => { e.preventDefault(); e.stopPropagation(); };

  const dragCounter = useRef(0);
  const emptyDragImage = useRef(null);

  useEffect(() => {
    const img = new Image();
    img.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>';
    emptyDragImage.current = img;
  }, []);

  const isAccepted = (file) => {
    if (!file) return false;
    const nameOk = ACCEPTED_EXTENSIONS.test(file.name || '');
    const typeOk = ACCEPTED_MIME.includes(file.type || '');
    return nameOk || typeOk;
  };

  const handleValidFile = async (f) => {
    setFileName(f.name);
    setFileError('');
    if (onFileAccepted) {
      try {
        onFileAccepted(f, f.name);
      } catch (err) {
        setFileError('Error reading file');
        setTimeout(() => setFileError(''), 3000);
      }
    }
  };

  const onDrop = (e) => {
    prevent(e);
    dragCounter.current = 0;
    setIsDragging(false);
    const files = e.dataTransfer?.files || e.target.files;
    if (files && files.length) {
      const f = files[0];
      if (isAccepted(f)) {
        handleValidFile(f);
      } else {
        setFileError('Please upload CSV, XLSX, JSON, or TSV files only');
        setTimeout(() => setFileError(''), 3000);
      }
    }
  };

  const onDragEnter = (e) => {
    prevent(e);
    dragCounter.current += 1;
    try { if (e.dataTransfer && emptyDragImage.current) e.dataTransfer.setDragImage(emptyDragImage.current, 0, 0); } catch (err) { /* ignore */ }
    if (dragCounter.current > 0) setIsDragging(true);
  };

  const onDragLeave = (e) => {
    prevent(e);
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const onFileChange = (e) => {
    const files = e.target.files;
    if (files && files.length) {
      const f = files[0];
      if (isAccepted(f)) {
        handleValidFile(f);
      } else {
        setFileError('Please upload CSV, XLSX, JSON, or TSV files only');
        setTimeout(() => setFileError(''), 3000);
      }
    }
  };

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 40);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="dd-container">
      <label
        className={`dd-box ${isDragging ? 'dragging' : ''} ${fileName ? 'has-file' : ''} ${fileError ? 'invalid' : ''} ${mounted ? 'mounted' : ''}`}
        onDragEnter={onDragEnter}
        onDragOver={(e) => { prevent(e); setIsDragging(true); }}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        tabIndex={0}
      >
        <div className="dd-icon" aria-hidden>
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4v10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M8 8l4-4 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        <div className="dd-text">
          <div className="dd-title">{fileName ? 'File selected' : 'Drag & drop a file'}</div>
          <div className="dd-sub">{fileError ? fileError : (fileName ? fileName : 'CSV, XLSX, JSON, TSV — OR CLICK TO BROWSE')}</div>
        </div>

        <input
          ref={inputRef}
          className="dd-input"
          type="file"
          accept=".csv,.xlsx,.xls,.json,.tsv,text/csv,application/json,text/tab-separated-values"
          onChange={onFileChange}
        />
      </label>

      {fileName && <div className="dd-footer">Selected: {fileName}</div>}
      <div aria-live="polite" style={{ position: 'absolute', left: -9999 }}>{fileError}</div>
    </div>
  );
}

export default DragAndDrop;
