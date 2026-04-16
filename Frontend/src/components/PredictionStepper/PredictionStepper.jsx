import React from 'react'
import './PredictionStepper.css'

const STEPS = [
  { id: 1, label: 'Patient Details', subtitle: 'ID · Eye · Post-DALK months' },
  { id: 2, label: 'Scan Reports',    subtitle: 'Topography · Pachymetry · Eye Meas.' },
  { id: 3, label: 'Measurements',    subtitle: 'Visual acuity · Refraction' },
]

function PredictionStepper({ activeStep = 1 }) {
  return (
    <div className="stepper">
      {STEPS.map((step, i) => {
        const isDone   = step.id < activeStep
        const isActive = step.id === activeStep
        return (
          <React.Fragment key={step.id}>
            <div className={`stepper-step${isActive ? ' active' : ''}${isDone ? ' done' : ''}`}>
              <div className="stepper-circle">
                {isDone ? '✓' : step.id}
              </div>
              <div className="stepper-text">
                <span className="stepper-label">{step.label}</span>
                <span className="stepper-sub">{step.subtitle}</span>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`stepper-line${isDone ? ' done' : ''}`} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

export default PredictionStepper
