import React, { useState } from 'react'
import Header             from '../../components/Header/Header'
import Sidebar            from '../../components/Sidebar/Sidebar'
import PredictionStepper  from '../../components/PredictionStepper/PredictionStepper'
import PatientInfo        from '../../components/PatientInfo/PatientInfo'
import ImageUpload        from '../../components/ImageUpload/ImageUpload'
import NumericInputs      from '../../components/NumericInputs/NumericInputs'
import PredictButton      from '../../components/PredictButton/PredictButton'
import ResultPanel        from '../../components/ResultPanel/ResultPanel'
import ModeModal          from '../../components/ModeModal/ModeModal'
import './Prediction.css'
import { snellenToLogmar } from '../../utils/visualAcuity'

const EMPTY_IMAGES    = { topography: null, pachymetry: null, eye_measurements: null }
const EMPTY_WARNINGS  = { topography: [],   pachymetry: [],   eye_measurements: [] }
const EMPTY_CHECKING  = { topography: false, pachymetry: false, eye_measurements: false }

function Prediction({ auth, onLogout }) {
  const [formData, setFormData] = useState({
    patientId: '', eye: 'OD', monthsAfterDALK: '',
    ucva: '', bcva: '', sphere: '', cylinder: '', axis: '',
    cornealThickness: '', k1Override: '', k2Override: '', cylOverride: '',
  })
  const [images,          setImages]          = useState({ ...EMPTY_IMAGES })
  const [result,          setResult]          = useState(null)
  const [isSubmitting,    setIsSubmitting]    = useState(false)
  const [error,           setError]           = useState(null)
  const [qualityWarnings, setQualityWarnings] = useState({ ...EMPTY_WARNINGS })
  const [qualityChecking, setQualityChecking] = useState({ ...EMPTY_CHECKING })
  const [submissionMode,  setSubmissionMode]  = useState(null) // null | 'ocr' | 'manual'
  const [showModeModal,   setShowModeModal]   = useState(false)

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleImageUpload = async (type, e) => {
    const file = e.target.files[0]
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/jpg'].includes(file.type)) {
      alert('Please upload JPG or PNG only'); e.target.value = ''; return
    }
    setImages(prev => ({ ...prev, [type]: { file, preview: URL.createObjectURL(file) } }))
    setQualityWarnings(prev => ({ ...prev, [type]: [] }))
    setSubmissionMode(null)
    setShowModeModal(false)
    setQualityChecking(prev => ({ ...prev, [type]: true }))
    try {
      const qForm = new FormData()
      // quality endpoint only accepts topography/pachymetry — skip for eye_measurements
      if (type !== 'eye_measurements') {
        qForm.append(type, file)
        const res = await fetch('/api/analyze-quality', { method: 'POST', body: qForm })
        if (res.ok) {
          const data = await res.json()
          const warnings = data.warnings?.[type] || []
          setQualityWarnings(prev => {
            const next = { ...prev, [type]: warnings }
            if (Object.values(next).some(w => w.length > 0)) setShowModeModal(true)
            return next
          })
        }
      }
    } catch {
      // non-fatal
    } finally {
      setQualityChecking(prev => ({ ...prev, [type]: false }))
    }
  }

  const removeImage = (type) => {
    if (images[type]?.preview) URL.revokeObjectURL(images[type].preview)
    setImages(prev => ({ ...prev, [type]: null }))
    setQualityWarnings(prev => ({ ...prev, [type]: [] }))
    setQualityChecking(prev => ({ ...prev, [type]: false }))
    setSubmissionMode(null)
    setShowModeModal(false)
  }

  const handleModeSelect = (mode) => {
    if (mode === 'reupload') {
      setShowModeModal(false)
      setSubmissionMode(null)
      setQualityWarnings({ ...EMPTY_WARNINGS })
      Object.values(images).forEach(img => { if (img?.preview) URL.revokeObjectURL(img.preview) })
      setImages({ ...EMPTY_IMAGES })
    } else {
      setSubmissionMode(mode)
      setShowModeModal(false)
    }
  }

  const ucvaLogmar = snellenToLogmar(formData.ucva)
  const bcvaLogmar = snellenToLogmar(formData.bcva)

  const isFormValid = () =>
    formData.patientId.trim() && formData.monthsAfterDALK &&
    formData.ucva && formData.bcva &&
    ucvaLogmar !== null && bcvaLogmar !== null &&
    formData.sphere && formData.cylinder && formData.axis

  // Determine which step is active for the stepper (visual only)
  const activeStep =
    formData.patientId && formData.monthsAfterDALK ? 2 : 1

  const handlePredict = async () => {
    if (!isFormValid() || isSubmitting) return
    setIsSubmitting(true); setResult(null); setError(null)
    try {
      const payload = new FormData()
      payload.append('patientId',        formData.patientId)
      payload.append('eye',              formData.eye)
      payload.append('monthsAfterDALK',  Number(formData.monthsAfterDALK))
      payload.append('ucva_logmar',      ucvaLogmar)
      payload.append('bcva_logmar',      bcvaLogmar)
      payload.append('sphere_diopters',   Number(formData.sphere))
      payload.append('cylinder_diopters', Number(formData.cylinder))
      payload.append('axis_degrees',      Number(formData.axis))
      if (formData.cornealThickness !== '') payload.append('corneal_thickness_override', Number(formData.cornealThickness))
      if (formData.k1Override  !== '')      payload.append('k1_override',  Number(formData.k1Override))
      if (formData.k2Override  !== '')      payload.append('k2_override',  Number(formData.k2Override))
      if (formData.cylOverride !== '')      payload.append('cyl_override', Number(formData.cylOverride))

      const effectiveMode = submissionMode || 'ocr'
      payload.append('mode', effectiveMode)

      if (effectiveMode !== 'manual') {
        if (images.topography?.file)      payload.append('topography',      images.topography.file)
        if (images.pachymetry?.file)      payload.append('pachymetry',      images.pachymetry.file)
        if (images.eye_measurements?.file) payload.append('eye_measurements', images.eye_measurements.file)
      }

      const response = await fetch('/api/predictions', { method: 'POST', body: payload })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.message || 'Prediction failed')
      }
      const data = await response.json()
      setResult(data)
      setTimeout(() => {
        document.querySelector('.result-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar auth={auth} />
      <div className="app-main">
        <Header auth={auth} onLogout={onLogout} title="Prediction" />
        <main className="page-content prediction-content">

          <PredictionStepper activeStep={activeStep} />

          <div className="prediction-form">
            <PatientInfo formData={formData} handleInputChange={handleInputChange} />

            <ImageUpload
              images={images}
              handleImageUpload={handleImageUpload}
              removeImage={removeImage}
              qualityWarnings={qualityWarnings}
              qualityChecking={qualityChecking}
              submissionMode={submissionMode}
            />

            <NumericInputs
              formData={formData}
              handleInputChange={handleInputChange}
              submissionMode={submissionMode}
            />

            <PredictButton
              isDisabled={!isFormValid() || isSubmitting}
              onClick={handlePredict}
            />

            {isSubmitting && (
              <div className="loading-state">
                <div className="loading-spinner" />
                <p>Analysing report images and predicting…</p>
              </div>
            )}
            {error && <div className="error-message">⚠ {error}</div>}

            <ResultPanel result={result} />
          </div>

        </main>
      </div>

      {showModeModal && (
        <ModeModal
          qualityWarnings={qualityWarnings}
          onModeSelect={handleModeSelect}
        />
      )}
    </div>
  )
}

export default Prediction
