import React, { useEffect, useState } from 'react'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './Profile.css'

function Profile({ auth, onLogout }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const token = auth?.token
    if (!token) return

    let cancelled = false
    setLoading(true)
    setError(null)

    fetch('/api/users/me/profile', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load your profile.')
        return r.json()
      })
      .then((data) => {
        if (cancelled) return
        setProfile(data.user || null)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load your profile.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [auth?.token])

  const name = profile?.username || auth?.user?.username || 'User'
  const photoDataUrl = profile?.doctorProfile?.photoBase64
    ? `data:${profile?.doctorProfile?.photoMimeType || 'image/jpeg'};base64,${profile.doctorProfile.photoBase64}`
    : ''
  const description = profile?.doctorProfile?.description || 'No profile description added yet.'
  const roleLabel = profile?.role === 'admin' ? 'Administrator' : 'Clinician'

  return (
    <div className="app-shell">
      <Sidebar auth={auth} onLogout={onLogout} />
      <div className="app-main">
        <main className="page-content">
          <Header
            title="My Profile"
            subtitle="Your account details and clinician information"
          />

          <div className="profile-container">
            <section className="profile-card">
              {loading && <p className="profile-loading">Loading profile...</p>}
              {error && <p className="profile-error">{error}</p>}
              {!loading && !error && (
                <>
                  <div className="profile-top">
                    <div className="profile-avatar">
                      {photoDataUrl
                        ? <img src={photoDataUrl} alt={name} />
                        : <span>{String(name).slice(0, 2).toUpperCase()}</span>}
                    </div>
                    <div className="profile-title-block">
                      <h2>{name}</h2>
                      <p>{roleLabel}</p>
                    </div>
                  </div>

                  <div className="profile-details">
                    <div className="profile-detail-item">
                      <span className="profile-detail-label">Username</span>
                      <span className="profile-detail-value">{name}</span>
                    </div>
                    <div className="profile-detail-item">
                      <span className="profile-detail-label">Role</span>
                      <span className="profile-detail-value">{roleLabel}</span>
                    </div>
                    <div className="profile-detail-item profile-detail-item-full">
                      <span className="profile-detail-label">Description</span>
                      <p className="profile-description">{description}</p>
                    </div>
                  </div>
                </>
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  )
}

export default Profile
