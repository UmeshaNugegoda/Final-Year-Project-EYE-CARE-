import React from 'react'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Activity, Users, BookOpen, ShieldCheck } from 'lucide-react'
import './Sidebar.css'

const NAV_ITEMS = [
  { to: '/dashboard',  label: 'Dashboard',         Icon: LayoutDashboard },
  { to: '/prediction', label: 'Prediction',         Icon: Activity },
  { to: '/patients',   label: 'Previous Patients',  Icon: Users },
  { to: '/history',    label: 'Patient History',    Icon: BookOpen },
]

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
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
          >
            <Icon size={18} className="sidebar-link-icon" />
            <span>{label}</span>
          </NavLink>
        ))}
        {role === 'admin' && (
          <NavLink
            to="/admin"
            className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
          >
            <ShieldCheck size={18} className="sidebar-link-icon" />
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
