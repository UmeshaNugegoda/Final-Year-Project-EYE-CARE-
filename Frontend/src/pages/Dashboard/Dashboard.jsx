import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './Dashboard.css'

function formatTimeAgo(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const sec = Math.floor((now - d) / 1000)
  if (sec < 60) return 'Just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} minute${min !== 1 ? 's' : ''} ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} hour${hr !== 1 ? 's' : ''} ago`
  const day = Math.floor(hr / 24)
  return `${day} day${day !== 1 ? 's' : ''} ago`
}

function Dashboard({ auth, onLogout }) {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const token = auth?.token
    if (!token) return

    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      fetch('/api/dashboard/stats', {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch('/api/dashboard/activity', {
        headers: { Authorization: `Bearer ${token}` },
      }),
    ])
      .then(([r1, r2]) => {
        if (cancelled) return
        if (!r1.ok) throw new Error('Failed to load stats')
        if (!r2.ok) throw new Error('Failed to load activity')
        return Promise.all([r1.json(), r2.json()])
      })
      .then(([statsData, activityData]) => {
        if (cancelled) return
        setStats(statsData)
        setActivity(activityData.activity || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load dashboard')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [auth?.token])

  const handleNewAssessment = () => navigate('/prediction')
  const handlePreviousPatients = () => navigate('/patients')
  const handlePatientHistory = () => navigate('/history')

  const overviewCards = stats
    ? [
        {
          title: 'Total Patients Assessed',
          value: stats.totalAssessments.toLocaleString(),
          icon: '👁️',
          accentClass: 'overview-card-accent-green',
        },
        {
          title: 'Glasses Recommendations',
          value: stats.glasses.toLocaleString(),
          icon: '👓',
          accentClass: 'overview-card-accent-blue',
        },
        {
          title: 'Contact Lens Recommendations',
          value: stats.contactLenses.toLocaleString(),
          icon: '🟣',
          accentClass: 'overview-card-accent-purple',
        },
        {
          title: 'No Correction Needed',
          value: stats.noCorrection.toLocaleString(),
          icon: '✅',
          accentClass: 'overview-card-accent-teal',
        },
      ]
    : []

  const activityType = (rec) => {
    if (rec === 'Spectacles') return 'assessment'
    if (rec === 'Contact Lenses') return 'contact'
    return 'followup'
  }

  return (
    <div className="dashboard-page">
      <Header auth={auth} onLogout={onLogout} />
      <div className="layout-shell">
        <Sidebar auth={auth} />
        <main className="layout-main">
          <div className="dashboard-container">
            <section className="dashboard-section">
              <h2 className="dashboard-section-title">Dashboard Overview</h2>
              {loading && <p className="dashboard-loading">Loading…</p>}
              {error && <p className="dashboard-error">{error}</p>}
              {!loading && !error && (
                <div className="dashboard-overview-grid">
                  {overviewCards.map((card) => (
                    <div key={card.title} className={`overview-card ${card.accentClass}`}>
                      <div className="overview-card-header">
                        <span className="overview-card-label">{card.title}</span>
                        <span className="overview-card-icon">{card.icon}</span>
                      </div>
                      <div className="overview-card-value">{card.value}</div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="dashboard-section">
              <h2 className="dashboard-section-title">Quick Actions</h2>
              <div className="dashboard-quick-grid">
                <article className="quick-card quick-card-primary">
                  <div className="quick-card-icon">👤</div>
                  <h3 className="quick-card-title">New Patient Assessment</h3>
                  <p className="quick-card-text">
                    Start a comprehensive eye examination for a new post‑DALK patient.
                  </p>
                  <button
                    type="button"
                    className="quick-card-button primary"
                    onClick={handleNewAssessment}
                  >
                    Begin Assessment
                  </button>
                </article>
                <article className="quick-card">
                  <div className="quick-card-icon">🌀</div>
                  <h3 className="quick-card-title">Previous Patients</h3>
                  <p className="quick-card-text">
                    View and manage existing post‑DALK patients and prior assessments.
                  </p>
                  <button
                    type="button"
                    className="quick-card-button"
                    onClick={handlePreviousPatients}
                  >
                    View Patients
                  </button>
                </article>
                <article className="quick-card">
                  <div className="quick-card-icon">📄</div>
                  <h3 className="quick-card-title">Patient History</h3>
                  <p className="quick-card-text">
                    Review detailed visual outcomes, refractions, and recommendations over time.
                  </p>
                  <button
                    type="button"
                    className="quick-card-button"
                    onClick={handlePatientHistory}
                  >
                    Browse History
                  </button>
                </article>
              </div>
            </section>

            <section className="dashboard-section">
              <h2 className="dashboard-section-title">Recent Activity</h2>
              <div className="dashboard-activity-card">
                {loading && <p className="dashboard-loading">Loading…</p>}
                {!loading && activity.length === 0 && (
                  <p className="dashboard-empty">No recent assessments yet.</p>
                )}
                {!loading &&
                  activity.length > 0 &&
                  activity.map((item, i) => (
                    <div key={item.createdAt + i} className="activity-row">
                      <div className={`activity-icon activity-icon-${activityType(item.recommendation)}`} />
                      <div className="activity-text">
                        <div className="activity-title">Patient assessment completed</div>
                        <div className="activity-subtitle">
                          {item.patientId} · Eye {item.eye} · {item.recommendation}
                        </div>
                      </div>
                      <div className="activity-time">{formatTimeAgo(item.createdAt)}</div>
                    </div>
                  ))}
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  )
}

export default Dashboard
