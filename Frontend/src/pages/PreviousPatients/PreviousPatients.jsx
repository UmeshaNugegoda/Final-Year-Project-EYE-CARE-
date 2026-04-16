import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
      <Sidebar auth={auth} />
      <div className="app-main">
        <Header auth={auth} onLogout={onLogout} title="Previous Patients" />
        <main className="page-content">
          <div className="patients-container">
            <section className="patients-header">
              <div>
                <h2 className="patients-title">Previous Patients</h2>
                <p className="patients-subtitle">
                  Review existing post‑DALK patients and open their assessment history.
                </p>
              </div>
              <div className="patients-filters">
                <input
                  type="text"
                  className="patients-search"
                  placeholder="Search by Patient ID"
                  aria-label="Search patients"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </section>

            <section className="patients-table-card">
              <div className="patients-table-header">
                <span>Patient</span>
                <span>Eye</span>
                <span>Months after DALK</span>
                <span>Last assessment</span>
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
                          <div className="patients-id">{p.patientId}</div>
                        </div>
                      </div>
                      <div className="patients-cell">{p.eye}</div>
                      <div className="patients-cell">{p.monthsAfterDALK ?? '—'}</div>
                      <div className="patients-cell">{formatDate(p.lastAssessment)}</div>
                      <div className="patients-cell patients-chip">
                        <span>{p.recommendation || '—'}</span>
                      </div>
                      <div className="patients-cell">
                        <button
                          type="button"
                          className="patients-view-button"
                          onClick={() => handleViewHistory(p.patientId, p.eye)}
                        >
                          View History
                        </button>
                      </div>
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

export default PreviousPatients

