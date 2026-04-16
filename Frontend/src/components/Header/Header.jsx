import React from 'react'
import './Header.css'

function Header({ auth, onLogout, title }) {
  const isLoggedIn = !!auth?.user

  return (
    <header className="header">
      <div className="header-inner">
        <h1 className="header-title">
          {title || 'Post-DALK Visual Correction Prediction'}
        </h1>
        {isLoggedIn && (
          <div className="header-actions">
            <span className="header-role-badge">
              {auth.user.role === 'admin' ? 'Admin' : 'Clinician'}
            </span>
            <button type="button" className="header-logout" onClick={onLogout}>
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

export default Header
