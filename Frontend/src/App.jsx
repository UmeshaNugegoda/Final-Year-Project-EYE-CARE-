import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login/Login'
import Prediction from './pages/Prediction/Prediction'
import Admin from './pages/Admin/Admin'
import Dashboard from './pages/Dashboard/Dashboard'
import PreviousPatients from './pages/PreviousPatients/PreviousPatients'
import PatientHistory from './pages/PatientHistory/PatientHistory'
import Profile from './pages/Profile/Profile'

function ProtectedRoute({ children, auth, requireAdmin = false }) {
  if (!auth?.token || !auth?.user) {
    return <Navigate to="/login" replace />
  }
  if (requireAdmin && auth.user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }
  return children
}

function App() {
  const [auth, setAuth] = useState(() => {
    try {
      const stored = localStorage.getItem('auth')
      return stored ? JSON.parse(stored) : { token: null, user: null }
    } catch {
      return { token: null, user: null }
    }
  })

  useEffect(() => {
    try {
      if (auth && auth.token) {
        localStorage.setItem('auth', JSON.stringify(auth))
      } else {
        localStorage.removeItem('auth')
      }
    } catch {
      // ignore storage errors in demo
    }
  }, [auth])

  const handleLogout = () => {
    setAuth({ token: null, user: null })
  }

  return (
    <Routes>
      <Route path="/login" element={<Login setAuth={setAuth} />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute auth={auth}>
            <Dashboard auth={auth} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/prediction"
        element={
          <ProtectedRoute auth={auth}>
            <Prediction auth={auth} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute auth={auth} requireAdmin>
            <Admin auth={auth} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/patients"
        element={
          <ProtectedRoute auth={auth}>
            <PreviousPatients auth={auth} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute auth={auth}>
            <PatientHistory auth={auth} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute auth={auth}>
            <Profile auth={auth} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default App

