import React from 'react'
import './NumericInputs.css'
import { snellenToLogmar, snellenToDecimal } from '../../utils/visualAcuity'

function NumericInputs({ formData, handleInputChange, submissionMode = null, showAsOcrFallback = false }) {
  const isManual = submissionMode === 'manual'

  return (
    <section className="form-card measure-card">
      <div className="form-card-header">
        <h2 className="form-card-title">
          {isManual ? 'Manual Measurement Entry' : 'Measurements'}
        </h2>
        <p className="form-card-subtitle">
          {isManual
            ? 'Enter all values directly from the printed report'
            : 'Visual acuity and refraction — K1/K2/CYL/CCT extracted from images automatically'}
        </p>
      </div>

      {showAsOcrFallback && (
        <div className="ocr-fallback-warning">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          Eye measurement image quality issues detected — OCR extraction may be inaccurate. Enter values manually as a fallback.
        </div>
      )}

      {/* ── Visual Acuity ── */}
      <div className="input-group">
        <h3 className="input-group-title">Visual Acuity (Snellen)</h3>
        <p className="section-note">
          Use Snellen (e.g. 6/6, 6/60, 20/20), or CF / HM. logMAR preview shown live.
        </p>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="ucva">
              UCVA
              <span className="field-hint">Unaided — e.g. 6/60</span>
            </label>
            <input type="text" id="ucva" name="ucva"
              value={formData.ucva} onChange={handleInputChange}
              placeholder="6/6" required />
          </div>
          <div className="form-group">
            <label htmlFor="bcva">
              BCVA
              <span className="field-hint">Best corrected — e.g. 6/9</span>
            </label>
            <input type="text" id="bcva" name="bcva"
              value={formData.bcva} onChange={handleInputChange}
              placeholder="6/6" required />
          </div>
        </div>

        {(formData.ucva !== '' || formData.bcva !== '') && (
          <div className="snellen-preview">
            {formData.ucva !== '' && (
              <span>
                UCVA: logMAR ≈ <strong>{snellenToLogmar(formData.ucva) ?? '—'}</strong>
                {snellenToDecimal(formData.ucva) != null && (
                  <> · decimal ≈ <strong>{snellenToDecimal(formData.ucva)}</strong></>
                )}
              </span>
            )}
            {formData.bcva !== '' && (
              <span>
                BCVA: logMAR ≈ <strong>{snellenToLogmar(formData.bcva) ?? '—'}</strong>
                {snellenToDecimal(formData.bcva) != null && (
                  <> · decimal ≈ <strong>{snellenToDecimal(formData.bcva)}</strong></>
                )}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Auto-Refraction ── */}
      <div className="input-group">
        <h3 className="input-group-title">Auto-Refraction</h3>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="sphere">Sphere (D)</label>
            <input type="number" id="sphere" name="sphere"
              value={formData.sphere} onChange={handleInputChange}
              placeholder="0.00" step="0.25" required />
          </div>
          <div className="form-group">
            <label htmlFor="cylinder">Cylinder (D)</label>
            <input type="number" id="cylinder" name="cylinder"
              value={formData.cylinder} onChange={handleInputChange}
              placeholder="0.00" step="0.25" required />
          </div>
          <div className="form-group">
            <label htmlFor="axis">Axis (°)</label>
            <input type="number" id="axis" name="axis"
              value={formData.axis} onChange={handleInputChange}
              placeholder="0" min="0" max="180" required />
          </div>
        </div>
      </div>

      {/* ── Topography & Pachymetry overrides ── */}
      <div className="input-group">
        <h3 className="input-group-title">
          {isManual ? 'Corneal Measurements' : 'Topography & Pachymetry Values'}
        </h3>
        {isManual ? (
          <div className="manual-notice">
            <span className="manual-badge">MANUAL</span>
            <p>
              OCR is skipped. Enter values from your printed report.
              K2 is calculated as K1 + |CYL| if not entered.
            </p>
          </div>
        ) : (
          <div className="auto-notice">
            <span className="auto-badge">AUTO</span>
            <p>
              K1/Kf, K2/Ks, Corneal Cyl, and CCT are extracted from uploaded images.
              Use these fields only to correct an incorrect OCR value.
            </p>
          </div>
        )}

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="k1Override">
              {isManual ? 'K1 / Flat K (D)' : 'K1 Override (D)'}
              {!isManual && <span className="field-hint">Override if OCR is wrong</span>}
            </label>
            <input type="number" id="k1Override" name="k1Override"
              value={formData.k1Override || ''} onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 42.18' : 'Optional'} step="0.01" />
          </div>
          <div className="form-group">
            <label htmlFor="k2Override">
              {isManual ? 'K2 / Steep K (D)' : 'K2 Override (D)'}
              {!isManual && <span className="field-hint">Optional</span>}
            </label>
            <input type="number" id="k2Override" name="k2Override"
              value={formData.k2Override || ''} onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 44.21' : 'Optional'} step="0.01" />
          </div>
          <div className="form-group">
            <label htmlFor="cylOverride">
              {isManual ? 'Corneal Cyl (D)' : 'Cyl Override (D)'}
              {!isManual && <span className="field-hint">Optional</span>}
            </label>
            <input type="number" id="cylOverride" name="cylOverride"
              value={formData.cylOverride || ''} onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 2.03' : 'Optional'}
              step="0.01" min="0" max="10" />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="cornealThickness">
              {isManual ? 'CCT (µm)' : 'CCT Fallback (µm)'}
              {!isManual && <span className="field-hint">Optional, only if OCR fails</span>}
            </label>
            <input type="number" id="cornealThickness" name="cornealThickness"
              value={formData.cornealThickness || ''} onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 520' : 'Optional'} min="250" max="800" step="1" />
          </div>
        </div>
      </div>
    </section>
  )
}

export default NumericInputs
