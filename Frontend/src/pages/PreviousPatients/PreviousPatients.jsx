import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, History, Users, CheckCircle, TrendingUp } from 'lucide-react'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './PreviousPatients.css'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toISOString().slice(0, 10)
  } catch {
    return iso
  }
}

function PreviousPatients({ auth, onLogout }) {
  const navigate = useNavigate()
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const token = auth?.token
    if (!token) return

    let cancelled = false
    setLoading(true)
    setError(null)

    fetch('/api/patients', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (cancelled) return
        if (!r.ok) throw new Error('Failed to load patients')
        return r.json()
      })
      .then((data) => {
        if (cancelled) return
        setPatients(data.patients || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load patients')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [auth?.token])

  const filtered = patients.filter(
    (p) =>
      !search.trim() ||
      String(p.patientId).toLowerCase().includes(search.toLowerCase())
  )

  const handleViewHistory = (patientId, eye) => {
    navigate(`/history?patientId=${encodeURIComponent(patientId)}&eye=${encodeURIComponent(eye || '')}`)
  }

  const initials = (patientId) => {
    const s = String(patientId).replace(/[^a-zA-Z0-9]/g, '')
    if (s.length >= 2) return s.slice(0, 2).toUpperCase()
    return s.toUpperCase() || '—'
  }

  return (
    <div className="app-shell">
      <Sidebar auth={auth} onLogout={onLogout} />
      <div className="app-main">
        <main className="page-content">

          <Header
            title="Previous Patients"
            subtitle="Review existing post-DALK patients and open their assessment history"
            searchValue={search}
            onSearch={(e) => setSearch(e.target.value)}
            searchPlaceholder="Search by Patient ID…"
          />

          <div className="patients-container">
            {/* ── Stats summary ── */}
            {!loading && !error && (
              <div className="patients-summary-row">
                {/* Card 1 */}
                <div className="patients-summary-card">
                  <div className="patients-summary-top">
                    <span className="patients-summary-label">Total Patients</span>
                    <Users size={16} className="patients-summary-icon" />
                  </div>
                  <span className="patients-summary-value">{patients.length}</span>
                  <div className="patients-summary-trend">
                    <span className="trend-pill trend-up"><TrendingUp size={12} /> 12%</span>
                    <span className="trend-text">All time</span>
                  </div>
                </div>
                {/* Card 2 */}
                <div className="patients-summary-card">
                  <div className="patients-summary-top">
                    <span className="patients-summary-label">Active Patients</span>
                    <CheckCircle size={16} className="patients-summary-icon" />
                  </div>
                  <span className="patients-summary-value">{filtered.length}</span>
                  <div className="patients-summary-trend">
                    <span className="trend-pill trend-up"><TrendingUp size={12} /> 100%</span>
                    <span className="trend-text">Active Ratio</span>
                  </div>
                </div>
              </div>
            )}

            {/* ── Table Top ── */}
            <div className="table-topbar">
              <h3 className="table-title">All Patients</h3>
            </div>

            {/* ── Table ── */}
            <section className="patients-table-card">
              <div className="patients-table-header">
                <span>Patient</span>
                <span>Eye</span>
                <span>Months after DALK</span>
                <span>Last Assessment</span>
                <span>Correction</span>
                <span>Action</span>
              </div>
              <div className="patients-table-body">
                {loading && (
                  <div className="patients-row patients-row-message">
                    <span>Loading…</span>
                  </div>
                )}
                {error && (
                  <div className="patients-row patients-row-message patients-row-error">
                    <span>{error}</span>
                  </div>
                )}
                {!loading && !error && filtered.length === 0 && (
                  <div className="patients-row patients-row-message">
                    <span>No patients found.</span>
                  </div>
                )}
                {!loading &&
                  !error &&
                  filtered.map((p) => (
                    <div key={`${p.patientId}-${p.eye}`} className="patients-row">
                      <div className="patients-cell-main">
                        <div className="patients-avatar">{initials(p.patientId)}</div>
                        <div className="patients-text">
                          <div className="patients-name">Patient {p.patientId}</div>
                          <div className="patients-id">#{p.patientId}</div>
                        </div>
                      </div>
                      <div className="patients-cell">{p.eye}</div>
                      <div className="patients-cell">{p.monthsAfterDALK ?? '—'}</div>
                      <div className="patients-cell">{formatDate(p.lastAssessment)}</div>
                      <div className="patients-cell patients-chip">
                        <span className={
                          p.recommendation === 'Spectacles'    ? 'chip-blue' :
                          p.recommendation === 'Contact Lenses'? 'chip-purple' :
                          p.recommendation ? 'chip-teal' : 'chip-muted'
                        }>{p.recommendation || '—'}</span>
                      </div>
                      <div className="patients-cell">
                        <button
                          type="button"
                          className="patients-view-button"
                          onClick={() => handleViewHistory(p.patientId, p.eye)}
                        >
                          <History size={13} />
                          View History
                        </button>
                      </div>
                    </div>
                  ))}
              </div>

              {!loading && filtered.length > 0 && (
                <div className="patients-table-footer">
                  Showing {filtered.length} of {patients.length} patient{patients.length !== 1 ? 's' : ''}
                </div>
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  )
}

export default PreviousPatients
