import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './PatientHistory.css'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toISOString().slice(0, 10)
  } catch {
    return iso
  }
}

function PatientHistory({ auth, onLogout }) {
  const [searchParams] = useSearchParams()
  const patientId = searchParams.get('patientId') || ''
  const eye = searchParams.get('eye') || ''
  const navigate = useNavigate()

  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedIndex, setExpandedIndex] = useState(null)

  const [patientOptions, setPatientOptions] = useState([])
  const [patientOptionsLoading, setPatientOptionsLoading] = useState(false)
  const [patientOptionsError, setPatientOptionsError] = useState(null)

  useEffect(() => {
    const token = auth?.token
    if (!token) return
    if (!patientId) {
      // User can still pick a patient from the dropdown below.
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    const url = eye
      ? `/api/patients/${encodeURIComponent(patientId)}/history?eye=${encodeURIComponent(eye)}`
      : `/api/patients/${encodeURIComponent(patientId)}/history`

    fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (cancelled) return
        if (!r.ok) throw new Error('Failed to load history')
        return r.json()
      })
      .then((data) => {
        if (cancelled) return
        setHistory(data.history || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load history')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [auth?.token, patientId, eye])

  useEffect(() => {
    const token = auth?.token
    if (!token) return
    if (patientId) return

    let cancelled = false
    setPatientOptionsLoading(true)
    setPatientOptionsError(null)

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
        setPatientOptions(data.patients || [])
      })
      .catch((err) => {
        if (!cancelled) setPatientOptionsError(err.message || 'Failed to load patients')
      })
      .finally(() => {
        if (!cancelled) setPatientOptionsLoading(false)
      })

    return () => { cancelled = true }
  }, [auth?.token, patientId])

  const uniquePatientIds = useMemo(() => {
    const set = new Set(patientOptions.map((p) => String(p.patientId)))
    return Array.from(set).sort((a, b) => (a > b ? 1 : -1))
  }, [patientOptions])

  const latest = history[0]
  const initials = (id) => {
    const s = String(id).replace(/[^a-zA-Z0-9]/g, '')
    if (s.length >= 2) return s.slice(0, 2).toUpperCase()
    return s.toUpperCase() || '—'
  }

  return (
    <div className="history-page">
      <Header auth={auth} onLogout={onLogout} />
      <div className="layout-shell">
        <Sidebar auth={auth} />
        <main className="layout-main">
      <div className="history-container">
        <section className="history-summary-card">
          <div className="history-summary-main">
            <div className="history-avatar">{initials(patientId)}</div>
            <div>
              <h2 className="history-name">Patient {patientId}</h2>
              <p className="history-id">
                {patientId}
                {eye ? ` · Eye ${eye}` : ''}
                {latest?.monthsAfterDALK != null
                  ? ` · ${latest.monthsAfterDALK} months after DALK`
                  : ''}
              </p>
            </div>
          </div>
          <div className="history-summary-meta">
            <div className="history-meta-item">
              <span className="history-meta-label">Last updated</span>
              <span className="history-meta-value">
                {latest ? formatDate(latest.createdAt) : '—'}
              </span>
            </div>
            <div className="history-meta-item">
              <span className="history-meta-label">Current plan</span>
              <span className="history-meta-value">
                {latest?.recommendedCorrection || '—'}
              </span>
            </div>
          </div>
        </section>

        <section className="history-timeline-card">
          <h3 className="history-section-title">Assessment Timeline</h3>
          {loading && <p className="history-loading">Loading…</p>}
          {error && <p className="history-error">{error}</p>}
          {!patientId && !loading && (
            <div className="history-patient-picker">
              <p style={{ marginBottom: 10 }}>
                Select a patient to view all their previous reports.
              </p>
              {patientOptionsLoading && <p className="history-loading">Loading patients…</p>}
              {patientOptionsError && <p className="history-error">{patientOptionsError}</p>}
              {!patientOptionsLoading && !patientOptionsError && (
                <select
                  className="history-patient-select"
                  defaultValue=""
                  onChange={(e) => {
                    const nextId = e.target.value
                    if (!nextId) return
                    navigate(`/history?patientId=${encodeURIComponent(nextId)}`)
                  }}
                >
                  <option value="" disabled>Select patient</option>
                  {uniquePatientIds.map((id) => (
                    <option key={id} value={id}>Patient {id}</option>
                  ))}
                </select>
              )}
            </div>
          )}
          {!patientId && !loading && !patientOptionsLoading && uniquePatientIds.length === 0 && (
            <p className="history-empty">No saved patients found yet.</p>
          )}
          {!loading && !error && patientId && history.length === 0 && (
            <p className="history-empty">No assessments found for this patient.</p>
          )}
          {!loading && !error && history.length > 0 && (
            <div className="history-timeline">
              {history.map((item, i) => (
                <div key={item.createdAt + i} className="history-timeline-row">
                  <div className="history-timeline-left">
                    <div className="history-dot" />
                    <div className="history-line" />
                  </div>
                  <div className="history-timeline-content">
                    <div className="history-date">{formatDate(item.createdAt)}</div>
                    <div className="history-event-title">
                      Assessment · {item.recommendedCorrection}
                      {item.confidence != null ? ` (${item.confidence}% confidence)` : ''}
                    </div>
                    <div className="history-event-details">
                      {item.explanation || 'No details recorded.'}
                    </div>
                    <div className="history-details-actions">
                      <button
                        type="button"
                        className="history-details-btn"
                        onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
                      >
                        {expandedIndex === i ? 'Hide report details' : 'View report details'}
                      </button>
                    </div>
                    {expandedIndex === i && (
                      <div className="history-details-card">
                        <div className="history-details-grid">
                          <div><strong>K1</strong></div>
                          <div>{item.K1_diopters != null ? `${item.K1_diopters} D` : '—'}</div>
                          <div><strong>K2</strong></div>
                          <div>{item.K2_diopters != null ? `${item.K2_diopters} D` : '—'}</div>
                          <div><strong>Corneal Astigmatism (Cyl)</strong></div>
                          <div>{item.astigmatism_diopters != null ? `${item.astigmatism_diopters} D` : '—'}</div>
                          <div><strong>Central Corneal Thickness (CCT)</strong></div>
                          <div>{item.corneal_thickness_um != null ? `${item.corneal_thickness_um} um` : '—'}</div>
                          <div><strong>Sphere</strong></div>
                          <div>{item.sphere != null ? `${item.sphere} D` : '—'}</div>
                          <div><strong>Cylinder</strong></div>
                          <div>{item.cylinder != null ? `${item.cylinder} D` : '—'}</div>
                          <div><strong>Axis</strong></div>
                          <div>{item.axis != null ? `${item.axis} deg` : '—'}</div>
                        </div>
                        {item.probabilities && (
                          <div className="history-prob-note">
                            Probabilities are saved for this report.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
        </main>
      </div>
    </div>
  )
}

export default PatientHistory
