import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sun, Moon } from 'lucide-react'
import './Login.css'

function Login({ setAuth }) {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)
  
  const [isDark, setIsDark] = useState(() => document.documentElement.getAttribute('data-theme') === 'dark')

  const toggleTheme = () => {
    const newDark = !isDark;
    setIsDark(newDark);
    const theme = newDark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!username.trim() || !password.trim()) {
      setError('Username and password are required.')
      return
    }
    try {
      setLoading(true)
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Login failed.')
      setAuth({ token: data.token, user: data.user })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <button 
        type="button" 
        onClick={toggleTheme} 
        style={{ position: 'absolute', top: 24, right: 32, zIndex: 10, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '50%', width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--color-text-secondary)', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}
        aria-label="Toggle Dark Mode"
      >
        {isDark ? <Sun size={20} /> : <Moon size={20} />}
      </button>
      {/* left decorative panel */}
      <div className="login-panel" aria-hidden="true">
        <div className="login-panel-content">
          <div className="login-panel-logo" style={{ backgroundImage: "url('/logo.png')", backgroundSize: 'cover' }}></div>
          <h2 className="login-panel-title">EyeCare+</h2>
          <p className="login-panel-text">
            Post-DALK clinical decision support system for corneal transplant follow-up.
          </p>
          <ul className="login-panel-features">
            <li>AI-powered correction prediction</li>
            <li>OCR-assisted measurement extraction</li>
            <li>Full patient assessment history</li>
            <li>Multi-user clinical access</li>
          </ul>
        </div>
      </div>

      {/* right form panel */}
      <div className="login-form-panel">
        <div className="login-card">
          <div className="login-header">
            <div className="login-logo" style={{ backgroundImage: "url('/logo.png')", backgroundSize: 'cover' }}></div>
            <h1 className="login-title">Welcome back</h1>
            <p className="login-subtitle">Sign in to continue to EyeCare+</p>
          </div>

          <div className="login-content">
            <form className="login-form" onSubmit={handleSubmit} noValidate>
              <div className="login-form-group">
                <label htmlFor="username">Username</label>
                <input
                  id="username" name="username" type="text"
                  value={username} onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username" autoComplete="username" required
                />
              </div>
              <div className="login-form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password" name="password" type="password"
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password" autoComplete="current-password" required
                />
              </div>
              {error && <div className="login-error" role="alert">{error}</div>}
              <button className="login-button" type="submit" disabled={loading}>
                {loading ? 'Signing in…' : 'Sign In'}
              </button>
            </form>
            <p className="login-hint">
              Default administrator:&nbsp;
              <span className="login-hint-strong">admin / admin123</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
