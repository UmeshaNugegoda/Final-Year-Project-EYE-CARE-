import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sun, Moon, Eye, EyeOff } from 'lucide-react'
import './Login.css'

function Login({ setAuth }) {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotSuccess, setForgotSuccess] = useState(false)

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

  const handleForgotSubmit = async (e) => {
    e.preventDefault()
    if (!forgotEmail.trim()) {
      setError('Please enter your email or username.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const response = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usernameOrEmail: forgotEmail.trim() }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Failed to send reset link.')
      setForgotSuccess(true)
    } catch (err) {
      setError(err.message || 'Failed to send reset link.')
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

      {/* Left — animated eye/DALK panel */}
      <div className="login-panel" aria-hidden="true">
        {/* Ambient background particles */}
        <div className="eye-particles">
          {[...Array(18)].map((_, i) => (
            <span key={i} className="eye-particle" style={{ '--i': i }} />
          ))}
        </div>

        <div className="login-panel-content">
          {/* Animated Eye */}
          <div className="eye-scene">
            {/* Outer glow ring */}
            <div className="eye-outer-ring" />
            <div className="eye-outer-ring eye-outer-ring-2" />

            {/* The eye shape */}
            <div className="eye-shape">
              {/* Iris */}
              <div className="eye-iris">
                {/* Iris pattern rings */}
                <div className="iris-ring iris-ring-1" />
                <div className="iris-ring iris-ring-2" />
                <div className="iris-ring iris-ring-3" />

                {/* Corneal scan sweep */}
                <div className="iris-scan-sweep" />

                {/* Pupil */}
                <div className="eye-pupil">
                  <div className="pupil-inner" />
                  {/* Corneal reflex */}
                  <div className="pupil-reflex" />
                </div>
              </div>
            </div>

            {/* Scan line */}
            <div className="eye-scan-line" />

            {/* Data readout labels */}
            <div className="eye-data-label eye-data-label-tl">K1: 43.2D</div>
            <div className="eye-data-label eye-data-label-tr">CCT: 512μm</div>
            <div className="eye-data-label eye-data-label-bl">DALK</div>
            <div className="eye-data-label eye-data-label-br">Scan OK</div>
          </div>

          {/* Text content */}
          <div className="panel-text-block">
            <h2 className="login-panel-title">EyeCare<span className="panel-title-plus">+</span></h2>
            <p className="login-panel-text">
              Post-DALK clinical decision support for corneal transplant follow-up.
            </p>
            <ul className="login-panel-features">
              <li>AI-powered correction prediction</li>
              <li>OCR-assisted measurement extraction</li>
              <li>Full patient assessment history</li>
              <li>Multi-user clinical access</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="login-form-panel">
        <div className="login-card">
          <div className="login-header">
            <div className="login-logo" style={{ backgroundImage: "url('/logo.png')", backgroundSize: 'cover' }}></div>
            <h1 className="login-title">Welcome back</h1>
            <p className="login-subtitle">Sign in to continue to EyeCare+</p>
          </div>

          <div className="login-content">
            {!showForgotPassword ? (
              <>
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <label htmlFor="password">Password</label>
                      <button type="button" className="login-forgot-link" onClick={() => { setShowForgotPassword(true); setError(null); setForgotSuccess(false); }}>Forgot Password?</button>
                    </div>
                    <div className="password-input-wrapper">
                      <input
                        id="password" name="password"
                        type={showPassword ? 'text' : 'password'}
                        value={password} onChange={(e) => setPassword(e.target.value)}
                        placeholder="Enter password" autoComplete="current-password" required
                      />
                      <button
                        type="button"
                        className="password-toggle-btn"
                        onClick={() => setShowPassword(prev => !prev)}
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                        tabIndex={-1}
                      >
                        {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                      </button>
                    </div>
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
              </>
            ) : (
              <div className="forgot-password-view">
                <h3>Reset Password</h3>
                {forgotSuccess ? (
                  <div className="forgot-success">
                    <p>If an account matches that username/email, a reset link has been sent.</p>
                    <button className="login-button" onClick={() => setShowForgotPassword(false)} style={{ marginTop: '20px' }}>
                      Back to Login
                    </button>
                  </div>
                ) : (
                  <form className="login-form" onSubmit={handleForgotSubmit} noValidate>
                    <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', marginBottom: '15px' }}>
                      Enter your username or email and we'll send you a link to reset your password.
                    </p>
                    <div className="login-form-group">
                      <label htmlFor="forgotEmail">Email or Username</label>
                      <input
                        id="forgotEmail" type="text"
                        value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)}
                        placeholder="Enter email or username" required
                      />
                    </div>
                    {error && <div className="login-error" role="alert">{error}</div>}
                    <button className="login-button" type="submit">
                      Send Reset Link
                    </button>
                    <button type="button" className="login-button login-button-secondary" onClick={() => setShowForgotPassword(false)} style={{ marginTop: '10px' }}>
                      Cancel
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
