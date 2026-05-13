import React, { useState, useEffect } from 'react'
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

const EMPTY_IMAGES   = { topography: null, pachymetry: null, eye_measurements: null }
const EMPTY_WARNINGS = { topography: [],   pachymetry: [],   eye_measurements: [] }
const EMPTY_CHECKING = { topography: false, pachymetry: false, eye_measurements: false }

function Prediction({ auth, onLogout }) {
  const [formData, setFormData] = useState({
    patientId: '', eye: 'OD', monthsAfterDALK: '',
    ucva: '', bcva: '', sphere: '', cylinder: '', axis: '',
    cornealThickness: '', k1Override: '', k2Override: '', cylOverride: '',
  })
  const [images,           setImages]           = useState({ ...EMPTY_IMAGES })
  const [result,           setResult]           = useState(null)
  const [isSubmitting,     setIsSubmitting]     = useState(false)
  const [error,            setError]            = useState(null)
  const [qualityWarnings,  setQualityWarnings]  = useState({ ...EMPTY_WARNINGS })
  const [qualityChecking,  setQualityChecking]  = useState({ ...EMPTY_CHECKING })
  const [submissionMode,   setSubmissionMode]   = useState(null)
  const [showModeModal,    setShowModeModal]    = useState(false)
  const [modalTriggerType, setModalTriggerType] = useState(null)
  const [showManualForm,   setShowManualForm]   = useState(false)
  const [fieldErrors,      setFieldErrors]      = useState({})
  const [vlmAvailable,     setVlmAvailable]     = useState(false)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(d => setVlmAvailable(!!d.vlm_available))
      .catch(() => {})
  }, [])

  const validateField = (name, value) => {
    switch (name) {
      case 'patientId':
        return value.trim() === '' ? 'Patient ID is required' : null
      case 'monthsAfterDALK': {
        if (value === '') return 'Required'
        const n = Number(value)
        if (isNaN(n) || !Number.isInteger(n)) return 'Must be a whole number'
        if (n < 0) return 'Cannot be negative'
        if (n > 120) return 'Value seems too high (max 120 months)'
        return null
      }
      case 'ucva':
      case 'bcva': {
        if (value === '') return 'Required'
        return snellenToLogmar(value) === null
          ? 'Enter Snellen (e.g. 6/6, 6/60, 20/200) or CF / HM'
          : null
      }
      case 'sphere': {
        if (value === '') return 'Required'
        const n = Number(value)
        if (isNaN(n)) return 'Must be a number'
        if (n < -25 || n > 25) return 'Expected −25 to +25 D'
        return null
      }
      case 'cylinder': {
        if (value === '') return 'Required'
        const n = Number(value)
        if (isNaN(n)) return 'Must be a number'
        if (n < -12 || n > 12) return 'Expected −12 to +12 D'
        return null
      }
      case 'axis': {
        if (value === '') return 'Required'
        const n = Number(value)
        if (isNaN(n) || !Number.isInteger(n) || n < 0 || n > 180) return 'Must be 0–180°'
        return null
      }
      case 'k1Override': {
        if (value === '') return null
        const n = Number(value)
        if (isNaN(n) || n < 30 || n > 65) return 'K values expected 30–65 D'
        return null
      }
      case 'k2Override': {
        if (value === '') return null
        const n = Number(value)
        if (isNaN(n) || n < 30 || n > 65) return 'K values expected 30–65 D'
        return null
      }
      case 'cylOverride': {
        if (value === '') return null
        const n = Number(value)
        if (isNaN(n) || n < 0 || n > 10) return 'Expected 0–10 D'
        return null
      }
      case 'cornealThickness': {
        if (value === '') return null
        const n = Number(value)
        if (isNaN(n) || n < 150 || n > 1000) return 'Expected 150–1000 µm'
        return null
      }
      default:
        return null
    }
  }

  const handleBlur = (e) => {
    const { name, value } = e.target
    const error = validateField(name, value)
    setFieldErrors(prev => ({ ...prev, [name]: error }))
  }

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
    // Clear error as user corrects a previously flagged field
    if (fieldErrors[name] !== undefined) {
      const error = validateField(name, value)
      setFieldErrors(prev => ({ ...prev, [name]: error }))
    }
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
    // Uploading a clean eye_measurements image collapses the manual form
    if (type === 'eye_measurements') setShowManualForm(false)
    setQualityChecking(prev => ({ ...prev, [type]: true }))
    try {
      const qForm = new FormData()
      qForm.append(type, file)
      const res = await fetch('/api/analyze-quality', {
        method: 'POST',
        body: qForm,
        headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : {},
      })
      if (res.ok) {
        const data = await res.json()
        const warnings = data.warnings?.[type] || []
        setQualityWarnings(prev => {
          const next = { ...prev, [type]: warnings }
          if (next[type].length > 0) {
            setModalTriggerType(type)
            if (!vlmAvailable) setShowModeModal(true)
          }
          return next
        })
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

  const handleClear = () => {
    Object.values(images).forEach(img => { if (img?.preview) URL.revokeObjectURL(img.preview) })
    setFormData({ patientId: '', eye: 'OD', monthsAfterDALK: '', ucva: '', bcva: '', sphere: '', cylinder: '', axis: '', cornealThickness: '', k1Override: '', k2Override: '', cylOverride: '' })
    setImages({ ...EMPTY_IMAGES })
    setQualityWarnings({ ...EMPTY_WARNINGS })
    setQualityChecking({ ...EMPTY_CHECKING })
    setSubmissionMode(null)
    setShowModeModal(false)
    setModalTriggerType(null)
    setShowManualForm(false)
    setFieldErrors({})
    setResult(null)
    setError(null)
  }

  const handleModeSelect = (mode) => {
    if (mode === 'reupload') {
      setShowModeModal(false)
      setSubmissionMode(null)
      setShowManualForm(false)
      if (modalTriggerType) {
        // Only remove the specific image that had quality issues — leave others intact
        if (images[modalTriggerType]?.preview) URL.revokeObjectURL(images[modalTriggerType].preview)
        setImages(prev => ({ ...prev, [modalTriggerType]: null }))
        setQualityWarnings(prev => ({ ...prev, [modalTriggerType]: [] }))
      }
      setModalTriggerType(null)
    } else {
      setSubmissionMode(mode)
      setShowModeModal(false)
      setModalTriggerType(null)
      if (mode === 'manual') setShowManualForm(true)
    }
  }

  const ucvaLogmar = snellenToLogmar(formData.ucva)
  const bcvaLogmar = snellenToLogmar(formData.bcva)

  // ── Visibility logic ───────────────────────────────────────────────
  const hasEyeMeasurementImage    = !!images.eye_measurements
  const eyeMeasurementHasWarnings = (qualityWarnings.eye_measurements || []).length > 0

  // OCR covers inputs when image is uploaded AND either it's clean or user chose to proceed anyway
  const ocrCoversInputs = hasEyeMeasurementImage && (
    !eyeMeasurementHasWarnings || submissionMode === 'ocr'
  )

  // Show the manual form only when the user has explicitly requested it (via modal or toggle)
  // Warnings alone no longer auto-open the form — user makes the choice in the modal first
  const manualFormVisible = !ocrCoversInputs && (showManualForm || submissionMode === 'manual')

  // ── Validation ─────────────────────────────────────────────────────
  const isFormValid = () => {
    if (!formData.patientId.trim() || !formData.monthsAfterDALK) return false
    if (Object.values(fieldErrors).some(e => e !== null && e !== undefined)) return false
    if (ocrCoversInputs) return true
    if (manualFormVisible) {
      return (
        formData.ucva && formData.bcva &&
        ucvaLogmar !== null && bcvaLogmar !== null &&
        formData.sphere !== '' && formData.cylinder !== '' && formData.axis !== ''
      )
    }
    return false
  }

  const hasAnyImage = !!(images.topography || images.pachymetry || images.eye_measurements)
  const hasMeasurements = ocrCoversInputs || (manualFormVisible && formData.ucva && formData.bcva && formData.sphere !== '' && formData.cylinder !== '' && formData.axis !== '')
  const step1Done = !!(formData.patientId && formData.monthsAfterDALK)
  const step2Done = step1Done && (hasAnyImage || hasMeasurements)
  const activeStep = !step1Done ? 1 : !step2Done ? 2 : 3

  const handlePredict = async () => {
    if (!isFormValid() || isSubmitting) return
    setIsSubmitting(true); setResult(null); setError(null)
    try {
      const payload = new FormData()
      payload.append('patientId',       formData.patientId)
      payload.append('eye',             formData.eye)
      payload.append('monthsAfterDALK', Number(formData.monthsAfterDALK))
      payload.append('ucva_logmar',     ucvaLogmar ?? '')
      payload.append('bcva_logmar',     bcvaLogmar ?? '')
      payload.append('sphere_diopters',   formData.sphere   !== '' ? Number(formData.sphere)   : '')
      payload.append('cylinder_diopters', formData.cylinder !== '' ? Number(formData.cylinder) : '')
      payload.append('axis_degrees',      formData.axis     !== '' ? Number(formData.axis)     : '')
      if (formData.cornealThickness !== '') payload.append('corneal_thickness_override', Number(formData.cornealThickness))
      if (formData.k1Override  !== '')      payload.append('k1_override',  Number(formData.k1Override))
      if (formData.k2Override  !== '')      payload.append('k2_override',  Number(formData.k2Override))
      if (formData.cylOverride !== '')      payload.append('cyl_override', Number(formData.cylOverride))

      const effectiveMode = submissionMode || 'ocr'
      payload.append('mode', effectiveMode)

      if (effectiveMode !== 'manual') {
        if (images.topography?.file)       payload.append('topography',       images.topography.file)
        if (images.pachymetry?.file)       payload.append('pachymetry',       images.pachymetry.file)
        if (images.eye_measurements?.file) payload.append('eye_measurements', images.eye_measurements.file)
      }

      const response = await fetch('/api/predictions', {
        method: 'POST',
        body: payload,
        headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : {},
      })
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
      <Sidebar auth={auth} onLogout={onLogout} />
      <div className="app-main">
        <main className="page-content prediction-content">
          <Header
            title="New Assessment"
            subtitle="Upload corneal images and run a post-DALK correction prediction"
            action={{ label: 'Clear', onClick: handleClear, className: 'page-header-action-btn--danger' }}
          />

          <PredictionStepper activeStep={activeStep} />

          <div className="prediction-form">
            <PatientInfo formData={formData} handleInputChange={handleInputChange} handleBlur={handleBlur} fieldErrors={fieldErrors} />

            <ImageUpload
              images={images}
              handleImageUpload={handleImageUpload}
              removeImage={removeImage}
              qualityWarnings={qualityWarnings}
              qualityChecking={qualityChecking}
              submissionMode={submissionMode}
              vlmAvailable={vlmAvailable}
              onManualEntry={() => setShowManualForm(true)}
            />

            {/* ── OCR covers inputs: show confirmation (clean image only) ── */}
            {ocrCoversInputs && !eyeMeasurementHasWarnings && (
              <div className="ocr-ready-note">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Eye measurements report uploaded — UCVA, BCVA, SPH, CYL and AXIS will be extracted automatically via OCR.
              </div>
            )}

            {/* ── Manual form ── */}
            {manualFormVisible && (
              <NumericInputs
                formData={formData}
                handleInputChange={handleInputChange}
                handleBlur={handleBlur}
                fieldErrors={fieldErrors}
                submissionMode={submissionMode}
                showAsOcrFallback={eyeMeasurementHasWarnings && submissionMode === 'manual'}
              />
            )}

            {/* ── Toggle: show manual entry when no image and form not yet open ── */}
            {!ocrCoversInputs && !manualFormVisible && (
              <div className="manual-toggle-row">
                <button
                  type="button"
                  className="manual-toggle-btn"
                  onClick={() => setShowManualForm(true)}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                  Enter measurements manually
                </button>
                <span className="manual-toggle-hint">
                  Or upload an Eye Measurements report above to extract automatically
                </span>
              </div>
            )}

            {/* ── Collapse button when manual form is open and user can close it ── */}
            {manualFormVisible && submissionMode !== 'manual' && (
              <button
                type="button"
                className="manual-collapse-btn"
                onClick={() => setShowManualForm(false)}
              >
                ✕ Hide manual entry
              </button>
            )}

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

            <ResultPanel result={result} auth={auth} />
          </div>

        </main>
      </div>

      {showModeModal && (
        <ModeModal
          qualityWarnings={qualityWarnings}
          onModeSelect={handleModeSelect}
          onClose={() => handleModeSelect('reupload')}
        />
      )}
    </div>
  )
}

export default Prediction
