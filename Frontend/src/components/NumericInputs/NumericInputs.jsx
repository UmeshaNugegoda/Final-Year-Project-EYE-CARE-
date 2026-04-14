import React from 'react'
import './NumericInputs.css'
import { snellenToLogmar, snellenToDecimal } from '../../utils/visualAcuity'

function NumericInputs({ formData, handleInputChange, submissionMode = null }) {
  const isManual = submissionMode === 'manual'
  return (
    <section className="numeric-inputs-section">

      {/* ── Visual Acuity ─────────────────────────────────────── */}
      <div className="input-group">
        <h2 className="section-title">Visual Acuity (Snellen)</h2>
        <p className="section-note">
          Use Snellen (e.g. 6/6, 6/6-, 6/6+, 20/20), or CF / HM per the Complete Visual Acuity Scoring System. logMAR and decimal follow the reference table.
        </p>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="ucva">
              UCVA (Snellen)
              <span className="field-hint">Unaided — e.g. 6/60</span>
            </label>
            <input type="text" id="ucva" name="ucva"
              value={formData.ucva} onChange={handleInputChange}
              placeholder="6/6" required />
          </div>
          <div className="form-group">
            <label htmlFor="bcva">
              BCVA (Snellen)
              <span className="field-hint">Best corrected — e.g. 6/9</span>
            </label>
            <input type="text" id="bcva" name="bcva"
              value={formData.bcva} onChange={handleInputChange}
              placeholder="6/6" required />
          </div>
        </div>

        {/* Live logMAR preview */}
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

      {/* ── Auto-Refraction ───────────────────────────────────── */}
      <div className="input-group">
        <h2 className="section-title">Auto-Refraction</h2>
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

      {/* ── Topography & Pachymetry Values ───────────────────── */}
      <div className="input-group">
        <h2 className="section-title">
          {isManual ? 'Manual Measurement Entry' : 'Topography & Pachymetry Values'}
        </h2>
        {isManual ? (
          <div className="manual-notice">
            <span className="manual-badge">MANUAL</span>
            <p>
              OCR is skipped. Enter the values from your printed report directly.
              K2 will be calculated as K1 + CYL if not entered.
            </p>
          </div>
        ) : (
          <div className="auto-notice">
            <span className="auto-badge">AUTO</span>
            <p>
              K1/Kf, K2/Ks, Corneal Astigmatism (Cyl), and Central Corneal Thickness (CCT) are
              extracted automatically from the uploaded report images using OCR.
              K2 is used directly when extracted; if not available, it is calculated as K1 + Corneal Astigmatism (Cyl). No manual entry needed.
            </p>
          </div>
        )}
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="k1Override">
              {isManual ? 'K1 / Flat K (D)' : 'K1 Override (D)'}
              {!isManual && <span className="field-hint">Optional — only if OCR value is wrong</span>}
            </label>
            <input
              type="number"
              id="k1Override"
              name="k1Override"
              value={formData.k1Override || ''}
              onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 42.18' : 'Optional'}
              step="0.01"
            />
          </div>
          <div className="form-group">
            <label htmlFor="k2Override">
              {isManual ? 'K2 / Steep K (D)' : 'K2 Override (D)'}
              {!isManual && <span className="field-hint">Optional</span>}
            </label>
            <input
              type="number"
              id="k2Override"
              name="k2Override"
              value={formData.k2Override || ''}
              onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 44.21' : 'Optional'}
              step="0.01"
            />
          </div>
          <div className="form-group">
            <label htmlFor="cylOverride">
              {isManual ? 'Corneal Cyl / CYL (D)' : 'Cyl Override (D)'}
              {!isManual && <span className="field-hint">Optional</span>}
            </label>
            <input
              type="number"
              id="cylOverride"
              name="cylOverride"
              value={formData.cylOverride || ''}
              onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 2.03' : 'Optional'}
              step="0.01"
              min="0"
              max="10"
            />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="cornealThickness">
              {isManual ? 'Central Corneal Thickness (µm)' : 'Central Corneal Thickness Fallback (um)'}
              {!isManual && <span className="field-hint">Optional, only if OCR fails (e.g. 424 or 566)</span>}
            </label>
            <input
              type="number"
              id="cornealThickness"
              name="cornealThickness"
              value={formData.cornealThickness || ''}
              onChange={handleInputChange}
              placeholder={isManual ? 'e.g. 520' : 'Optional'}
              min="250"
              max="800"
              step="1"
            />
          </div>
        </div>
      </div>

    </section>
  )
}

export default NumericInputs