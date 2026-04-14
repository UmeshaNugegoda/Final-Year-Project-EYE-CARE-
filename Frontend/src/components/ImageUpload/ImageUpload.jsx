import React, { useState } from 'react'
import './ImageUpload.css'

const QUALITY_TIPS = [
  { icon: '✅', text: 'Digital export or screenshot directly from the device software gives the best results.' },
  { icon: '✅', text: 'If photographing a printout, ensure the page is flat, well-lit, and the camera is directly above it.' },
  { icon: '✅', text: 'Higher resolution helps — try to capture the full report page without cropping edge values.' },
  { icon: '⚠️', text: 'Blurry or low-contrast photos reduce accuracy. If OCR extraction looks wrong, enter the value manually in the fallback field below.' },
  { icon: '⚠️', text: 'Photos taken at an angle may cause columns to be misread. Keep the camera parallel to the printout.' },
  { icon: '⚠️', text: 'Torn, folded, or punched pages can obscure values — check extracted results carefully.' },
  { icon: 'ℹ️', text: 'Handwritten reports are not currently supported. Enter those values manually in the fields below.' },
]

function ImageUpload({ images, handleImageUpload, removeImage, qualityWarnings = {}, qualityChecking = {} }) {
  const [tipsOpen, setTipsOpen] = useState(false)

  return (
    <section className="image-upload-section">
      <h2 className="section-title">Report Images</h2>
      <p className="section-note">
        K1/Kf, K2/Ks, Corneal Astigmatism (Cyl), and Central Corneal Thickness are extracted automatically
        from these images using OCR. You do not need to enter them manually.
      </p>

      {/* ── Image quality guidance ──────────────────────────── */}
      <div className="img-guidance-banner">
        <button
          type="button"
          className="img-guidance-toggle"
          onClick={() => setTipsOpen(o => !o)}
          aria-expanded={tipsOpen}
        >
          <span className="img-guidance-icon">📷</span>
          <span className="img-guidance-label">Image quality tips for accurate extraction</span>
          <span className={`img-guidance-chevron ${tipsOpen ? 'open' : ''}`}>▾</span>
        </button>

        {tipsOpen && (
          <ul className="img-guidance-list">
            {QUALITY_TIPS.map((tip, i) => (
              <li key={i} className="img-guidance-item">
                <span className="img-guidance-bullet">{tip.icon}</span>
                <span>{tip.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="image-upload-grid">

        {/* ── Topography ─────────────────────────────────────── */}
        <div className="upload-card">
          <div className="upload-card-header">
            <span className="upload-title">Topography Report</span>
            <span className="upload-badge">Extracts K1/Kf · Corneal Astigmatism (Cyl) · K2/Ks</span>
          </div>

          {!images.topography ? (
            <label className="upload-area" htmlFor="topography-input">
              <div className="upload-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <p className="upload-hint">Click to upload topography image</p>
              <p className="upload-format">JPG or PNG · digital export preferred</p>
              <input
                type="file" id="topography-input" accept="image/*"
                onChange={(e) => handleImageUpload('topography', e)}
                style={{ display:'none' }}
              />
            </label>
          ) : (
            <div className="upload-preview">
              <img
                src={images.topography.preview}
                alt="Topography report"
                className="preview-image"
              />
              <div className="preview-overlay">
                <span className="preview-filename">
                  {images.topography.file.name}
                </span>
                <button
                  className="remove-btn"
                  onClick={() => removeImage('topography')}
                  type="button"
                >
                  Remove
                </button>
              </div>
              {qualityChecking.topography && (
                <div className="quality-checking">
                  <span className="quality-spinner" /> Checking image quality…
                </div>
              )}
              {qualityWarnings.topography?.length > 0 && (
                <div className="quality-warnings">
                  {qualityWarnings.topography.map(w => (
                    <div key={w.code} className="quality-warning-item">⚠ {w.message}</div>
                  ))}
                  <p className="quality-warning-note">Warnings do not block submission. Verify extracted results.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Pachymetry ─────────────────────────────────────── */}
        <div className="upload-card">
          <div className="upload-card-header">
            <span className="upload-title">Pachymetry Report</span>
            <span className="upload-badge">Extracts Central Corneal Thickness (CCT)</span>
          </div>

          {!images.pachymetry ? (
            <label className="upload-area" htmlFor="pachymetry-input">
              <div className="upload-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <p className="upload-hint">Click to upload pachymetry image</p>
              <p className="upload-format">JPG or PNG · digital export preferred</p>
              <input
                type="file" id="pachymetry-input" accept="image/*"
                onChange={(e) => handleImageUpload('pachymetry', e)}
                style={{ display:'none' }}
              />
            </label>
          ) : (
            <div className="upload-preview">
              <img
                src={images.pachymetry.preview}
                alt="Pachymetry report"
                className="preview-image"
              />
              <div className="preview-overlay">
                <span className="preview-filename">
                  {images.pachymetry.file.name}
                </span>
                <button
                  className="remove-btn"
                  onClick={() => removeImage('pachymetry')}
                  type="button"
                >
                  Remove
                </button>
              </div>
              {qualityChecking.pachymetry && (
                <div className="quality-checking">
                  <span className="quality-spinner" /> Checking image quality…
                </div>
              )}
              {qualityWarnings.pachymetry?.length > 0 && (
                <div className="quality-warnings">
                  {qualityWarnings.pachymetry.map(w => (
                    <div key={w.code} className="quality-warning-item">⚠ {w.message}</div>
                  ))}
                  <p className="quality-warning-note">Warnings do not block submission. Verify extracted results.</p>
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </section>
  )
}

export default ImageUpload