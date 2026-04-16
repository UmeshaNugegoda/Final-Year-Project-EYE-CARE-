import React from 'react'
import './PatientInfo.css'

function PatientInfo({ formData, handleInputChange }) {
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
            placeholder="e.g. PT-001"
            required
          />
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
            placeholder="0"
            min="0"
            required
          />
        </div>
      </div>
    </section>
  )
}

export default PatientInfo
