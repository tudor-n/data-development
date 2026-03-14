import React, { useState, useRef, useCallback, useEffect } from 'react'
import { Search, X, Clock } from 'lucide-react'
import './SearchBar.css'

const MAX_HISTORY = 10
const BLUR_DELAY_MS = 150

export default function SearchBar({ onSearch }) {
  const [query, setQuery]       = useState('')
  const [history, setHistory]   = useState([])
  const [showDrop, setShowDrop] = useState(false)
  const inputRef  = useRef(null)
  const wrapRef   = useRef(null)
  const timerRef  = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setShowDrop(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleChange = (e) => {
    const val = e.target.value
    setQuery(val)
    setShowDrop(true)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => onSearch(val), 200)
  }

  const addToHistory = useCallback((q) => {
    const trimmed = q.trim()
    if (!trimmed) return
    setHistory(prev =>
      [{ id: Date.now(), query: trimmed }, ...prev.filter(h => h.query !== trimmed)].slice(0, MAX_HISTORY)
    )
  }, [])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') { addToHistory(query); setShowDrop(false) }
    if (e.key === 'Escape') clearSearch()
  }

  const handleBlur = () => {
    addToHistory(query)
    setTimeout(() => setShowDrop(false), BLUR_DELAY_MS)
  }

  const clearSearch = () => {
    setQuery('')
    onSearch('')
    inputRef.current?.focus()
  }

  const pickHistory = (item) => {
    setQuery(item.query)
    onSearch(item.query)
    setShowDrop(false)
  }

  const deleteHistoryItem = (e, item) => {
    e.stopPropagation()
    setHistory(prev => prev.filter(h => h.id !== item.id))
  }

  return (
    <div className="searchbar-wrap" ref={wrapRef}>
      <div className="searchbar-input-row">
        <Search size={15} className="searchbar-icon" />
        <input
          ref={inputRef}
          className="searchbar-input"
          type="text"
          placeholder="Search in table…"
          value={query}
          onChange={handleChange}
          onFocus={() => setShowDrop(true)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
        />
        {query && (
          <button className="searchbar-clear" onClick={clearSearch} tabIndex={-1}>
            <X size={13} />
          </button>
        )}
      </div>

      {showDrop && history.length > 0 && (
        <ul className="searchbar-dropdown">
          {history.map((item) => (
            <li key={item.id} className="searchbar-history-item" onMouseDown={() => pickHistory(item)}>
              <Clock size={12} className="searchbar-hist-icon" />
              <span className="searchbar-hist-text">{item.query}</span>
              <button className="searchbar-hist-del" onMouseDown={(e) => deleteHistoryItem(e, item)} title="Remove">
                <X size={11} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
