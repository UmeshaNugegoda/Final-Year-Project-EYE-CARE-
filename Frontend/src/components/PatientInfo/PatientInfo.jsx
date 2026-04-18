import React from 'react'
import './PatientInfo.css'

function PatientInfo({ formData, handleInputChange, handleBlur = () => {}, fieldErrors = {} }) {
  const handleEyeSelect = (eye) => {
    handleInputChange({ target: { name: 'eye', value: eye } })
  }

  return (
    <section className="form-card patient-card">
      <div className="form-card-header">
        <h2 className="form-card-title">Patient Details</h2>
        <p className="form-card-subtitle">Patient ID, eye under assessment, and time since surgery</p>
      </div>
      <div className="form-row-3">
        <div className="form-group">
          <label htmlFor="patientId">Patient ID</label>
          <input
            type="text"
            id="patientId"
            name="patientId"
            value={formData.patientId}
            onChange={handleInputChange}
            onBlur={handleBlur}
            placeholder="e.g. PT-001"
            className={fieldErrors.patientId ? 'input-error' : ''}
            required
          />
          {fieldErrors.patientId && <span className="field-error-msg">{fieldErrors.patientId}</span>}
        </div>

        <div className="form-group">
          <label>Eye</label>
          <div className="eye-segmented">
            <button
              type="button"
              className={`eye-seg-btn${formData.eye === 'OD' ? ' active' : ''}`}
              onClick={() => handleEyeSelect('OD')}
            >
              OD <span className="eye-seg-sub">Right</span>
            </button>
            <button
              type="button"
              className={`eye-seg-btn${formData.eye === 'OS' ? ' active' : ''}`}
              onClick={() => handleEyeSelect('OS')}
            >
              OS <span className="eye-seg-sub">Left</span>
            </button>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="monthsAfterDALK">Months after DALK</label>
          <input
            type="number"
            id="monthsAfterDALK"
            name="monthsAfterDALK"
            value={formData.monthsAfterDALK}
            onChange={handleInputChange}
            onBlur={handleBlur}
            placeholder="0"
            min="0"
            max="120"
            step="1"
            className={fieldErrors.monthsAfterDALK ? 'input-error' : ''}
            required
          />
          {fieldErrors.monthsAfterDALK && <span className="field-error-msg">{fieldErrors.monthsAfterDALK}</span>}
        </div>
      </div>
    </section>
  )
}

export default PatientInfo
