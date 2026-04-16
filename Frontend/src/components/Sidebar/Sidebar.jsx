import React from 'react'
import { NavLink } from 'react-router-dom'
import './Sidebar.css'

function Sidebar({ auth }) {
  const role     = auth?.user?.role
  const username = auth?.user?.username || ''

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">VC</div>
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-title">Visual Correction</span>
          <span className="sidebar-brand-subtitle">Post‑DALK CDS</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/dashboard"
          className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
        >
          <span className="sidebar-link-icon">🏠</span>
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/prediction"
          className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
        >
          <span className="sidebar-link-icon">📊</span>
          <span>Prediction</span>
        </NavLink>
        <NavLink to="/patients"
          className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
        >
          <span className="sidebar-link-icon">👥</span>
          <span>Previous Patients</span>
        </NavLink>
        <NavLink to="/history"
          className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
        >
          <span className="sidebar-link-icon">📚</span>
          <span>Patient History</span>
        </NavLink>
        {role === 'admin' && (
          <NavLink to="/admin"
            className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
          >
            <span className="sidebar-link-icon">🛠️</span>
            <span>Admin</span>
          </NavLink>
        )}
      </nav>

      {auth?.user && (
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">
            {username.charAt(0).toUpperCase()}
          </div>
          <div className="sidebar-user-info">
            <span className="sidebar-user-name">{username}</span>
            <span className="sidebar-user-role">
              {role === 'admin' ? 'Administrator' : 'Clinician'}
            </span>
          </div>
        </div>
      )}
    </aside>
  )
}

export default Sidebar
