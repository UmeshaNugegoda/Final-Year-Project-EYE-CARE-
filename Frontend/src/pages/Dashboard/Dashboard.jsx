import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Eye, Glasses, Focus, CheckCircle2,
  ClipboardPlus, Users, FileText, Clock,
  TrendingUp,
} from 'lucide-react'
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
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  return `${day}d ago`
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toISOString().slice(0, 10)
}

function Dashboard({ auth, onLogout }) {
  const navigate = useNavigate()
  const [stats,    setStats]    = useState(null)
  const [activity, setActivity] = useState([])
  const [due,      setDue]      = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    const token = auth?.token
    if (!token) return

    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      fetch('/api/dashboard/stats',             { headers: { Authorization: `Bearer ${token}` } }),
      fetch('/api/dashboard/activity',          { headers: { Authorization: `Bearer ${token}` } }),
      fetch('/api/dashboard/due-reassessment',  { headers: { Authorization: `Bearer ${token}` } }),
    ])
      .then(([r1, r2, r3]) => {
        if (cancelled) return
        if (r1.status === 401 || r2.status === 401) { onLogout(); return }
        if (!r1.ok) throw new Error('Failed to load stats')
        if (!r2.ok) throw new Error('Failed to load activity')
        return Promise.all([r1.json(), r2.json(), r3.ok ? r3.json() : Promise.resolve({ due: [] })])
      })
      .then(([statsData, activityData, dueData]) => {
        if (cancelled) return
        setStats(statsData)
        setActivity(activityData.activity || [])
        setDue(dueData.due || [])
      })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load dashboard') })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [auth?.token])

  const overviewCards = stats ? [
    { title: 'Total Assessed',  value: stats.totalAssessments, Icon: Eye,          colorClass: 'ic-teal'   },
    { title: 'Spectacles',      value: stats.glasses,          Icon: Glasses,      colorClass: 'ic-blue'   },
    { title: 'Contact Lenses',  value: stats.contactLenses,    Icon: Focus,        colorClass: 'ic-purple' },
    { title: 'No Correction',   value: stats.noCorrection,     Icon: CheckCircle2, colorClass: 'ic-green'  },
  ] : []

  const recChip = (rec) => {
    if (rec === 'Spectacles')    return 'chip-blue'
    if (rec === 'Contact Lenses') return 'chip-purple'
    return 'chip-teal'
  }

  return (
    <div className="app-shell">
      <Sidebar auth={auth} onLogout={onLogout} />
      <div className="app-main">
        <main className="page-content">

          <Header
            title="Dashboard"
            subtitle="Overview of your post-DALK clinical assessments"
            action={{ label: '+ New Assessment', onClick: () => navigate('/prediction') }}
          />

          <div className="dashboard-container">

            {/* ── Stats row ── */}
            {loading && <p className="dashboard-loading">Loading…</p>}
            {error   && <p className="dashboard-error">{error}</p>}
            {!loading && !error && (
              <div className="stats-grid">
                {overviewCards.map(({ title, value, Icon, colorClass }) => (
                  <div key={title} className="stat-card">
                    <div className="stat-card-left">
                      <span className="stat-label">{title}</span>
                      <span className="stat-value">{value?.toLocaleString() ?? '—'}</span>
                      <span className="stat-trend">
                        <TrendingUp size={12} className="stat-trend-icon" />
                        All time
                      </span>
                    </div>
                    <div className={`stat-icon-box ${colorClass}`}>
                      <Icon size={22} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Quick actions ── */}
            <section className="dashboard-section">
              <h2 className="dashboard-section-title">Quick Actions</h2>
              <div className="actions-grid">
                <article className="action-card action-card-primary">
                  <div className="action-icon-box">
                    <ClipboardPlus size={22} />
                  </div>
                  <h3 className="action-title">New Patient Assessment</h3>
                  <p className="action-desc">
                    Start a comprehensive eye examination for a new post‑DALK patient.
                  </p>
                  <button type="button" className="action-btn action-btn-primary" onClick={() => navigate('/prediction')}>
                    Begin Assessment
                  </button>
                </article>

                <article className="action-card">
                  <div className="action-icon-box action-icon-muted">
                    <Users size={22} />
                  </div>
                  <h3 className="action-title">Previous Patients</h3>
                  <p className="action-desc">
                    View and manage existing post‑DALK patients and prior assessments.
                  </p>
                  <button type="button" className="action-btn" onClick={() => navigate('/patients')}>
                    View Patients
                  </button>
                </article>

                <article className="action-card">
                  <div className="action-icon-box action-icon-muted">
                    <FileText size={22} />
                  </div>
                  <h3 className="action-title">Patient History</h3>
                  <p className="action-desc">
                    Review visual outcomes, refractions, and recommendations over time.
                  </p>
                  <button type="button" className="action-btn" onClick={() => navigate('/history')}>
                    Browse History
                  </button>
                </article>
              </div>
            </section>

            {/* ── Due for re-assessment ── */}
            {!loading && due.length > 0 && (
              <section className="dashboard-section">
                <h2 className="dashboard-section-title">
                  Due for Re-assessment
                  <span className="due-count-badge">{due.length}</span>
                </h2>
                <div className="due-card">
                  {due.map((p, i) => (
                    <div key={`${p.patientId}-${p.eye}-${i}`} className="due-row">
                      <div className="due-avatar">{String(p.patientId).slice(0,2).toUpperCase()}</div>
                      <div className="due-body">
                        <span className="due-patient">Patient {p.patientId} · Eye {p.eye}</span>
                        <span className="due-meta">
                          Last seen {formatDate(p.lastAssessment)} · {p.recommendation || '—'}
                        </span>
                      </div>
                      <div className="due-right">
                        <span className={`due-overdue-badge ${p.daysOverdue > 30 ? 'overdue-urgent' : 'overdue-soon'}`}>
                          <Clock size={11} />
                          {p.daysOverdue === 0 ? 'Due today' : `${p.daysOverdue}d overdue`}
                        </span>
                        <button
                          type="button"
                          className="due-assess-btn"
                          onClick={() => navigate(`/prediction?patientId=${encodeURIComponent(p.patientId)}&eye=${p.eye}`)}
                        >
                          Assess
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── Recent activity ── */}
            <section className="dashboard-section">
              <h2 className="dashboard-section-title">Recent Activity</h2>
              <div className="activity-card">
                {/* table header */}
                <div className="activity-table-header">
                  <span>Patient</span>
                  <span>Eye</span>
                  <span>Recommendation</span>
                  <span>Time</span>
                </div>
                {loading && <p className="dashboard-loading" style={{ padding: '20px 20px' }}>Loading…</p>}
                {!loading && activity.length === 0 && (
                  <p className="dashboard-empty">No recent assessments yet.</p>
                )}
                {!loading && activity.length > 0 && activity.map((item, i) => (
                  <div key={item.createdAt + i} className="activity-row">
                    <div className="activity-patient-cell">
                      <div className="activity-avatar">
                        {String(item.patientId || '').slice(0,2).toUpperCase() || '—'}
                      </div>
                      <span className="activity-title">Patient {item.patientId}</span>
                    </div>
                    <span className="activity-eye">{item.eye}</span>
                    <span className={`activity-chip ${recChip(item.recommendation)}`}>
                      {item.recommendation}
                    </span>
                    <span className="activity-time">{formatTimeAgo(item.createdAt)}</span>
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
