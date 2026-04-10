import React from 'react'
import './PredictButton.css'

function PredictButton({ isDisabled, onClick }) {
  return (
    <section className="predict-section">
      <button
        className={`predict-button ${isDisabled ? 'disabled' : ''}`}
        onClick={onClick}
        disabled={isDisabled}
        aria-label="Predict Visual Correction"
      >
        Predict Visual Correction
      </button>
    </section>
  )
}

export default PredictButton

