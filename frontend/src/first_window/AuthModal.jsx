import React, { useState } from 'react'
import './AuthModal.css'

const API_BASE = '/api/v1'

function AuthModal({ onClose, onSuccess, initialMode = 'login' }) {
  const [mode, setMode] = useState(initialMode)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (mode === 'login' && (!email.trim() || !password.trim())) {
      setError('Please fill in all fields')
      return
    }
    if (mode === 'signup') {
      if (!email.trim() || !username.trim() || !password.trim() || !confirmPassword.trim()) {
        setError('Please fill in all fields')
        return
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match')
        return
      }
    }

    setLoading(true)

  const endpoint = mode === 'login' ? '/auth/login' : '/auth/register'
  const body = mode === 'login'
    ? { email, password }
    : { email, username, password, confirm_password: confirmPassword }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    })

    let data
    try {
      data = await res.json()
    } catch {
      throw new Error(`Server error (${res.status}) — check backend logs`)
    }

    if (!res.ok) throw new Error(data.detail || 'Authentication failed')
    onSuccess(data.user, data.access_token)
  } catch (err) {
    setError(err.message)
  } finally {
    setLoading(false)
  }
}

  const switchMode = (m) => { setMode(m); setError('') }

  return (
    <div className="auth-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose}>&times;</button>
        <h2>{mode === 'login' ? 'Welcome Back' : 'Create Account'}</h2>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={loading} autoFocus />
          </div>

          {mode === 'signup' && (
            <div className="auth-field">
              <label>Username</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} disabled={loading} />
            </div>
          )}

          <div className="auth-field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={loading} />
          </div>

          {mode === 'signup' && (
            <div className="auth-field">
              <label>Confirm Password</label>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} disabled={loading} />
            </div>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Log In' : 'Sign Up'}
          </button>
        </form>

        <div className="auth-switch">
          {mode === 'login'
            ? (<>Don't have an account?<span onClick={() => switchMode('signup')}> Sign up</span></>)
            : (<>Already have an account?<span onClick={() => switchMode('login')}> Log in</span></>)
          }
        </div>
      </div>
    </div>
  )
}

export default AuthModal