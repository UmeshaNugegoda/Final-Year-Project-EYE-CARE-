import React, { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Menu, X, LogOut, Sun, Moon } from 'lucide-react'
import './Sidebar.css'

const NAV_ITEMS = [
  { to: '/dashboard',  label: 'Overview' },
  { to: '/patients',   label: 'Patients' },
  { to: '/prediction', label: 'Assessment' },
  { to: '/history',    label: 'History' },
]

function Sidebar({ auth, onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const role     = auth?.user?.role
  const username = auth?.user?.username || ''
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isDark, setIsDark] = useState(() => document.documentElement.getAttribute('data-theme') === 'dark')
  const [profile, setProfile] = useState(null)

  const isAdminPage = role === 'admin' && location.pathname === '/admin'
  const adminPageNavItems = [
    { to: '/admin?tab=directory', label: 'Directory' },
    { to: '/admin?tab=settings', label: 'Settings' },
    { to: '/admin?tab=predictions', label: 'Performance Predictions' },
  ]

  const topNavItems = isAdminPage
    ? adminPageNavItems
    : [
        ...NAV_ITEMS,
        ...(role === 'admin' ? [{ to: '/admin', label: 'Admin Dashboard' }] : []),
      ]

  const currentTab = new URLSearchParams(location.search).get('tab') || 'directory'
  
  const classForItem = ({ to, isActive }) => {
    if (isAdminPage && to.startsWith('/admin?tab=')) {
      const tab = to.split('tab=')[1] || ''
      return `topnav-link${tab === currentTab ? ' topnav-link-active' : ''}`
    }
    if (to === '/admin') return `topnav-link${location.pathname === '/admin' ? ' topnav-link-active' : ''}`
    return `topnav-link${isActive ? ' topnav-link-active' : ''}`
  }
  
  const mobileClassForItem = ({ to, isActive }) => {
    if (isAdminPage && to.startsWith('/admin?tab=')) {
      const tab = to.split('tab=')[1] || ''
      return `topnav-mobile-link${tab === currentTab ? ' topnav-mobile-link-active' : ''}`
    }
    if (to === '/admin') return `topnav-mobile-link${location.pathname === '/admin' ? ' topnav-mobile-link-active' : ''}`
    return `topnav-mobile-link${isActive ? ' topnav-mobile-link-active' : ''}`
  }

  const toggleTheme = () => {
    const newDark = !isDark;
    setIsDark(newDark);
    const theme = newDark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  useEffect(() => {
    if (!auth?.token || !auth?.user) return
    let cancelled = false
    fetch('/api/users/me/profile', {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.resolve(null)))
      .then((data) => {
        if (cancelled || !data?.user) return
        setProfile(data.user)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [auth?.token, auth?.user?.id])

  // Use the username's first two characters nicely capitalized
  const displayName = profile?.username || username
  const userInitials = displayName
    ? displayName.substring(0, 2).charAt(0).toUpperCase() + displayName.substring(1, 2).toLowerCase()
    : 'Be'
  const userFullName = displayName || 'Be Confidency'
  const userEmail = profile?.doctorProfile?.description || (username ? `${username.toLowerCase()}@gmail.com` : 'helloconfidency@gmail.com')
  const userPhotoDataUrl = profile?.doctorProfile?.photoBase64
    ? `data:${profile?.doctorProfile?.photoMimeType || 'image/jpeg'};base64,${profile.doctorProfile.photoBase64}`
    : ''

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
          {topNavItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => classForItem({ to, isActive })}
            >
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* ── Right block items ── */}
        <div className="topnav-actions">
          <button type="button" className="topnav-icon-btn" onClick={toggleTheme} aria-label="Toggle Dark Mode">
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {auth?.user && (
            <div className="topnav-user" onClick={() => navigate('/profile')}>
              <div className="topnav-user-avatar">
                {userPhotoDataUrl ? <img src={userPhotoDataUrl} alt={userFullName} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} /> : userInitials}
              </div>
              <div className="topnav-user-info">
                <span className="topnav-user-name">{userFullName}</span>
                <span className="topnav-user-role">{role === 'admin' ? 'Administrator' : userEmail}</span>
              </div>
              <button 
                type="button" 
                onClick={(e) => { e.stopPropagation(); onLogout() }} 
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
          {topNavItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => mobileClassForItem({ to, isActive })}
            >
              <span>{label}</span>
            </NavLink>
          ))}
          {auth?.user && (
            <NavLink
              to="/profile"
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `topnav-mobile-link${isActive ? ' topnav-mobile-link-active' : ''}`}
            >
              <span>My Profile</span>
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
