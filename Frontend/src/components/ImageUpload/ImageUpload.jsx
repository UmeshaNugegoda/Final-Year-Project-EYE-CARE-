import React, { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import './ImageUpload.css'

const WARNING_DETAIL = {
  blurry          : 'Image appears blurry. OCR accuracy will be reduced — use a digital export if possible.',
  low_resolution  : 'Image resolution is below 800 px on one side. Higher resolution improves extraction.',
  hole_punch      : 'Hole-punch marks detected. These can obscure values near page edges.',
  angled          : 'Page appears to be photographed at an angle. Keep the camera directly above the report.',
  edge_clipping   : 'Dark borders suggest the image is clipped. Ensure the full report is visible.',
}

const WARNING_LABELS = {
  blurry         : 'Blurry',
  low_resolution : 'Low resolution',
  hole_punch     : 'Hole punches',
  angled         : 'Angled',
  edge_clipping  : 'Edge clipping',
}

const SCANNERS = [
  {
    key     : 'topography',
    title   : 'Topography Report',
    badge   : 'Extracts K1 · K2 · Corneal Cyl',
    hint    : 'Click to upload topography image',
  },
  {
    key     : 'pachymetry',
    title   : 'Pachymetry Report',
    badge   : 'Extracts CCT',
    hint    : 'Click to upload pachymetry image',
  },
  {
    key     : 'eye_measurements',
    title   : 'Eye Measurements Report',
    badge   : 'Extracts SPH · CYL · AXIS · UCVA · BCVA',
    hint    : 'Click to upload refraction report',
  },
]

function WarningChips({ warnings }) {
  const [openCode, setOpenCode] = useState(null)
  if (!warnings || warnings.length === 0) return null
  return (
    <div className="warning-chips">
      {warnings.map(w => (
        <div key={w.code} className="warning-chip-wrap">
          <button
            type="button"
            className="warning-chip"
            onClick={() => setOpenCode(openCode === w.code ? null : w.code)}
            aria-expanded={openCode === w.code}
          >
            <AlertTriangle size={12} /> {WARNING_LABELS[w.code] || w.code}
          </button>
          {openCode === w.code && (
            <div className="warning-chip-popover">
              {WARNING_DETAIL[w.code] || w.message}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function UploadCard({ scanner, image, onUpload, onRemove, warnings, checking }) {
  return (
    <div className="upload-card">
      <div className="upload-card-header">
        <span className="upload-title">{scanner.title}</span>
        <span className="upload-badge">{scanner.badge}</span>
      </div>

      {!image ? (
        <label className="upload-area" htmlFor={`${scanner.key}-input`}>
          <div className="upload-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <p className="upload-hint">{scanner.hint}</p>
          <p className="upload-format">JPG or PNG</p>
          <input
            type="file" id={`${scanner.key}-input`} accept="image/*"
            onChange={(e) => onUpload(scanner.key, e)}
            style={{ display: 'none' }}
          />
        </label>
      ) : (
        <div className="upload-preview">
          <img src={image.preview} alt={`${scanner.title} preview`} className="preview-image" />
          <div className="preview-overlay">
            <span className="preview-filename">{image.file.name}</span>
            <button className="remove-btn" onClick={() => onRemove(scanner.key)} type="button">
              Remove
            </button>
          </div>
          {checking && (
            <div className="quality-checking">
              <span className="quality-spinner" /> Checking quality…
            </div>
          )}
          <WarningChips warnings={warnings} />
        </div>
      )}
    </div>
  )
}

function ImageUpload({
  images,
  handleImageUpload,
  removeImage,
  qualityWarnings = {},
  qualityChecking = {},
  submissionMode  = null,
}) {
  return (
    <section className="form-card scanner-card">
      <div className="form-card-header">
        <h2 className="form-card-title">Scan Reports</h2>
        <p className="form-card-subtitle">
          {submissionMode === 'manual'
            ? 'Manual entry selected — image upload skipped'
            : 'Upload report images for automatic OCR extraction'}
        </p>
      </div>

      {submissionMode === 'manual' ? (
        <div className="manual-skip-note">
          Images will not be processed. Enter values directly in the Measurements section below.
        </div>
      ) : (
        <div className={`upload-grid${submissionMode === 'manual' ? ' upload-grid-hidden' : ''}`}>
          {SCANNERS.map(s => (
            <UploadCard
              key={s.key}
              scanner={s}
              image={images[s.key]}
              onUpload={handleImageUpload}
              onRemove={removeImage}
              warnings={qualityWarnings[s.key]}
              checking={qualityChecking[s.key]}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default ImageUpload
