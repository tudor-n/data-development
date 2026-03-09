import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, Clock } from 'lucide-react'
import './SearchBar.css'

const API_BASE = import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL.replace('/analyze', '')
    : 'http://127.0.0.1:8000'

// Delay before closing dropdown on blur, to allow click-on-item to register first
const BLUR_DELAY_MS = 150

export default function SearchBar({ onSearch }) {
    const [query, setQuery] = useState('')
    const [history, setHistory] = useState([])
    const [showDrop, setShowDrop] = useState(false)
    const inputRef = useRef(null)
    const wrapRef = useRef(null)
    const timerRef = useRef(null)

    // ── fetch history ───────────────────────────────────────────────
    const fetchHistory = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/search-history`)
            if (res.ok) setHistory(await res.json())
        } catch { /* backend may be offline */ }
    }, [])

    useEffect(() => { fetchHistory() }, [fetchHistory])

    // ── close dropdown on outside click ────────────────────────────
    useEffect(() => {
        const handler = (e) => {
            if (wrapRef.current && !wrapRef.current.contains(e.target)) {
                setShowDrop(false)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])

    // ── debounced search ────────────────────────────────────────────
    const handleChange = (e) => {
        const val = e.target.value
        setQuery(val)
        setShowDrop(true)
        clearTimeout(timerRef.current)
        timerRef.current = setTimeout(() => onSearch(val), 200)
    }

    // ── persist on Enter or blur ────────────────────────────────────
    const persist = useCallback(async (q) => {
        if (!q.trim()) return
        try {
            await fetch(`${API_BASE}/search-history`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q.trim() }),
            })
            fetchHistory()
        } catch { /* offline */ }
    }, [fetchHistory])

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') { persist(query); setShowDrop(false) }
        if (e.key === 'Escape') { clearSearch() }
    }

    const handleBlur = () => {
        persist(query)
        setTimeout(() => setShowDrop(false), BLUR_DELAY_MS) // delay so click on item registers
    }

    // ── clear ───────────────────────────────────────────────────────
    const clearSearch = () => {
        setQuery('')
        onSearch('')
        inputRef.current?.focus()
    }

    // ── pick a history item ─────────────────────────────────────────
    const pickHistory = (item) => {
        setQuery(item.query)
        onSearch(item.query)
        setShowDrop(false)
    }

    // ── delete a history item ───────────────────────────────────────
    const deleteHistory = async (e, item) => {
        e.stopPropagation()
        try {
            await fetch(`${API_BASE}/search-history/${item.id}`, { method: 'DELETE' })
            setHistory(prev => prev.filter(h => h.id !== item.id))
        } catch { /* offline */ }
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
                    {history.map(item => (
                        <li key={item.id} className="searchbar-history-item" onMouseDown={() => pickHistory(item)}>
                            <Clock size={12} className="searchbar-hist-icon" />
                            <span className="searchbar-hist-text">{item.query}</span>
                            <button
                                className="searchbar-hist-del"
                                onMouseDown={(e) => deleteHistory(e, item)}
                                title="Remove"
                            >
                                <X size={11} />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}
