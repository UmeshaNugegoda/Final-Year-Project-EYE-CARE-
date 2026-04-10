import React from 'react'
import './ImageUpload.css'

function ImageUpload({ images, handleImageUpload, removeImage }) {
  return (
    <section className="image-upload-section">
      <h2 className="section-title">Report Images</h2>
      <p className="section-note">
        K1/Kf, K2/Ks, Corneal Astigmatism (Cyl), and Central Corneal Thickness are extracted automatically
        from these images. You do not need to enter them manually.
      </p>

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
              <p className="upload-format">JPG or PNG</p>
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
              <p className="upload-format">JPG or PNG</p>
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
            </div>
          )}
        </div>

      </div>
    </section>
  )
}

export default ImageUpload