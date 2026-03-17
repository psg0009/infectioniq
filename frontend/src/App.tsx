import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import ProtectedRoute from './components/auth/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import ToastContainer from './components/Toast'
import { useAuthStore } from './stores/authStore'
import DashboardPage from './pages/DashboardPage'
import CasePage from './pages/CasePage'
import AnalyticsPage from './pages/AnalyticsPage'
import LoginPage from './pages/LoginPage'
import SSOCallbackPage from './pages/SSOCallbackPage'
import ZoneCalibrationPage from './pages/ZoneCalibrationPage'
import StaffPage from './pages/StaffPage'
import DispensersPage from './pages/DispensersPage'
import ROICalculatorPage from './pages/ROICalculatorPage'
import GestureCalibrationPage from './pages/GestureCalibrationPage'
import VideoUploadPage from './pages/VideoUploadPage'
import LiveCameraPage from './pages/LiveCameraPage'

function App() {
  const initSession = useAuthStore((s) => s.initSession)
  useEffect(() => { initSession() }, [initSession])

  return (
    <ErrorBoundary>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/sso-callback" element={<SSOCallbackPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/case/:caseId" element={<CasePage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                  <Route path="/calibration" element={<ZoneCalibrationPage />} />
                  <Route path="/staff" element={<StaffPage />} />
                  <Route path="/dispensers" element={<DispensersPage />} />
                  <Route path="/roi" element={<ROICalculatorPage />} />
                  <Route path="/gesture-calibration" element={<GestureCalibrationPage />} />
                  <Route path="/video" element={<VideoUploadPage />} />
                  <Route path="/camera" element={<LiveCameraPage />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </ErrorBoundary>
  )
}

export default App
