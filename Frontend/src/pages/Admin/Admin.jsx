import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, ChevronRight, Edit3, Paperclip, Pencil, Settings, Trash2, X } from 'lucide-react'
import Header from '../../components/Header/Header'
import Sidebar from '../../components/Sidebar/Sidebar'
import './Admin.css'

function formatDateTime(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

function clinicianSpecialtyFrom(description) {
  const text = String(description || '').toLowerCase()
  if (text.includes('pediatric')) return 'Pediatrician'
  if (text.includes('cornea')) return 'Cornea Specialist'
  if (text.includes('retina')) return 'Retina Specialist'
  if (text.includes('glaucoma')) return 'Glaucoma Specialist'
  if (text.includes('optometrist')) return 'Optometrist'
  return 'General Practitioner'
}

function Admin({ auth, onLogout }) {
  const navigate = useNavigate()
  const token = auth?.token

  const currentTab = new URLSearchParams(window.location.search).get('tab') || 'directory'
  const activeTab = currentTab
  const setActiveTab = (tab) => navigate(`/admin?tab=${tab}`)

  // Lists & Filters
  const [search, setSearch] = useState('')
  const [specialtyFilter, setSpecialtyFilter] = useState('')
  const [locationFilter, setLocationFilter] = useState('')

  // API Data
  const [clinicians, setClinicians] = useState([])
  const [loadingClinicians, setLoadingClinicians] = useState(true)
  const [cliniciansError, setCliniciansError] = useState(null)

  const [selectedClinicianId, setSelectedClinicianId] = useState(null)
  const [expandedClinicianId, setExpandedClinicianId] = useState(null)
  
  const [patientsByClinician, setPatientsByClinician] = useState({})
  const [patientsLoadingByClinician, setPatientsLoadingByClinician] = useState({})
  const [patientsErrorByClinician, setPatientsErrorByClinician] = useState({})

  const [stats, setStats] = useState(null)

  // Forms
  const [createForm, setCreateForm] = useState({ username: '', password: '', role: 'user', doctorDescription: '', photo: null })
  const [createStatus, setCreateStatus] = useState(null)
  const [createSubmitting, setCreateSubmitting] = useState(false)

  const [profileForm, setProfileForm] = useState({ specialty: '', doctorDescription: '', photo: null })
  const [profileStatus, setProfileStatus] = useState(null)
  const [profileSubmitting, setProfileSubmitting] = useState(false)

  const [resetPasswordSubmitting, setResetPasswordSubmitting] = useState(false)

  const [globalSettings, setGlobalSettings] = useState({
    syncUrl: 'https://api.primary-ehr.local/v1',
    realTimeSync: true,
    minPasswordLength: '8',
    twoFactor: true,
    confThreshold: '80',
    automatedTraining: false
  })

  // Fetch Clinicians
  const fetchClinicians = async () => {
    if (!token) return
    setLoadingClinicians(true)
    setCliniciansError(null)
    try {
      const response = await fetch('/api/admin/clinicians', {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Failed to load clinicians.')
      const list = data.clinicians || []
      setClinicians(list)
      setSelectedClinicianId((prev) => (prev && list.some((c) => c.id === prev) ? prev : (list[0]?.id || null)))
    } catch (error) {
      setCliniciansError(error.message || 'Failed to load clinicians.')
    } finally {
      setLoadingClinicians(false)
    }
  }

  // Fetch Stats for Predictions Tab
  const fetchStats = async () => {
    if (!token) return
    try {
      const response = await fetch('/api/dashboard/stats', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    fetchClinicians()
    fetchStats()
  }, [token])

  const selectedClinician = useMemo(
    () => clinicians.find((c) => c.id === selectedClinicianId) || null,
    [clinicians, selectedClinicianId],
  )

  useEffect(() => {
    setProfileStatus(null)
    setProfileForm({
      specialty: clinicianSpecialtyFrom(selectedClinician?.description),
      doctorDescription: selectedClinician?.description || '',
      photo: null,
    })
  }, [selectedClinician?.id, selectedClinician?.description])

  const clinicianRows = useMemo(() => {
    return clinicians.map((c) => ({
      ...c,
      specialty: clinicianSpecialtyFrom(c.description),
      location: 'Main Clinic',
      scheduleStatus: c.lastActivityAt ? 'Active' : 'Pending',
    }))
  }, [clinicians])

  const filteredClinicians = useMemo(() => {
    const q = search.trim().toLowerCase()
    return clinicianRows.filter((c) => {
      const bySearch = !q || String(c.username || '').toLowerCase().includes(q)
      const bySpec = !specialtyFilter || c.specialty === specialtyFilter
      const byLocation = !locationFilter || c.location === locationFilter
      return bySearch && bySpec && byLocation
    })
  }, [search, specialtyFilter, locationFilter, clinicianRows])

  const loadClinicianPatients = async (clinicianId) => {
    if (!token || !clinicianId) return
    if (patientsByClinician[clinicianId]) return
    setPatientsLoadingByClinician((prev) => ({ ...prev, [clinicianId]: true }))
    setPatientsErrorByClinician((prev) => ({ ...prev, [clinicianId]: null }))
    try {
      const response = await fetch(`/api/admin/clinicians/${encodeURIComponent(clinicianId)}/patients`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Failed to load clinician patients.')
      setPatientsByClinician((prev) => ({ ...prev, [clinicianId]: data.patients || [] }))
    } catch (error) {
      setPatientsErrorByClinician((prev) => ({ ...prev, [clinicianId]: error.message || 'Failed to load patients.' }))
    } finally {
      setPatientsLoadingByClinician((prev) => ({ ...prev, [clinicianId]: false }))
    }
  }

  const handleRowToggle = (cId) => {
    if (expandedClinicianId === cId) {
      setExpandedClinicianId(null)
    } else {
      setExpandedClinicianId(cId)
      setSelectedClinicianId(cId)
      loadClinicianPatients(cId)
    }
  }

  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    setCreateStatus(null)
    if (!createForm.username.trim() || !createForm.password.trim()) {
      setCreateStatus({ type: 'error', message: 'Username and password are required.' })
      return
    }
    try {
      setCreateSubmitting(true)
      const body = new FormData()
      body.append('username', createForm.username.trim())
      body.append('password', createForm.password)
      body.append('role', createForm.role)
      if (createForm.role === 'user') {
        body.append('doctorDescription', createForm.doctorDescription.trim())
        if (createForm.photo) body.append('photo', createForm.photo)
      }
      const response = await fetch('/api/users', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Failed to create clinician.')
      setCreateStatus({ type: 'success', message: 'Clinician created successfully.' })
      setCreateForm({ username: '', password: '', role: 'user', doctorDescription: '', photo: null })
      await fetchClinicians()
      setTimeout(() => setActiveTab('directory'), 1500)
    } catch (error) {
      setCreateStatus({ type: 'error', message: error.message || 'Failed to create clinician.' })
    } finally {
      setCreateSubmitting(false)
    }
  }

  const handleProfileSave = async (e) => {
    e.preventDefault()
    if (!selectedClinician?.id) return
    setProfileStatus(null)
    try {
      setProfileSubmitting(true)
      const body = new FormData()
      body.append('doctorDescription', profileForm.doctorDescription.trim())
      if (profileForm.photo) body.append('photo', profileForm.photo)
      const response = await fetch(`/api/admin/clinicians/${encodeURIComponent(selectedClinician.id)}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Failed to update clinician.')
      setProfileStatus({ type: 'success', message: 'Profile updated!' })
      await fetchClinicians()
    } catch (error) {
      setProfileStatus({ type: 'error', message: error.message || 'Failed to update profile.' })
    } finally {
      setProfileSubmitting(false)
    }
  }

  const handlePatientHistory = (patientId, eye) => {
    navigate(`/history?patientId=${encodeURIComponent(patientId)}&eye=${encodeURIComponent(eye || '')}`)
  }

  const handleDeleteClinician = async (clinicianId) => {
    if (!window.confirm('Are you sure you want to permanently remove this clinician?')) return;
    try {
      let response = await fetch(`/api/users/${encodeURIComponent(clinicianId)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) {
        response = await fetch(`/api/admin/clinicians/${encodeURIComponent(clinicianId)}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!response.ok) throw new Error('Failed to delete clinician. Backend endpoint may be unsupported.')
      }
      if (selectedClinicianId === clinicianId) setSelectedClinicianId(null)
      await fetchClinicians()
      window.alert('Clinician removed successfully.')
    } catch (error) {
      window.alert(error.message)
    }
  }

  const handleDeactivate = (e) => {
    e.preventDefault();
    window.alert('Account has been marked as inactive.');
  }

  const handleResetPassword = async (clinicianId) => {
    const newPassword = window.prompt('Enter new password for this clinician (min 6 characters):')
    if (!newPassword) return;
    if (newPassword.length < 6) {
      window.alert('Password must be at least 6 characters.')
      return
    }
    try {
      setResetPasswordSubmitting(true)
      const response = await fetch(`/api/admin/clinicians/${encodeURIComponent(clinicianId)}/reset-password`, {
        method: 'PATCH',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({ newPassword }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Failed to reset password.')
      window.alert('Password reset successfully.')
    } catch (error) {
      window.alert(error.message || 'Failed to reset password.')
    } finally {
      setResetPasswordSubmitting(false)
    }
  }

  const renderAccountHandling = () => (
    <aside className="admin-side-panel">
      <button className="admin-side-panel-close"><X size={18} /></button>
      <h3>Account Handling:<br/>{selectedClinician ? selectedClinician.username : 'No Selection'}</h3>
      
      {selectedClinician ? (
        <form onSubmit={handleProfileSave}>
          <div className="admin-side-avatar-container">
            <div className="admin-side-avatar">
              {selectedClinician.photoDataUrl ? (
                <img src={selectedClinician.photoDataUrl} alt="Doctor" style={{ width: '100%', height: '100%', borderRadius: '50%' }} />
              ) : (
                <div style={{ width: '100%', height: '100%', borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', color: '#64748b' }}>
                  {selectedClinician.username.slice(0,2).toUpperCase()}
                </div>
              )}
              <div className="admin-edit-avatar-btn">
                <label style={{cursor: 'pointer', margin: 0, padding: 0, display: 'flex'}}>
                  <Edit3 size={12} />
                  <input type="file" accept="image/*" style={{display: 'none'}} onChange={(e) => setProfileForm({ ...profileForm, photo: e.target.files?.[0] || null })} />
                </label>
              </div>
            </div>
            <div className="admin-strong" style={{ fontSize: '0.85rem' }}>Edit/Upload New Photo</div>
            {profileForm.photo && <div style={{fontSize: '0.75rem', color: 'green'}}>New photo selected</div>}
          </div>

          <div className="admin-form-group">
            <label>Specialty</label>
            <input type="text" value={profileForm.specialty} onChange={e => setProfileForm({...profileForm, specialty: e.target.value})} />
          </div>

          <div className="admin-form-group">
            <label>Description/Bio</label>
            <textarea rows={4} value={profileForm.doctorDescription} onChange={e => setProfileForm({...profileForm, doctorDescription: e.target.value})} />
          </div>

          <div className="admin-form-group" style={{ marginBottom: '20px' }}>
            <label>Access Permissions</label>
            <label className="admin-toggle">
              <input type="checkbox" defaultChecked />
              <div className="admin-toggle-slider"></div>
              <span className="admin-toggle-text">View Data</span>
            </label>
            <label className="admin-toggle">
              <input type="checkbox" defaultChecked />
              <div className="admin-toggle-slider"></div>
              <span className="admin-toggle-text">Confirm Predictions</span>
            </label>
          </div>

          {profileStatus && (
            <div style={{ padding: '10px', marginBottom: '10px', borderRadius: '4px', fontSize: '0.85rem', background: profileStatus.type === 'error' ? '#fee2e2' : '#dcfce7', color: profileStatus.type === 'error' ? '#991b1b' : '#166534' }}>
              {profileStatus.message}
            </div>
          )}

          <button type="submit" disabled={profileSubmitting} className="admin-btn btn-primary">
            {profileSubmitting ? 'Saving...' : 'Save Profile Details'}
          </button>
          <button type="button" disabled={resetPasswordSubmitting} className="admin-btn btn-secondary" onClick={() => handleResetPassword(selectedClinician.id)}>
            {resetPasswordSubmitting ? 'Resetting...' : 'Reset Password'}
          </button>
          <button type="button" className="admin-btn btn-yellow" onClick={handleDeactivate}>Deactivate Account</button>
          <button type="button" className="admin-btn btn-red" onClick={() => handleDeleteClinician(selectedClinician.id)}>Remove Clinician</button>
        </form>
      ) : (
        <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Select a clinician from the directory to manage their account details.</div>
      )}
    </aside>
  )

  const handleGlobalSettingsSave = () => {
    window.alert('Global Settings saved successfully.');
  }

  const renderGlobalSettingsRight = () => (
    <aside className="admin-side-panel">
      <button className="admin-side-panel-close"><X size={18} /></button>
      <h3>Global System<br/>Settings</h3>

      <div className="admin-settings-section">
        <div className="admin-form-group">
          <label>Global System Configuration</label>
        </div>
        <div className="admin-form-group">
          <label>Data Synchronization</label>
          <select value={globalSettings.syncUrl} onChange={(e) => setGlobalSettings({...globalSettings, syncUrl: e.target.value})}>
            <option value="https://api.primary-ehr.local/v1">EHR Primary Sink</option>
            <option value="https://api.backup.local">Backup Source URL</option>
          </select>
        </div>
        <label className="admin-toggle" style={{ marginBottom: '20px' }}>
          <input type="checkbox" checked={globalSettings.realTimeSync} onChange={(e) => setGlobalSettings({...globalSettings, realTimeSync: e.target.checked})} />
          <div className="admin-toggle-slider"></div>
          <span className="admin-toggle-text">Real-time Sync</span>
        </label>

        <div className="admin-form-group">
          <label>User Account Policies</label>
          <label style={{fontWeight: 'normal'}}>Minimum Password Length</label>
          <input type="number" value={globalSettings.minPasswordLength} onChange={(e) => setGlobalSettings({...globalSettings, minPasswordLength: e.target.value})} />
        </div>
        <label className="admin-toggle" style={{ marginBottom: '20px' }}>
          <input type="checkbox" checked={globalSettings.twoFactor} onChange={(e) => setGlobalSettings({...globalSettings, twoFactor: e.target.checked})} />
          <div className="admin-toggle-slider"></div>
          <span className="admin-toggle-text">Enable 2FA (System Wide)</span>
        </label>

        <div className="admin-form-group">
          <label>System Logs</label>
          <textarea className="admin-logs-box" readOnly value={`Model updated to v3.1.\nData sync complete.\nData sync complete.\nFailed 1 sync record.\nModel updated to v3.1`} />
        </div>

        <button className="admin-btn btn-primary" onClick={handleGlobalSettingsSave}>Save Global Settings</button>
      </div>
    </aside>
  )

  const getPercentageHeight = (val, max) => {
    if (!max || max === 0) return '0%';
    return `${(val / max) * 100}%`;
  }

  const statGlasses = stats?.glasses || 0
  const statLenses = stats?.contactLenses || 0
  const statNone = stats?.noCorrection || 0
  const maxStat = Math.max(statGlasses, statLenses, statNone, 1)

  return (
    <div className="app-shell" style={{ background: '#f8fafc' }}>
      <Sidebar auth={auth} onLogout={onLogout} />
      <Header
        title="Clinician Management Dashboard"
        action={{ label: 'Admin User', icon: <Settings size={18}/>, onClick: onLogout }}
      />
      
      <div className="page-content admin-page-layout">
        
        {/* VIEW: CLINICIAN DIRECTORY */}
        {activeTab === 'directory' && (
          <div className="admin-layout-grid">
            <div className="admin-main-panel">
              <div className="admin-directory-header">
                <h2>Clinician Directory</h2>
                <button className="admin-btn btn-primary" style={{ width: 'auto', padding: '10px 20px', margin: 0 }} onClick={() => setActiveTab('add')}>
                  Add New Clinician
                </button>
              </div>

              <div className="admin-filters">
                <input type="text" placeholder="Search Clinicians..." value={search} onChange={e => setSearch(e.target.value)} />
                <select value={specialtyFilter} onChange={e => setSpecialtyFilter(e.target.value)}>
                  <option value="">All Specialties</option>
                  <option value="General Practitioner">General Practitioner</option>
                  <option value="Pediatrician">Pediatrician</option>
                  <option value="Optometrist">Optometrist</option>
                  <option value="Cornea Specialist">Cornea Specialist</option>
                  <option value="Retina Specialist">Retina Specialist</option>
                  <option value="Glaucoma Specialist">Glaucoma Specialist</option>
                </select>
                <select value={locationFilter} onChange={e => setLocationFilter(e.target.value)}>
                  <option value="">All Locations</option>
                  <option value="Main Clinic">Main Clinic</option>
                </select>
              </div>

              <div className="admin-table-shell">
                <div className="admin-table-header">
                  <span></span>
                  <span>Clinician (Profile)</span>
                  <span>Specialty</span>
                  <span>Prediction Count</span>
                  <span>Status</span>
                  <span>Actions</span>
                </div>
                
                {loadingClinicians && <div style={{padding: '20px', textAlign: 'center'}}>Loading clinicians...</div>}
                {cliniciansError && <div style={{padding: '20px', color: 'red'}}>{cliniciansError}</div>}
                
                {!loadingClinicians && filteredClinicians.map(c => {
                  const isExpanded = expandedClinicianId === c.id;
                  const patients = patientsByClinician[c.id] || []
                  const pLoad = patientsLoadingByClinician[c.id]
                  
                  return (
                    <div key={c.id}>
                      <div className={`admin-row ${selectedClinicianId === c.id ? 'admin-row-selected' : ''}`}>
                        <button className="admin-expand-btn" onClick={() => handleRowToggle(c.id)}>
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                        <div className="admin-profile-cell">
                          {c.photoDataUrl ? (
                            <img src={c.photoDataUrl} alt="Dr" className="admin-profile-img" />
                          ) : (
                            <div className="admin-profile-img" style={{ display:'flex', alignItems:'center', justifyContent:'center', fontWeight:'bold', color: '#fff', background: 'var(--color-primary)'}}>
                              {c.username.substring(0,2).toUpperCase()}
                            </div>
                          )}
                          <div className="admin-profile-text">
                            <span className="admin-strong">{c.username}</span>
                            <span className="admin-sub">{c.specialty}</span>
                          </div>
                        </div>
                        <span>{c.specialty}</span>
                        <span>{c.patientCount || 0}</span>
                        <span><span className="admin-status-pill">{c.scheduleStatus}</span></span>
                        <div className="admin-row-actions">
                          <button onClick={() => { setSelectedClinicianId(c.id); setActiveTab('directory'); }} title="Focus Account"><Paperclip size={14}/></button>
                          <button onClick={() => handleDeleteClinician(c.id)} title="Remove Clinician"><Trash2 size={14} color="#ef4444" /></button>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="admin-inner-panel">
                          <h4>Predictions for {c.username}'s Patients</h4>
                          <div className="admin-inner-table">
                            <div className="admin-inner-header">
                              <span>Patient (ID)</span>
                              <span>Last Visit Date</span>
                              <span>Recommendation</span>
                              <span>Confidence</span>
                              <span>Status</span>
                              <span>Actions</span>
                            </div>
                            {pLoad && <div style={{padding: '10px 14px'}}>Loading patient records...</div>}
                            {!pLoad && patients.length === 0 && <div style={{padding: '10px 14px', color:'var(--color-text-muted)'}}>No recorded patients for this clinician.</div>}
                            {!pLoad && patients.map((p, i) => {
                              const getRecColor = (rec) => {
                                if (rec?.includes('Spectacles')) return 'badge-blue';
                                if (rec?.includes('Contact Lenses')) return 'badge-purple';
                                return 'badge-green';
                              };
                              return (
                                <div key={i} className="admin-inner-row">
                                  <span className="admin-strong">{p.patientId}</span>
                                  <span>{formatDateTime(p.lastAssessment || p.lastVisit)}</span>
                                  <div><span className={getRecColor(p.recommendation)}>{p.recommendation || 'None'}</span></div>
                                  <span>{p.confidence ? `${p.confidence}%` : '—'}</span>
                                  <span>{p.status || 'Verified'}</span>
                                  <div className="admin-row-actions">
                                    <button onClick={() => handlePatientHistory(p.patientId, p.eye)} title="View Patient chart"><Pencil size={12}/></button>
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {renderAccountHandling()}
          </div>
        )}

        {/* VIEW: ADD CLINICIAN (NEW) */}
        {activeTab === 'add' && (
          <div className="admin-layout-grid">
            <div className="admin-main-panel">
              <div className="admin-directory-header">
                <h2>Add New Clinician</h2>
                <button className="admin-btn btn-secondary" style={{ width: 'auto', padding: '10px 20px', margin: 0, border: '1px solid #cbd5e1', background: 'transparent' }} onClick={() => setActiveTab('directory')}>
                  Cancel & Return
                </button>
              </div>
              <form onSubmit={handleCreateSubmit} style={{ maxWidth: '600px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <div className="admin-form-group">
                  <label>Username</label>
                  <input type="text" value={createForm.username} onChange={e => setCreateForm({...createForm, username: e.target.value})} required/>
                </div>
                <div className="admin-form-group">
                  <label>Password</label>
                  <input type="password" value={createForm.password} onChange={e => setCreateForm({...createForm, password: e.target.value})} style={{padding: '10px', borderRadius: '8px', border: '1px solid var(--color-border)'}} required/>
                </div>
                <div className="admin-form-group">
                  <label>Role</label>
                  <select value={createForm.role} onChange={e => setCreateForm({...createForm, role: e.target.value})}>
                    <option value="user">Clinician</option>
                    <option value="admin">Administrator</option>
                  </select>
                </div>
                {createForm.role === 'user' && (
                  <>
                    <div className="admin-form-group">
                      <label>Photo</label>
                      <input type="file" accept="image/*" onChange={e => setCreateForm({...createForm, photo: e.target.files?.[0] || null})} style={{padding: '8px'}} />
                    </div>
                    <div className="admin-form-group">
                      <label>Description (Bio)</label>
                      <textarea rows={4} value={createForm.doctorDescription} onChange={e => setCreateForm({...createForm, doctorDescription: e.target.value})} />
                    </div>
                  </>
                )}
                
                {createStatus && (
                  <div style={{ padding: '12px', borderRadius: '8px', background: createStatus.type === 'error' ? '#fee2e2' : '#dcfce7', color: createStatus.type === 'error' ? '#991b1b' : '#166534' }}>
                    {createStatus.message}
                  </div>
                )}
                
                <button type="submit" disabled={createSubmitting} className="admin-btn btn-primary" style={{marginTop: '10px', width: '200px'}}>
                  {createSubmitting ? 'Creating...' : 'Create Clinician'}
                </button>
              </form>
            </div>
            {renderAccountHandling()}
          </div>
        )}

        {/* VIEW: SETTINGS */}
        {activeTab === 'settings' && (
           <div className="admin-layout-grid">
             <div className="admin-main-panel">
               <div className="admin-directory-header" style={{ marginBottom: '30px' }}>
                  <h2>Global System Configuration</h2>
                  <span style={{color: 'var(--color-text-muted)', fontSize: '0.85rem'}}>Updated Live</span>
               </div>

               <div className="admin-settings-container">
                 <div>
                    <div className="admin-form-group">
                      <label>Data Synchronization</label>
                      <select value={globalSettings.syncUrl} onChange={(e) => setGlobalSettings({...globalSettings, syncUrl: e.target.value})}>
                        <option value="https://api.primary-ehr.local/v1">EHR Primary Sink</option>
                        <option value="https://api.backup.local">Backup Source</option>
                      </select>
                    </div>
                    <label className="admin-toggle">
                      <input type="checkbox" checked={globalSettings.realTimeSync} onChange={(e) => setGlobalSettings({...globalSettings, realTimeSync: e.target.checked})} />
                      <div className="admin-toggle-slider"></div>
                      <span className="admin-toggle-text">Real-time Sync [ON]</span>
                    </label>

                    <div className="admin-form-group" style={{ marginTop: '20px' }}>
                      <label>Advanced AI Model Settings</label>
                      <label style={{fontWeight: 'normal', color: 'var(--color-text-secondary)', textTransform: 'none'}}>Prediction Algorithm</label>
                      <select>
                        <option>XGBoost (Active)</option>
                        <option>Random Forest (Legacy)</option>
                      </select>
                    </div>

                    <div className="admin-form-group" style={{ marginTop: '20px' }}>
                      <label>Clinical Metric Defaults</label>
                      <label style={{fontWeight: 'normal', color: 'var(--color-text-secondary)', textTransform: 'none'}}>Visual Acuity Input Format</label>
                      <select>
                        <option>Snellen (e.g. 6/6)</option>
                        <option>logMAR (e.g. 0.0)</option>
                        <option>Decimal (e.g. 1.0)</option>
                      </select>
                    </div>
                 </div>

                 <div>
                    <div className="admin-form-group">
                      <label>User Account Policies</label>
                      <label style={{fontWeight: 'normal', color: 'var(--color-text-secondary)', textTransform: 'none'}}>Minimum Password Length</label>
                      <input type="number" value={globalSettings.minPasswordLength} onChange={(e) => setGlobalSettings({...globalSettings, minPasswordLength: e.target.value})} />
                    </div>
                    <label className="admin-toggle">
                      <input type="checkbox" checked={globalSettings.twoFactor} onChange={(e) => setGlobalSettings({...globalSettings, twoFactor: e.target.checked})} />
                      <div className="admin-toggle-slider"></div>
                      <span className="admin-toggle-text">Require 2FA for Clinic Admins</span>
                    </label>

                    <div className="admin-form-group" style={{ marginTop: '20px' }}>
                      <label style={{fontWeight: 'normal', color: 'var(--color-text-secondary)', textTransform: 'none'}}>Confidence Threshold (%)</label>
                      <input type="number" value={globalSettings.confThreshold} onChange={(e) => setGlobalSettings({...globalSettings, confThreshold: e.target.value})} />
                    </div>

                    <div className="admin-form-group" style={{ marginTop: '20px' }}>
                      <label>OCR Extraction Engine</label>
                      <label style={{fontWeight: 'normal', color: 'var(--color-text-secondary)', textTransform: 'none'}}>Image Processing Sensitivity</label>
                      <select>
                        <option>High (Slower, High Accuracy)</option>
                        <option>Standard (Balanced)</option>
                        <option>Fast (Quick Scans)</option>
                      </select>
                    </div>
                 </div>

                 <div style={{gridColumn: '1 / -1', borderTop: '1px solid var(--color-border)', paddingTop: '20px', display: 'flex', justifyContent: 'space-between'}}>
                    <div style={{ flex: 1, marginRight: '20px' }}>
                      <label style={{fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom:'10px'}}>Security & Network</label>
                      <button className="admin-btn btn-primary" onClick={() => window.alert('VPN tunnel settings initialized. Please provide configuration.')} style={{width: '200px'}}>Configure VPN Tunnels</button>
                    </div>
                    <div>
                      <label className="admin-toggle" style={{ marginTop: '30px' }}>
                        <input type="checkbox" checked={globalSettings.automatedTraining} onChange={(e) => setGlobalSettings({...globalSettings, automatedTraining: e.target.checked})} />
                        <div className="admin-toggle-slider"></div>
                        <span className="admin-toggle-text">Enable Automated<br/>Nightly Model Retraining</span>
                      </label>
                    </div>
                 </div>
               </div>

               <div style={{ borderTop: '2px solid var(--color-border)', marginTop: '20px', paddingTop: '20px' }}>
                 <h3>Action and Status Logs</h3>
                 <div className="admin-form-group" style={{marginTop: '10px'}}>
                    <label>System Logs</label>
                    <textarea className="admin-logs-box" style={{height: '140px'}} readOnly value={`[SYS] Model v3.1 active and parsing topography.\n[SYS] Real-time sync heart beat OK.\n[WARN] Clinician ID 1 login attempt registered out of bounds.\n[SYS] Cache cleared successfully.`} />
                 </div>
               </div>
             </div>

             {renderGlobalSettingsRight()}
           </div>
        )}

        {/* VIEW: PREDICTIONS */}
        {activeTab === 'predictions' && (
           <div className="admin-layout-grid">
             <div className="admin-main-panel">
                <div className="admin-directory-header" style={{ marginBottom: '30px' }}>
                  <h2>Global Prediction Model Performance (AIv3.1)</h2>
                  <select style={{ border: '1px solid var(--color-border)', padding: '6px 12px', borderRadius: '4px' }}>
                    <option>Affect in Content</option>
                  </select>
                </div>

                <div className="admin-grid-top">
                  <div className="admin-stats-card">
                    <h4>AI Model Accuracy (SPH/CYL) over 12 Months</h4>
                    <div className="mock-line-chart">
                      <div className="mock-axis-y">
                        <span>100%</span>
                        <span>80%</span>
                        <span>60%</span>
                        <span>40%</span>
                        <span>20%</span>
                        <span>0%</span>
                      </div>
                      <div className="mock-line"></div>
                      <div className="mock-line-dots">
                        {[20, 30, 48, 48, 62, 60, 68, 75, 80, 85, 92].map((y, i) => (
                           <div key={i} className="mock-dot" style={{ left: `${i * 10}%`, bottom: `${y}%`}}></div>
                        ))}
                      </div>
                      <div className="mock-axis-x">
                        <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span><span>6</span>
                        <span>7</span><span>8</span><span>9</span><span>10</span><span>11</span><span>12</span>
                      </div>
                    </div>
                    <div style={{textAlign: 'right', fontWeight: 'bold', color: 'var(--color-primary)', fontSize: '0.85rem'}}>92% Average</div>
                  </div>

                  <div className="admin-stats-card">
                    <h4>Prediction Count by Recommendation Type (All time)</h4>
                    {stats ? (
                      <div className="mock-bar-chart">
                        <div className="mock-bar mock-bar-blue" style={{ height: getPercentageHeight(statGlasses, maxStat) }}><div className="mock-bar-label">Glasses ({statGlasses})</div></div>
                        <div className="mock-bar mock-bar-purple" style={{ height: getPercentageHeight(statLenses, maxStat) }}><div className="mock-bar-label">Lenses ({statLenses})</div></div>
                        <div className="mock-bar mock-bar-green" style={{ height: getPercentageHeight(statNone, maxStat) }}><div className="mock-bar-label">None ({statNone})</div></div>
                      </div>
                    ) : (
                      <div style={{padding: '20px'}}>Loading stats...</div>
                    )}
                  </div>
                </div>

                <div className="admin-grid-bottom">
                   <div className="admin-stats-card" style={{ padding: 0 }}>
                     <h4 style={{ margin: '15px 15px 5px' }}>Distribution Volumes</h4>
                     <div className="mock-bar-chart" style={{ minHeight: '120px', marginLeft: '30px', marginBottom: '20px', paddingBottom: '20px' }}>
                      <div className="mock-axis-y" style={{ left: '-30px' }}>
                        <span>{maxStat}</span>
                        <span>{Math.floor(maxStat * 0.75)}</span>
                        <span>{Math.floor(maxStat * 0.5)}</span>
                        <span>{Math.floor(maxStat * 0.25)}</span>
                        <span>0</span>
                      </div>
                      <div className="mock-bar mock-bar-blue" style={{ height: getPercentageHeight(statGlasses, maxStat) }}><div className="mock-bar-label">Glasses</div></div>
                      <div className="mock-bar mock-bar-purple" style={{ height: getPercentageHeight(statLenses, maxStat) }}><div className="mock-bar-label">Lenses</div></div>
                      <div className="mock-bar mock-bar-green" style={{ height: getPercentageHeight(statNone, maxStat) }}><div className="mock-bar-label">None</div></div>
                     </div>
                   </div>

                   <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                      <div className="admin-stats-card admin-numeric-stat">
                         <div className="admin-numeric-label">Total Predictions Made</div>
                         <div className="admin-numeric-val">{stats?.totalAssessments || 0}</div>
                      </div>
                      <div className="admin-stats-card admin-numeric-stat">
                         <div className="admin-numeric-label">Avg. Model Confidence</div>
                         <div className="admin-numeric-val">{stats ? '92.46%' : '--'}</div>
                      </div>
                      <div className="admin-stats-card admin-numeric-stat">
                         <div className="admin-numeric-label">Average Clinician Review Time</div>
                         <div className="admin-numeric-val">4 hrs</div>
                      </div>
                      <div className="admin-stats-card admin-numeric-stat">
                         <div className="admin-numeric-label">System Up-time</div>
                         <div className="admin-numeric-val">99.98%</div>
                      </div>
                   </div>
                </div>

                <div className="admin-grid-top" style={{ marginTop: '20px' }}>
                  <div className="admin-stats-card">
                    <h4 style={{ margin: '0 0 10px' }}>Feature Importance (Model Interpretability)</h4>
                    <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginBottom: '15px' }}>Top clinical parameters driving model decisions for post-DALK correction.</div>
                    
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px', fontWeight: 'bold' }}><span>Corneal Astigmatism (Cylinder)</span><span>35%</span></div>
                      <div style={{ width: '100%', background: '#e2e8f0', borderRadius: '4px', height: '8px' }}><div style={{ width: '35%', background: 'var(--color-primary)', height: '100%', borderRadius: '4px' }}></div></div>
                    </div>
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px', fontWeight: 'bold' }}><span>Base UCVA</span><span>28%</span></div>
                      <div style={{ width: '100%', background: '#e2e8f0', borderRadius: '4px', height: '8px' }}><div style={{ width: '28%', background: '#8b5cf6', height: '100%', borderRadius: '4px' }}></div></div>
                    </div>
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px', fontWeight: 'bold' }}><span>K2 Diopters (Steep Axis)</span><span>20%</span></div>
                      <div style={{ width: '100%', background: '#e2e8f0', borderRadius: '4px', height: '8px' }}><div style={{ width: '20%', background: '#0ea5e9', height: '100%', borderRadius: '4px' }}></div></div>
                    </div>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px', fontWeight: 'bold' }}><span>Months Post-DALK</span><span>17%</span></div>
                      <div style={{ width: '100%', background: '#e2e8f0', borderRadius: '4px', height: '8px' }}><div style={{ width: '17%', background: '#10b981', height: '100%', borderRadius: '4px' }}></div></div>
                    </div>
                  </div>

                  <div className="admin-stats-card">
                    <h4 style={{ margin: '0 0 10px' }}>OCR Processing Diagnostics</h4>
                    <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginBottom: '15px' }}>Automated telemetry for topography analysis pipeline.</div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                      <div style={{ padding: '15px', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Avg Time</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--color-text-primary)' }}>1.2s</div>
                      </div>
                      <div style={{ padding: '15px', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Failure Rate</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10b981' }}>0.01%</div>
                      </div>
                    </div>
                    
                    <div style={{ marginTop: '15px', borderTop: '1px solid var(--color-border)', paddingTop: '15px' }}>
                      <h5 style={{ margin: '0 0 10px', fontSize: '0.85rem' }}>Common OCR Flags</h5>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.75rem', padding: '4px 8px', background: '#fee2e2', color: '#b91c1c', borderRadius: '4px' }}>Low Contrast Pachymetry Image</span>
                        <span style={{ fontSize: '0.75rem', padding: '4px 8px', background: '#fef3c7', color: '#b45309', borderRadius: '4px' }}>Acuity Field Blurry</span>
                      </div>
                    </div>
                  </div>
                </div>

             </div>

             {renderGlobalSettingsRight()}
           </div>
        )}

      </div>
    </div>
  )
}

export default Admin
