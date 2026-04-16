import React, { useState } from 'react'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './Admin.css'

function Admin({ auth, onLogout }) {
  const [form, setForm] = useState({
    username: '',
    password: '',
    role: 'user',
  })
  const [status, setStatus] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus(null)

    if (!form.username.trim() || !form.password.trim()) {
      setStatus({ type: 'error', message: 'Username and password are required.' })
      return
    }

    try {
      setSubmitting(true)
      const response = await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${auth?.token}`,
        },
        body: JSON.stringify({
          username: form.username.trim(),
          password: form.password,
          role: form.role,
        }),
      })

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(data.message || 'Failed to create user.')
      }

      setStatus({ type: 'success', message: 'User created successfully.' })
      setForm({ username: '', password: '', role: 'user' })
    } catch (error) {
      setStatus({ type: 'error', message: error.message || 'Failed to create user.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar auth={auth} />
      <div className="app-main">
        <Header auth={auth} onLogout={onLogout} title="Admin" />
        <main className="page-content">
          <div className="admin-container">
        <div className="admin-card">
          <h2 className="admin-title">User Management</h2>
          <p className="admin-subtitle">
            Create clinician and admin accounts for accessing the prediction tool.
          </p>

          <form className="admin-form" onSubmit={handleSubmit}>
            <div className="admin-form-row">
              <div className="admin-form-group">
                <label htmlFor="username">Username</label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  value={form.username}
                  onChange={handleChange}
                  placeholder="Enter username"
                  required
                />
              </div>
            </div>

            <div className="admin-form-row">
              <div className="admin-form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="Enter password"
                  required
                />
              </div>
            </div>

            <div className="admin-form-row">
              <div className="admin-form-group">
                <label htmlFor="role">Role</label>
                <select
                  id="role"
                  name="role"
                  value={form.role}
                  onChange={handleChange}
                >
                  <option value="user">Clinician</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            </div>

            {status && (
              <div
                className={`admin-status ${
                  status.type === 'success' ? 'admin-status-success' : 'admin-status-error'
                }`}
              >
                {status.message}
              </div>
            )}

            <button
              type="submit"
              className="admin-submit-button"
              disabled={submitting}
            >
              {submitting ? 'Saving...' : 'Create User'}
            </button>
          </form>

          <div className="admin-hint">
            <p>
              First-time setup: default admin account is
              <span className="admin-hint-strong"> admin / admin123</span>. Please change
              or create a new admin user after logging in.
            </p>
          </div>
        </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default Admin

