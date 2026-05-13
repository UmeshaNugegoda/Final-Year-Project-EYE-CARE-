import React, { useState } from 'react'
import { ScanLine, AlertTriangle, TrendingUp, TrendingDown, Minus, Printer } from 'lucide-react'
import { jsPDF } from 'jspdf'
import './ResultPanel.css'

const KEY_TO_STATUS_FIELD = {
  K1_diopters          : 'K1_diopters',
  K2_diopters          : 'K2_diopters',
  astigmatism_diopters : 'astigmatism_diopters',
  corneal_thickness_um : 'corneal_thickness_um',
}

const CLASS_COLORS = {
  'Spectacles'          : { badge: '#2E8A4F', bg: '#EAF7EE' },
  'Contact Lenses'      : { badge: '#0D7A6F', bg: '#E0F5F3' },
  'No Correction'       : { badge: '#1D5FA6', bg: '#E8F1FB' },
  'Refer to Specialist' : { badge: '#D97706', bg: '#FEF3C7' },
}
const DEFAULT_COLOR = { badge: '#4B5C72', bg: '#F5F7FA' }

function Accordion({ title, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="accordion">
      <button type="button" className="accordion-toggle" onClick={() => setOpen(o => !o)}>
        <span>{title}</span>
        <span className={`accordion-chevron${open ? ' open' : ''}`}>▾</span>
      </button>
      {open && <div className="accordion-body">{children}</div>}
    </div>
  )
}

function ResultPanel({ result, auth }) {
  const [ocrPopover,  setOcrPopover]  = useState(false)
  const [estPopover,  setEstPopover]  = useState(false)
  const [notes,       setNotes]       = useState('')
  const [notesSaving, setNotesSaving] = useState(false)
  const [notesSaved,  setNotesSaved]  = useState(false)

  if (!result) return null

  const colors     = CLASS_COLORS[result.recommended] || DEFAULT_COLOR
  const confidence = typeof result.confidence === 'number' ? result.confidence : null
  const confLevel  = confidence == null ? null
    : confidence >= 80 ? 'high'
    : confidence >= 60 ? 'mid'
    : 'low'

  const probEntries = result.probabilities
    ? Object.entries(result.probabilities).sort((a, b) => b[1] - a[1])
    : []

  const estimatedCount = result.extractionStatus
    ? Object.values(result.extractionStatus).filter(s => s === 'not_found').length
    : 0

  const hasOcr = !!result.extractedValues

  const handleDownloadPdf = () => {
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    const pageWidth = doc.internal.pageSize.getWidth()
    const pageHeight = doc.internal.pageSize.getHeight()
    const left = 40
    const right = pageWidth - 40
    const bottom = pageHeight - 40
    let y = 44

    const addLine = (text, opts = {}) => {
      const {
        size = 10,
        bold = false,
        gapAfter = 8,
      } = opts
      doc.setFont('helvetica', bold ? 'bold' : 'normal')
      doc.setFontSize(size)
      const wrapped = doc.splitTextToSize(String(text), right - left)
      wrapped.forEach((line) => {
        if (y > bottom) {
          doc.addPage()
          y = 44
        }
        doc.text(line, left, y)
        y += size + 4
      })
      y += gapAfter
    }

    addLine('Post-DALK Prediction Report', { size: 16, bold: true, gapAfter: 10 })
    addLine(`Generated: ${new Date().toLocaleString()}`)
    addLine(`Patient ID: ${result.patientId || '-'}`)
    addLine(`Eye: ${result.eye || '-'}`)
    addLine(`Months After DALK: ${result.monthsAfterDALK ?? '-'}`)
    addLine(`Recommended: ${result.recommended || '-'}`)
    addLine(`Confidence: ${confidence != null ? `${confidence.toFixed(1)}%` : '-'}`, { gapAfter: 14 })

    if (result.hasEstimatedValues) {
      addLine('Warning: Report contains estimated values. Verify before clinical use.', { bold: true })
    }

    addLine('Class Probabilities', { size: 12, bold: true, gapAfter: 6 })
    if (probEntries.length === 0) {
      addLine('N/A')
    } else {
      probEntries.forEach(([label, prob]) => addLine(`${label}: ${Number(prob).toFixed(1)}%`, { gapAfter: 4 }))
      y += 6
    }

    addLine('Extracted / Calculated Values', { size: 12, bold: true, gapAfter: 6 })
    const statusLabel = (key) => {
      const s = result.extractionStatus?.[key]
      if (s === 'extracted') return 'Extracted'
      if (s === 'manual_override') return 'Manual override'
      return 'Estimated'
    }
    if (!result.extractedValues || Object.keys(result.extractedValues).length === 0) {
      addLine('No extracted values')
    } else {
      Object.entries(result.extractedValues).forEach(([key, val]) => {
        const fk = KEY_TO_STATUS_FIELD[key] || key
        addLine(`${formatKey(key)}: ${String(val ?? '-')} (${statusLabel(fk)})`, { gapAfter: 4 })
      })
      y += 6
    }

    addLine('Clinical Explanation', { size: 12, bold: true, gapAfter: 6 })
    addLine(result.explanation || '-')

    const safePatient = String(result.patientId || 'patient').replace(/[^a-zA-Z0-9_-]/g, '_')
    const safeEye = String(result.eye || 'eye').replace(/[^a-zA-Z0-9_-]/g, '_')
    const stamp = new Date().toISOString().slice(0, 10)
    doc.save(`prediction-report-${safePatient}-${safeEye}-${stamp}.pdf`)
  }

  const isReferral = result.recommended === 'Refer to Specialist'

  return (
    <section className="result-panel">

      {/* ── Referral banner ── */}
      {isReferral && (
        <div className="referral-banner">
          <AlertTriangle size={16} />
          <div>
            <strong>Confidence below clinical threshold ({confidence?.toFixed(1)}%)</strong>
            <p>The model cannot make a reliable recommendation with the available data. Please refer this patient to a specialist for manual assessment.</p>
          </div>
        </div>
      )}

      {/* ── Main recommendation + confidence ── */}
      <div className="result-main">
        <div className="result-recommendation" style={{ background: colors.bg }}>
          <span className="result-rec-label">Recommendation</span>
          <span className="result-rec-badge" style={{ background: colors.badge }}>
            {result.recommended}
          </span>
        </div>

        <div className="result-confidence-block">
          <span className="result-rec-label">Confidence</span>
          <span className={`result-conf-value conf-${confLevel}`}>
            {confidence != null ? `${confidence.toFixed(1)}%` : result.confidence}
          </span>
        </div>

        <div className="result-actions">
          <button type="button" className="result-pdf-btn" onClick={handleDownloadPdf}>
            ↓ Save as PDF
          </button>
          <button type="button" className="result-print-btn" onClick={() => window.print()}>
            <Printer size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} /> Print Report
          </button>
          {result.historySaved && (
            <span className="result-saved-note">✓ Saved to history</span>
          )}
        </div>
      </div>

      {/* ── Compact status chips ── */}
      <div className="result-chips">
        {hasOcr && (
          <div className="chip-wrap">
            <button
              type="button"
              className="info-chip"
              onClick={() => setOcrPopover(v => !v)}
            >
              <ScanLine size={13} /> OCR extracted
            </button>
            {ocrPopover && (
              <div className="chip-popover">
                Values read automatically from uploaded images. Accuracy depends on image quality — always verify against the original report.
              </div>
            )}
          </div>
        )}

        {result.hasEstimatedValues && estimatedCount > 0 && (
          <div className="chip-wrap">
            <button
              type="button"
              className="warn-chip"
              onClick={() => setEstPopover(v => !v)}
            >
              <AlertTriangle size={13} /> {estimatedCount} estimated value{estimatedCount > 1 ? 's' : ''}
            </button>
            {estPopover && (
              <div className="chip-popover">
                {estimatedCount} field{estimatedCount > 1 ? 's' : ''} could not be extracted and{' '}
                {estimatedCount > 1 ? 'were' : 'was'} filled with population averages.
                Not suitable for clinical decisions without verification.
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Collapsible sections ── */}
      <div className="result-accordions">

        {probEntries.length > 0 && (
          <Accordion title="Class Probabilities">
            <div className="prob-list">
              {probEntries.map(([label, prob]) => {
                const c = CLASS_COLORS[label] || DEFAULT_COLOR
                return (
                  <div key={label} className="prob-row">
                    <span className="prob-label">{label}</span>
                    <div className="prob-track">
                      <div className="prob-fill" style={{ width: `${prob}%`, background: c.badge }} />
                    </div>
                    <span className="prob-value">{prob.toFixed(1)}%</span>
                  </div>
                )
              })}
            </div>
          </Accordion>
        )}

        {result.extractedValues && (
          <Accordion title="Extracted Values">
            <div className="extracted-grid">
              {Object.entries(result.extractedValues).map(([key, val]) => {
                const fk     = KEY_TO_STATUS_FIELD[key]
                const status = fk ? (result.extractionStatus?.[fk] || 'not_found') : null
                const isK2   = key === 'K2_diopters'
                return (
                  <div key={key} className="extracted-item">
                    <span className="extracted-key">
                      {formatKey(key)}
                      {isK2 && result.k2Derived && (
                        <span className="k2-derived-note" title="K2 was calculated as K1 + |Cyl| — not directly extracted">
                          calc
                        </span>
                      )}
                    </span>
                    <span className="extracted-val">{val ?? '—'}</span>
                    {status === 'extracted'       && <span className="badge-extracted">Extracted</span>}
                    {status === 'manual_override' && <span className="badge-override">Manual</span>}
                    {status === 'not_found'       && <span className="badge-estimated">Estimated</span>}
                  </div>
                )
              })}
            </div>
          </Accordion>
        )}

        {result.explanation && (
          <Accordion title="Clinical Explanation" defaultOpen={false}>
            <p className="result-explanation">{result.explanation}</p>
          </Accordion>
        )}

      </div>

      {/* ── Prior assessment comparison ── */}
      {result.priorAssessment && (
        <div className="prior-assessment">
          <span className="prior-label">vs. last visit ({result.priorAssessment.createdAt?.slice(0,10)})</span>
          <div className="prior-row">
            <span className="prior-field">Recommendation</span>
            <span className="prior-value">
              {result.priorAssessment.recommendedCorrection}
              {result.priorAssessment.recommendedCorrection === result.recommended
                ? <span className="prior-unchanged">unchanged</span>
                : <span className="prior-changed">→ {result.recommended}</span>}
            </span>
          </div>
          <div className="prior-row">
            <span className="prior-field">Confidence</span>
            <span className="prior-value">
              {result.priorAssessment.confidence?.toFixed(1)}%
              {result.confidence != null && result.priorAssessment.confidence != null && (() => {
                const delta = result.confidence - result.priorAssessment.confidence
                if (Math.abs(delta) < 0.5) return <span className="prior-delta neutral"><Minus size={12}/></span>
                return delta > 0
                  ? <span className="prior-delta up"><TrendingUp size={12}/> +{delta.toFixed(1)}%</span>
                  : <span className="prior-delta down"><TrendingDown size={12}/> {delta.toFixed(1)}%</span>
              })()}
            </span>
          </div>
        </div>
      )}

      {/* ── Clinician notes ── */}
      {result.recordId && (
        <div className="clinician-notes">
          <label className="notes-label" htmlFor="clinician-notes-input">Clinician Notes</label>
          <textarea
            id="clinician-notes-input"
            className="notes-textarea"
            placeholder="Add clinical notes, observations, or patient preferences…"
            value={notes}
            onChange={e => { setNotes(e.target.value); setNotesSaved(false) }}
            rows={3}
          />
          <div className="notes-actions">
            <button
              type="button"
              className="notes-save-btn"
              disabled={notesSaving || !notes.trim()}
              onClick={async () => {
                setNotesSaving(true)
                try {
                  await fetch(`/api/predictions/${result.recordId}/notes`, {
                    method: 'PATCH',
                    headers: {
                      'Content-Type': 'application/json',
                      ...(auth?.token ? { Authorization: `Bearer ${auth.token}` } : {}),
                    },
                    body: JSON.stringify({ notes }),
                  })
                  setNotesSaved(true)
                } catch { /* non-fatal */ }
                finally { setNotesSaving(false) }
              }}
            >
              {notesSaving ? 'Saving…' : 'Save Notes'}
            </button>
            {notesSaved && <span className="notes-saved-indicator">✓ Saved</span>}
          </div>
        </div>
      )}

    </section>
  )
}

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1')
    .replace(/\b\w/g, c => c.toUpperCase()).trim()
}

export default ResultPanel
