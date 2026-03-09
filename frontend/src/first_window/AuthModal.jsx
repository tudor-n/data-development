import React, { useState } from 'react';
import './AuthModal.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

function AuthModal({ onClose, onSuccess, initialMode = 'login' }) {
    const [mode, setMode] = useState(initialMode); // 'login' or 'signup'
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!username.trim() || !password.trim()) {
            setError('Please fill in all fields');
            return;
        }

        setLoading(true);
        const endpoint = mode === 'login' ? '/auth/login' : '/auth/signup';

        try {
            const res = await fetch(`${API_URL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Authentication failed');
            }

            // Success
            onSuccess(data.username);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-overlay" onClick={onClose}>
            <div className="auth-modal" onClick={e => e.stopPropagation()}>
                <button className="auth-close" onClick={onClose}>&times;</button>
                <h2>{mode === 'login' ? 'Welcome Back' : 'Create Account'}</h2>

                {error && <div className="auth-error">{error}</div>}

                <form onSubmit={handleSubmit}>
                    <div className="auth-field">
                        <label>Username</label>
                        <input
                            type="text"
                            value={username}
                            onChange={e => setUsername(e.target.value)}
                            disabled={loading}
                            autoFocus
                        />
                    </div>
                    <div className="auth-field">
                        <label>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <button type="submit" className="auth-submit" disabled={loading}>
                        {loading ? 'Please wait...' : (mode === 'login' ? 'Log In' : 'Sign Up')}
                    </button>
                </form>

                <div className="auth-switch">
                    {mode === 'login' ? (
                        <>Don't have an account? <span onClick={() => { setMode('signup'); setError(''); }}>Sign up</span></>
                    ) : (
                        <>Already have an account? <span onClick={() => { setMode('login'); setError(''); }}>Log in</span></>
                    )}
                </div>
            </div>
        </div>
    );
}

export default AuthModal;
