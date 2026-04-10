import React from 'react'
import './Header.css'

function Header({ auth, onLogout }) {
  const isLoggedIn = !!auth?.user

  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-text">
          <h1 className="header-title">Post-DALK Visual Correction Prediction</h1>
          <p className="header-subtitle">Clinical decision support tool</p>
        </div>
        {isLoggedIn && (
          <div className="header-actions">
            <span className="header-user">
              {auth.user.username} · {auth.user.role === 'admin' ? 'Admin' : 'Clinician'}
            </span>
            <button
              type="button"
              className="header-logout"
              onClick={onLogout}
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

export default Header

