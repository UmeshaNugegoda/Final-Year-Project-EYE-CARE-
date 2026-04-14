import React from 'react'
import './ResultPanel.css'

// Maps extractedValues display keys → extractionStatus field names
const KEY_TO_STATUS_FIELD = {
  K1_diopters          : 'K1_diopters',
  K2_diopters          : 'K2_diopters',
  astigmatism_diopters : 'astigmatism_diopters',
  corneal_thickness_um : 'corneal_thickness_um',
}

const CLASS_COLORS = {
  'Spectacles'    : { bg:'#EAF3DE', accent:'#3B6D11', badge:'#639922' },
  'Contact Lenses': { bg:'#E1F5EE', accent:'#085041', badge:'#1D9E75' },
  'No Correction' : { bg:'#E6F1FB', accent:'#0C447C', badge:'#378ADD' },
}
const DEFAULT_COLOR = { bg:'#F1EFE8', accent:'#444441', badge:'#888780' }

function ResultPanel({ result }) {
  if (!result) return null

  const isHighConf = typeof result.confidence === 'number' && result.confidence >= 80
  const colors     = CLASS_COLORS[result.recommended] || DEFAULT_COLOR
  const probEntries = result.probabilities
    ? Object.entries(result.probabilities).sort((a,b) => b[1]-a[1])
    : []

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
            const fieldKey = KEY_TO_STATUS_FIELD[key] || key
            return `<tr><td>${escapeHtml(formatKey(key))}</td><td>${escapeHtml(String(val ?? '-'))}${escapeHtml(statusLabel(fieldKey))}</td></tr>`
          })
          .join('')
      : ''

    const probRows = probEntries
      .map(([label, prob]) => `<tr><td>${escapeHtml(label)}</td><td>${Number(prob).toFixed(1)}%</td></tr>`)
      .join('')

    const html = `
      <html>
        <head>
          <title>Prediction Report - ${escapeHtml(String(result.patientId || ''))}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #222; }
            h1 { margin: 0 0 12px; font-size: 22px; }
            .meta { margin-bottom: 18px; color: #555; font-size: 13px; }
            .box { border: 1px solid #d7d7d7; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
            .row { margin: 4px 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 8px; }
            th, td { border: 1px solid #ddd; padding: 8px; font-size: 13px; text-align: left; }
            th { background: #f3f3f3; }
          </style>
        </head>
        <body>
          <h1>Post-DALK Prediction Report</h1>
          <div class="meta">Generated: ${escapeHtml(new Date().toLocaleString())}</div>
          <div class="box">
            <div class="row"><strong>Patient ID:</strong> ${escapeHtml(String(result.patientId || '-'))}</div>
            <div class="row"><strong>Eye:</strong> ${escapeHtml(String(result.eye || '-'))}</div>
            <div class="row"><strong>Months After DALK:</strong> ${escapeHtml(String(result.monthsAfterDALK ?? '-'))}</div>
            <div class="row"><strong>Recommended:</strong> ${escapeHtml(String(result.recommended || '-'))}</div>
            <div class="row"><strong>Confidence:</strong> ${typeof result.confidence === 'number' ? `${result.confidence.toFixed(1)}%` : escapeHtml(String(result.confidence || '-'))}</div>
          </div>
          <div class="box">
            <strong>Class Probabilities</strong>
            <table>
              <thead><tr><th>Class</th><th>Probability</th></tr></thead>
              <tbody>${probRows || '<tr><td colspan="2">No probabilities available</td></tr>'}</tbody>
            </table>
          </div>
          <div class="box">
            <strong>Extracted/Calculated Values</strong>
            <p style="font-size:12px;color:#8a6800;background:#fffbe6;border:1px solid #f0c93a;border-radius:6px;padding:8px 12px;margin:10px 0 6px;">
              ⚠ These values were read automatically from the uploaded images using OCR. Accuracy depends on image quality. Always verify against the original report before accepting the prediction.
            </p>
            <table>
              <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
              <tbody>${extractedRows || '<tr><td colspan="2">No extracted values</td></tr>'}</tbody>
            </table>
          </div>
          <div class="box">
            <strong>Clinical Explanation</strong>
            <div class="row">${escapeHtml(String(result.explanation || '-'))}</div>
          </div>
          <script>window.print();</script>
        </body>
      </html>
    `

    win.document.open()
    win.document.write(html)
    win.document.close()
  }

  return (
    <section className="result-panel" style={{ '--rb':colors.bg, '--ra':colors.accent }}>
      <h2 className="section-title">Prediction Result</h2>

      <div className="result-content">

        {/* Main recommendation */}
        <div className="result-main">
          <div className="result-item">
            <span className="result-label">Recommended</span>
            <span className="result-badge" style={{ background: colors.badge }}>
              {result.recommended}
            </span>
          </div>
          <div className="result-item">
            <span className="result-label">Confidence</span>
            <span className={`result-confidence ${isHighConf ? 'high' : 'low'}`}>
              {typeof result.confidence === 'number'
                ? `${result.confidence.toFixed(1)}%`
                : result.confidence}
            </span>
          </div>
          <div className="result-actions">
            <button type="button" className="result-pdf-btn" onClick={handleDownloadPdf}>
              Save as PDF
            </button>
            {result.historySaved && (
              <span className="result-saved-note">Saved to patient history</span>
            )}
          </div>
        </div>

        {/* Probability bars */}
        {probEntries.length > 0 && (
          <div className="prob-section">
            <p className="prob-title">Class probabilities</p>
            {probEntries.map(([label, prob]) => {
              const c = CLASS_COLORS[label] || DEFAULT_COLOR
              return (
                <div key={label} className="prob-row">
                  <span className="prob-label">{label}</span>
                  <div className="prob-track">
                    <div className="prob-fill"
                      style={{ width:`${prob}%`, background: c.badge }} />
                  </div>
                  <span className="prob-value">{prob.toFixed(1)}%</span>
                </div>
              )
            })}
          </div>
        )}

        {/* OCR extracted values */}
        {result.extractedValues && (
          <div className="extracted-section">
            <p className="extracted-title">Values extracted from report images</p>

            {/* OCR accuracy notice */}
            <div className="ocr-notice">
              <span className="ocr-notice-icon">🔍</span>
              <span>
                These values were read automatically from the uploaded images using OCR.
                Accuracy depends on image quality — blurry, photographed, or damaged reports
                may produce incorrect readings. <strong>Always verify extracted values against
                the original report before accepting the prediction.</strong>
              </span>
            </div>

            <div className="extracted-grid">
              {Object.entries(result.extractedValues).map(([key, val]) => {
                const fieldKey = KEY_TO_STATUS_FIELD[key]
                const status   = fieldKey ? (result.extractionStatus?.[fieldKey] || 'not_found') : null
                return (
                  <div key={key} className="extracted-item">
                    <span className="extracted-key">{formatKey(key)}</span>
                    <span className="extracted-val">{val ?? '—'}</span>
                    {status === 'extracted'       && <span className="status-extracted">Extracted</span>}
                    {status === 'manual_override' && <span className="status-override">Manual override</span>}
                    {status === 'not_found'       && <span className="status-estimated">Estimated</span>}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Explanation */}
        {result.explanation && (
          <div className="result-explanation">
            <p>{result.explanation}</p>
          </div>
        )}

        {/* Low confidence warning */}
        {!isHighConf && (
          <div className="conf-warning">
            ⚠ Confidence below 80% — please review clinical findings before proceeding.
          </div>
        )}

      </div>
    </section>
  )
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function formatKey(key) {
  return key.replace(/_/g,' ').replace(/([A-Z])/g,' $1')
    .replace(/\b\w/g, c => c.toUpperCase()).trim()
}

export default ResultPanel