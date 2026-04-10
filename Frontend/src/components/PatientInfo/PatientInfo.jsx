import React from 'react'
import './PatientInfo.css'

function PatientInfo({ formData, handleInputChange }) {
  return (
    <section className="patient-info-section">
      <h2 className="section-title">Patient & Visit Information</h2>
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="patientId">Patient ID</label>
          <input
            type="text"
            id="patientId"
            name="patientId"
            value={formData.patientId}
            onChange={handleInputChange}
            placeholder="Enter Patient ID"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="eye">Eye</label>
          <select
            id="eye"
            name="eye"
            value={formData.eye}
            onChange={handleInputChange}
          >
            <option value="OD">OD</option>
            <option value="OS">OS</option>
          </select>
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

