import React, { useState } from 'react'
import './ResultPanel.css'

const KEY_TO_STATUS_FIELD = {
  K1_diopters          : 'K1_diopters',
  K2_diopters          : 'K2_diopters',
  astigmatism_diopters : 'astigmatism_diopters',
  corneal_thickness_um : 'corneal_thickness_um',
}

const CLASS_COLORS = {
  'Spectacles'    : { badge: '#2E8A4F', bg: '#EAF7EE' },
  'Contact Lenses': { badge: '#0D7A6F', bg: '#E0F5F3' },
  'No Correction' : { badge: '#1D5FA6', bg: '#E8F1FB' },
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

function ResultPanel({ result }) {
  const [ocrPopover, setOcrPopover] = useState(false)
  const [estPopover, setEstPopover] = useState(false)

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
    const win = window.open('', '_blank')
    if (!win) return

    const statusLabel = (key) => {
      const s = result.extractionStatus?.[key]
      if (s === 'extracted')       return ' [Extracted]'
      if (s === 'manual_override') return ' [Manual override]'
      return ' [Estimated]'
    }

    const extractedRows = result.extractedValues
      ? Object.entries(result.extractedValues)
          .map(([key, val]) => {
            const fk = KEY_TO_STATUS_FIELD[key] || key
            return `<tr><td>${escapeHtml(formatKey(key))}</td><td>${escapeHtml(String(val ?? '-'))}${escapeHtml(statusLabel(fk))}</td></tr>`
          }).join('')
      : ''

    const probRows = probEntries
      .map(([label, prob]) => `<tr><td>${escapeHtml(label)}</td><td>${Number(prob).toFixed(1)}%</td></tr>`)
      .join('')

    const estimationWarning = result.hasEstimatedValues
      ? `<div style="background:#FEF3C7;border:1px solid #fbbf24;border-left:4px solid #D97706;border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:#92400e;">
           <strong>⚠ Contains estimated values</strong> — one or more corneal measurements could not be extracted and were replaced with population averages. Not suitable for clinical decision-making without manual verification.
         </div>`
      : ''

    const html = `<html><head><title>Prediction Report - ${escapeHtml(String(result.patientId || ''))}</title>
      <style>body{font-family:Arial,sans-serif;margin:24px;color:#222}h1{margin:0 0 12px;font-size:20px}
      .meta{margin-bottom:18px;color:#555;font-size:13px}.box{border:1px solid #d7d7d7;border-radius:8px;padding:12px;margin-bottom:12px}
      .row{margin:4px 0}table{width:100%;border-collapse:collapse;margin-top:8px}th,td{border:1px solid #ddd;padding:8px;font-size:13px;text-align:left}th{background:#f3f3f3}</style>
      </head><body>
      <h1>Post-DALK Prediction Report</h1>
      <div class="meta">Generated: ${escapeHtml(new Date().toLocaleString())}</div>
      ${estimationWarning}
      <div class="box">
        <div class="row"><strong>Patient ID:</strong> ${escapeHtml(String(result.patientId || '-'))}</div>
        <div class="row"><strong>Eye:</strong> ${escapeHtml(String(result.eye || '-'))}</div>
        <div class="row"><strong>Months After DALK:</strong> ${escapeHtml(String(result.monthsAfterDALK ?? '-'))}</div>
        <div class="row"><strong>Recommended:</strong> ${escapeHtml(String(result.recommended || '-'))}</div>
        <div class="row"><strong>Confidence:</strong> ${confidence != null ? `${confidence.toFixed(1)}%` : '-'}</div>
      </div>
      <div class="box"><strong>Class Probabilities</strong>
        <table><thead><tr><th>Class</th><th>Probability</th></tr></thead>
        <tbody>${probRows || '<tr><td colspan="2">N/A</td></tr>'}</tbody></table>
      </div>
      <div class="box"><strong>Extracted / Calculated Values</strong>
        <p style="font-size:12px;color:#8a6800;background:#fffbe6;border:1px solid #f0c93a;border-radius:4px;padding:6px 10px;margin:8px 0 4px">
          ⚠ Values read automatically via OCR — verify before use.
        </p>
        <table><thead><tr><th>Parameter</th><th>Value</th></tr></thead>
        <tbody>${extractedRows || '<tr><td colspan="2">No extracted values</td></tr>'}</tbody></table>
      </div>
      <div class="box"><strong>Clinical Explanation</strong>
        <div class="row">${escapeHtml(String(result.explanation || '-'))}</div>
      </div>
      <script>window.print();</script></body></html>`

    win.document.open()
    win.document.write(html)
    win.document.close()
  }

  return (
    <section className="result-panel">

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
              🔍 OCR extracted
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
              ⚠ {estimatedCount} estimated value{estimatedCount > 1 ? 's' : ''}
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
                return (
                  <div key={key} className="extracted-item">
                    <span className="extracted-key">{formatKey(key)}</span>
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
    </section>
  )
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;')
}

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1')
    .replace(/\b\w/g, c => c.toUpperCase()).trim()
}

export default ResultPanel
