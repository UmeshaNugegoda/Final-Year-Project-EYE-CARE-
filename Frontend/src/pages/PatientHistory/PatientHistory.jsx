import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './PatientHistory.css'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

function formatMeasurement(extracted, estimated, unit) {
  if (extracted != null) return `${extracted} ${unit}`
  if (estimated != null) return (
    <span className="history-estimated-val">
      {Number(estimated).toFixed(2)} {unit}
      <span className="history-estimated-badge">Est.</span>
    </span>
  )
  return '—'
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
  }, [auth?.token])

  const uniquePatientIds = useMemo(() => {
    const set = new Set(patientOptions.map((p) => String(p.patientId)))
    return Array.from(set).sort((a, b) => (a > b ? 1 : -1))
  }, [patientOptions])

  const latest  = history[0]
  const oldest  = history[history.length - 1]
  const initials = (id) => {
    const s = String(id).replace(/[^a-zA-Z0-9]/g, '')
    if (s.length >= 2) return s.slice(0, 2).toUpperCase()
    return s.toUpperCase() || '?'
  }

  // Derive eye options from loaded patients list for the selected patient
  const eyeOptions = useMemo(() => {
    if (!patientId) return []
    const eyes = new Set(
      patientOptions
        .filter((p) => String(p.patientId) === patientId && p.eye)
        .map((p) => p.eye)
    )
    return Array.from(eyes).sort()
  }, [patientOptions, patientId])

  return (
    <div className="app-shell">
      <Sidebar auth={auth} onLogout={onLogout} />
      <div className="app-main">
        <main className="page-content">
          <Header
            title="Patient History"
            subtitle={
              patientId
                ? `Assessment timeline for Patient ${patientId}${eye ? ` · Eye ${eye}` : ''}`
                : 'Select a patient to view their assessment timeline'
            }
          />

          <div className="history-container">

            {/* ── No patient selected: Welcome / picker card ── */}
            {!patientId && (
              <section className="history-welcome-card">
                <div className="history-welcome-icon">
                  <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" opacity="0.3"/>
                    <path d="M8 24C8 24 14 14 24 14C34 14 40 24 40 24C40 24 34 34 24 34C14 34 8 24 8 24Z" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round"/>
                    <circle cx="24" cy="24" r="6" stroke="currentColor" strokeWidth="2.2"/>
                    <circle cx="24" cy="24" r="2.5" fill="currentColor"/>
                  </svg>
                </div>
                <div className="history-welcome-text">
                  <h2 className="history-welcome-title">Patient Assessment History</h2>
                  <p className="history-welcome-sub">
                    Choose a patient below to explore their full DALK follow-up timeline, clinical measurements, AI predictions, and clinician notes.
                  </p>
                </div>

                <div className="history-welcome-stats">
                  <div className="history-stat-chip">
                    <span className="history-stat-value">
                      {patientOptionsLoading ? '…' : uniquePatientIds.length}
                    </span>
                    <span className="history-stat-label">Total Patients</span>
                  </div>
                  <div className="history-stat-chip">
                    <span className="history-stat-value">
                      {patientOptionsLoading ? '…' : patientOptions.length}
                    </span>
                    <span className="history-stat-label">Total Records</span>
                  </div>
                </div>

                <div className="history-picker-block">
                  <label className="history-picker-label" htmlFor="patient-select">
                    Select Patient ID
                  </label>
                  {patientOptionsLoading && <p className="history-loading">Loading patients…</p>}
                  {patientOptionsError && <p className="history-error">{patientOptionsError}</p>}
                  {!patientOptionsLoading && !patientOptionsError && (
                    <select
                      id="patient-select"
                      className="history-patient-select"
                      defaultValue=""
                      onChange={(e) => {
                        const nextId = e.target.value
                        if (!nextId) return
                        navigate(`/history?patientId=${encodeURIComponent(nextId)}`)
                      }}
                    >
                      <option value="" disabled>Choose a patient…</option>
                      {uniquePatientIds.map((id) => (
                        <option key={id} value={id}>Patient {id}</option>
                      ))}
                    </select>
                  )}
                  {!patientOptionsLoading && !patientOptionsError && uniquePatientIds.length === 0 && (
                    <p className="history-empty" style={{ marginTop: 12 }}>No saved patients found yet.</p>
                  )}
                </div>
              </section>
            )}

            {/* ── Patient selected: rich summary card ── */}
            {patientId && (
              <section className="history-summary-card">
                <div className="history-summary-main">
                  <div className="history-avatar">{initials(patientId)}</div>
                  <div>
                    <h2 className="history-name">Patient {patientId}</h2>
                    <p className="history-id">
                      ID: {patientId}
                      {eye ? <span className="history-eye-badge">Eye {eye}</span> : null}
                      {latest?.monthsAfterDALK != null
                        ? ` · ${latest.monthsAfterDALK} months post-DALK`
                        : ''}
                    </p>
                  </div>
                </div>

                <div className="history-summary-meta">
                  <div className="history-meta-item">
                    <span className="history-meta-label">Assessments</span>
                    <span className="history-meta-value">
                      {loading ? '…' : history.length || '—'}
                    </span>
                  </div>
                  <div className="history-meta-item">
                    <span className="history-meta-label">First Visit</span>
                    <span className="history-meta-value">
                      {oldest ? formatDate(oldest.createdAt) : '—'}
                    </span>
                  </div>
                  <div className="history-meta-item">
                    <span className="history-meta-label">Last Updated</span>
                    <span className="history-meta-value">
                      {latest ? formatDate(latest.createdAt) : '—'}
                    </span>
                  </div>
                  <div className="history-meta-item">
                    <span className="history-meta-label">Current Plan</span>
                    <span className="history-meta-value history-plan-value">
                      {latest?.recommendedCorrection || '—'}
                    </span>
                  </div>
                </div>

                {/* Eye filter pills (if multiple eyes exist) */}
                {eyeOptions.length > 1 && (
                  <div className="history-eye-filter">
                    <button
                      className={`history-eye-pill${!eye ? ' active' : ''}`}
                      onClick={() => navigate(`/history?patientId=${encodeURIComponent(patientId)}`)}
                    >Both Eyes</button>
                    {eyeOptions.map((e2) => (
                      <button
                        key={e2}
                        className={`history-eye-pill${eye === e2 ? ' active' : ''}`}
                        onClick={() => navigate(`/history?patientId=${encodeURIComponent(patientId)}&eye=${encodeURIComponent(e2)}`)}
                      >Eye {e2}</button>
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* ── Timeline card (only when patient selected) ── */}
            {patientId && (
              <section className="history-timeline-card">
                <h3 className="history-section-title">Assessment Timeline</h3>
                {loading && <p className="history-loading">Loading…</p>}
                {error && <p className="history-error">{error}</p>}
                {!loading && !error && history.length === 0 && (
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
                                <div><strong>UCVA</strong></div>
                                <div>{item.ucva_snellen || (item.ucva_logmar != null ? `${item.ucva_logmar} logMAR` : '—')}</div>
                                <div><strong>BCVA</strong></div>
                                <div>{item.bcva_snellen || (item.bcva_logmar != null ? `${item.bcva_logmar} logMAR` : '—')}</div>
                                <div><strong>Sphere</strong></div>
                                <div>{item.sphere != null ? `${item.sphere} D` : '—'}</div>
                                <div><strong>Cylinder</strong></div>
                                <div>{item.cylinder != null ? `${item.cylinder} D` : '—'}</div>
                                <div><strong>Axis</strong></div>
                                <div>{item.axis != null ? `${item.axis}°` : '—'}</div>
                                <div><strong>K1 (Flat)</strong></div>
                                <div>{formatMeasurement(item.K1_diopters, item.estimatedFeatures?.K1_diopters, 'D')}</div>
                                <div><strong>K2 (Steep)</strong></div>
                                <div>{formatMeasurement(item.K2_diopters, item.estimatedFeatures?.K2_diopters, 'D')}</div>
                                <div><strong>Corneal Cyl</strong></div>
                                <div>{formatMeasurement(item.astigmatism_diopters, item.estimatedFeatures?.astigmatism_diopters, 'D')}</div>
                                <div><strong>CCT</strong></div>
                                <div>{formatMeasurement(item.corneal_thickness_um, item.estimatedFeatures?.corneal_thickness_um, 'µm')}</div>
                              </div>
                              {item.probabilities && (
                                <div className="history-prob-note">
                                  Probabilities are saved for this report.
                                </div>
                              )}
                              {item.clinicianNotes && (
                                <div className="history-clinician-notes">
                                  <span className="history-notes-label">Clinician Notes</span>
                                  <p className="history-notes-text">{item.clinicianNotes}</p>
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
            )}

          </div>
        </main>
      </div>
    </div>
  )
}

export default PatientHistory
