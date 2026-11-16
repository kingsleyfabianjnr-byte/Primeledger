import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import SetupAccountPage from './pages/SetupAccountPage'
import DashboardPage from './pages/DashboardPage'
import ExceptionQueuePage from './pages/ExceptionQueuePage'
import AuditTrailPage from './pages/AuditTrailPage'
import ImportPage from './pages/ImportPage'
import UsersPage from './pages/UsersPage'
import ProfilePage from './pages/ProfilePage'
import ContractsPage from './pages/ContractsPage'
import AppLayout from './components/AppLayout'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/setup-account" element={<SetupAccountPage />} />

          {/* Protected app routes */}
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/app/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="exceptions" element={<ExceptionQueuePage />} />
            <Route path="import" element={<ImportPage />} />
            <Route path="audit" element={<AuditTrailPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="contracts" element={<ContractsPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
