import React from 'react'
import './ModeModal.css'

function ModeModal({ qualityWarnings = {}, onModeSelect, onClose }) {
  // Collect all unique warnings across all three image types
  const allWarnings = []
  for (const type of ['topography', 'pachymetry', 'eye_measurements']) {
    for (const w of qualityWarnings[type] || []) {
      if (!allWarnings.find(x => x.code === w.code)) allWarnings.push(w)
    }
  }

  return (
    <div className="mode-modal-overlay">
      <div className="mode-modal-card" role="dialog" aria-modal="true" aria-labelledby="mode-modal-title">

        <div className="mode-modal-header">
          <span className="mode-modal-icon">⚠</span>
          <h2 id="mode-modal-title" className="mode-modal-title">Image Quality Issues Detected</h2>
          {onClose && (
            <button type="button" className="mode-modal-close" onClick={onClose} aria-label="Close">✕</button>
          )}
        </div>

        {allWarnings.length > 0 && (
          <ul className="mode-modal-warnings">
            {allWarnings.map(w => (
              <li key={w.code} className="mode-modal-warning-item">{w.message}</li>
            ))}
          </ul>
        )}

        <p className="mode-modal-prompt">
          How would you like to proceed?
        </p>

        <div className="mode-modal-options">

          <button
            type="button"
            className="mode-option mode-option--manual"
            onClick={() => onModeSelect('manual')}
          >
            <div className="mode-option-top">
              <span className="mode-option-label">Enter Values Manually</span>
              <span className="mode-recommended-badge">Recommended</span>
            </div>
            <p className="mode-option-desc">
              Skip OCR entirely. Type K1, K2, CYL, and CCT directly from the
              printed report. Most accurate — no neural network, no crash risk.
            </p>
          </button>

          <button
            type="button"
            className="mode-option mode-option--reupload"
            onClick={() => onModeSelect('reupload')}
          >
            <div className="mode-option-top">
              <span className="mode-option-label">Re-upload a Better Image</span>
            </div>
            <p className="mode-option-desc">
              Go back and upload a cleaner scan or digital export. OCR works
              best on flat, well-lit, directly-above photographs.
            </p>
          </button>

          <button
            type="button"
            className="mode-option mode-option--estimate"
            onClick={() => onModeSelect('ocr')}
          >
            <div className="mode-option-top">
              <span className="mode-option-label">Try OCR Anyway</span>
              <span className="mode-caution-badge">Not for clinical decisions</span>
            </div>
            <p className="mode-option-desc">
              Run standard OCR on the image. Values that can't be read will be
              filled using population averages. The result will display a disclaimer.
            </p>
          </button>

        </div>
      </div>
    </div>
  )
}

export default ModeModal
