import React, { useState } from 'react'
import Header        from '../../components/Header/Header'
import Sidebar       from '../../components/Sidebar/Sidebar'
import PatientInfo   from '../../components/PatientInfo/PatientInfo'
import ImageUpload   from '../../components/ImageUpload/ImageUpload'
import NumericInputs from '../../components/NumericInputs/NumericInputs'
import PredictButton from '../../components/PredictButton/PredictButton'
import ResultPanel   from '../../components/ResultPanel/ResultPanel'
import './Prediction.css'
import { snellenToLogmar } from '../../utils/visualAcuity'

function Prediction({ auth, onLogout }) {
  const [formData, setFormData] = useState({
    patientId: '', eye: 'OD', monthsAfterDALK: '',
    ucva: '', bcva: '', sphere: '', cylinder: '', axis: '', cornealThickness: '',
    k1Override: '', k2Override: '', cylOverride: '',
  })
  const [images, setImages]         = useState({ topography: null, pachymetry: null })
  const [result, setResult]         = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError]           = useState(null)
  const [qualityWarnings, setQualityWarnings] = useState({ topography: [], pachymetry: [] })
  const [qualityChecking, setQualityChecking] = useState({ topography: false, pachymetry: false })

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleImageUpload = async (type, e) => {
    const file = e.target.files[0]
    if (!file) return
    if (!['image/jpeg','image/png','image/jpg'].includes(file.type)) {
      alert('Please upload JPG or PNG only'); e.target.value = ''; return
    }
    setImages(prev => ({ ...prev, [type]: { file, preview: URL.createObjectURL(file) } }))
    setQualityWarnings(prev => ({ ...prev, [type]: [] }))
    setQualityChecking(prev => ({ ...prev, [type]: true }))
    try {
      const qForm = new FormData()
      qForm.append(type, file)
      const res = await fetch('/api/analyze-quality', { method: 'POST', body: qForm })
      if (res.ok) {
        const data = await res.json()
        setQualityWarnings(prev => ({ ...prev, [type]: data.warnings?.[type] || [] }))
      }
    } catch {
      // non-fatal — silently ignore
    } finally {
      setQualityChecking(prev => ({ ...prev, [type]: false }))
    }
  }

  const removeImage = (type) => {
    if (images[type]?.preview) URL.revokeObjectURL(images[type].preview)
    setImages(prev => ({ ...prev, [type]: null }))
    setQualityWarnings(prev => ({ ...prev, [type]: [] }))
    setQualityChecking(prev => ({ ...prev, [type]: false }))
  }

  const ucvaLogmar = snellenToLogmar(formData.ucva)
  const bcvaLogmar = snellenToLogmar(formData.bcva)

  const isFormValid = () =>
    formData.patientId.trim() && formData.monthsAfterDALK &&
    formData.ucva && formData.bcva &&
    ucvaLogmar !== null && bcvaLogmar !== null &&
    formData.sphere &&
    formData.cylinder && formData.axis
    // Images are optional — the backend imputer fills missing OCR values.

  const handlePredict = async () => {
    if (!isFormValid() || isSubmitting) return
    setIsSubmitting(true); setResult(null); setError(null)
    try {
      const payload = new FormData()
      payload.append('patientId',       formData.patientId)
      payload.append('eye',             formData.eye)
      payload.append('monthsAfterDALK', Number(formData.monthsAfterDALK))
      payload.append('ucva_logmar',     ucvaLogmar)
      payload.append('bcva_logmar',     bcvaLogmar)
      payload.append('sphere_diopters',   Number(formData.sphere))
      payload.append('cylinder_diopters', Number(formData.cylinder))
      payload.append('axis_degrees',      Number(formData.axis))
      if (formData.cornealThickness !== '') {
        payload.append('corneal_thickness_override', Number(formData.cornealThickness))
      }
      if (formData.k1Override  !== '') payload.append('k1_override',  Number(formData.k1Override))
      if (formData.k2Override  !== '') payload.append('k2_override',  Number(formData.k2Override))
      if (formData.cylOverride !== '') payload.append('cyl_override', Number(formData.cylOverride))
      payload.append('topography', images.topography.file)  // OCR → K1, astig, K2
      payload.append('pachymetry', images.pachymetry.file)  // OCR → CCT

      const response = await fetch('/api/predictions', { method:'POST', body: payload })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.message || 'Prediction failed')
      }
      const data = await response.json()
      setResult(data)
      setTimeout(() => {
        document.querySelector('.result-panel')
          ?.scrollIntoView({ behavior:'smooth', block:'start' })
      }, 100)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="prediction-page">
      <Header auth={auth} onLogout={onLogout} />
      <div className="layout-shell">
        <Sidebar auth={auth} />
        <main className="layout-main">
          <div className="container">
            <PatientInfo formData={formData} handleInputChange={handleInputChange} />
            <ImageUpload images={images} handleImageUpload={handleImageUpload} removeImage={removeImage} qualityWarnings={qualityWarnings} qualityChecking={qualityChecking} />
            <NumericInputs formData={formData} handleInputChange={handleInputChange} />
            <PredictButton isDisabled={!isFormValid() || isSubmitting} onClick={handlePredict} />
            {isSubmitting && (
              <div className="loading-state">
                <div className="loading-spinner" />
                <p>Analysing report images and predicting...</p>
              </div>
            )}
            {error && <div className="error-message">⚠ {error}</div>}
            <ResultPanel result={result} />
          </div>
        </main>
      </div>
    </div>
  )
}
export default Prediction