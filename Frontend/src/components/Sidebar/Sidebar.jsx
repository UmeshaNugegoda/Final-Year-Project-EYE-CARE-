import React, { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Menu, X, LogOut, Sun, Moon } from 'lucide-react'
import './Sidebar.css'

const NAV_ITEMS = [
  { to: '/dashboard',  label: 'Overview' },
  { to: '/patients',   label: 'Patients' },
  { to: '/prediction', label: 'Assessment' },
  { to: '/history',    label: 'History' },
]

function Sidebar({ auth, onLogout }) {
  const role     = auth?.user?.role
  const username = auth?.user?.username || ''
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isDark, setIsDark] = useState(() => document.documentElement.getAttribute('data-theme') === 'dark')

  const toggleTheme = () => {
    const newDark = !isDark;
    setIsDark(newDark);
    const theme = newDark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  // Use the username's first two characters nicely capitalized
  const userInitials = username ? username.substring(0, 2).charAt(0).toUpperCase() + username.substring(1, 2).toLowerCase() : 'Be'
  const userFullName = username ? username : 'Be Confidency'
  const userEmail = username ? `${username.toLowerCase()}@gmail.com` : 'helloconfidency@gmail.com'

  return (
    <header className="topnav">
      <div className="topnav-inner">

        {/* ── Brand ── */}
        <NavLink to="/dashboard" className="topnav-brand">
          <div className="topnav-logo" />
          <div className="topnav-brand-text">
            <span className="topnav-brand-title">EyeCare+</span>
          </div>
        </NavLink>

        {/* ── Nav links (desktop) ── */}
        <nav className="topnav-nav">
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `topnav-link${isActive ? ' topnav-link-active' : ''}`}
            >
              <span>{label}</span>
            </NavLink>
          ))}
          {role === 'admin' && (
            <NavLink
              to="/admin"
              className={({ isActive }) => `topnav-link${isActive ? ' topnav-link-active' : ''}`}
            >
              <span>Admin</span>
            </NavLink>
          )}
        </nav>

        {/* ── Right block items ── */}
        <div className="topnav-actions">
          <button type="button" className="topnav-icon-btn" onClick={toggleTheme} aria-label="Toggle Dark Mode">
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {auth?.user && (
            <div className="topnav-user">
              <div className="topnav-user-avatar">
                {userInitials}
              </div>
              <div className="topnav-user-info">
                <span className="topnav-user-name">{userFullName}</span>
                <span className="topnav-user-role">{role === 'admin' ? 'Administrator' : userEmail}</span>
              </div>
              <button 
                type="button" 
                onClick={onLogout} 
                title="Log out" 
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', marginLeft: '8px', color: 'var(--color-danger)' }}>
                <LogOut size={16} />
              </button>
            </div>
          )}
        </div>

        {/* ── Mobile hamburger ── */}
        <button
          type="button"
          className="topnav-hamburger"
          onClick={() => setMobileOpen(v => !v)}
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* ── Mobile drawer ── */}
      {mobileOpen && (
        <div className="topnav-mobile-drawer">
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `topnav-mobile-link${isActive ? ' topnav-mobile-link-active' : ''}`}
            >
              <span>{label}</span>
            </NavLink>
          ))}
          {role === 'admin' && (
            <NavLink
              to="/admin"
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `topnav-mobile-link${isActive ? ' topnav-mobile-link-active' : ''}`}
            >
              <span>Admin</span>
            </NavLink>
          )}
          {auth?.user && (
            <button type="button" className="topnav-mobile-logout" onClick={onLogout}>
              <LogOut size={15} />
              Log out
            </button>
          )}
        </div>
      )}
    </header>
  )
}

export default Sidebar
