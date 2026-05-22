import { type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import ProtectedRoute from '../components/auth/ProtectedRoute'
import DashboardLayout from '../components/layout/DashboardLayout'
import Footer from '../components/layout/Footer'
import Navbar from '../components/layout/Navbar'
import { useAuth } from '../context/AuthContext'
import AnalyticsPage from '../pages/AnalyticsPage'
import AlertsPage from '../pages/AlertsPage'
import CamerasPage from '../pages/CamerasPage'
import DashboardPage from '../pages/DashboardPage'
import FaceDataPage from '../pages/FaceDataPage'
import LandingPage from '../pages/LandingPage'
import LoginPage from '../pages/LoginPage'
import ManageUsersPage from '../pages/ManageUsersPage'
import ReportsPage from '../pages/ReportsPage'
import SettingsPage from '../pages/SettingsPage'
import TrackPage from '../pages/TrackPage'
import { getDefaultRouteForRole } from './routeConfig'

interface AppRoutesProps {
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

function PublicShell({
  theme,
  onToggleTheme,
  children,
}: {
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  children: ReactNode
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, isAuthResolved, user } = useAuth()

  const navItems = [{ label: 'Sign Up', href: '/login' }]

  const handleNavClick = (href: string) => {
    navigate(href)
  }

  if (!isAuthResolved) {
    return null
  }

  if (isAuthenticated && user && location.pathname === '/login') {
    return <Navigate to={getDefaultRouteForRole(user.role)} replace />
  }

  return (
    <div className={`flex min-h-screen flex-col ${theme === 'dark' ? 'bg-slate-950' : 'bg-[#f8faf9]'}`}>
      <Navbar
        logoText="AIFLOW"
        navItems={navItems}
        theme={theme}
        onLogoClick={() => navigate('/')}
        onNavClick={handleNavClick}
        onToggleTheme={onToggleTheme}
      />
      {children}
      <Footer companyName="AIFLOW" theme={theme} />
    </div>
  )
}

export default function AppRoutes({ theme, onToggleTheme }: AppRoutesProps) {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <PublicShell theme={theme} onToggleTheme={onToggleTheme}>
            <LandingPage />
          </PublicShell>
        }
      />
      <Route
        path="/login"
        element={
          <PublicShell theme={theme} onToggleTheme={onToggleTheme}>
            <LoginPage theme={theme} />
          </PublicShell>
        }
      />

      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout theme={theme} onToggleTheme={onToggleTheme} />}>
          <Route path="/dashboard" element={<DashboardPage theme={theme} />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={['admin', 'security_officer']} />}>
        <Route element={<DashboardLayout theme={theme} onToggleTheme={onToggleTheme} />}>
          <Route path="/alerts" element={<AlertsPage theme={theme} />} />
          <Route path="/track" element={<TrackPage theme={theme} />} />
          <Route path="/cameras" element={<CamerasPage theme={theme} />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
        <Route element={<DashboardLayout theme={theme} onToggleTheme={onToggleTheme} />}>
          <Route path="/manage-users" element={<ManageUsersPage theme={theme} />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={['admin', 'security_officer']} />}>
        <Route element={<DashboardLayout theme={theme} onToggleTheme={onToggleTheme} />}>
          <Route path="/analytics" element={<AnalyticsPage theme={theme} />} />
          <Route path="/reports" element={<ReportsPage theme={theme} />} />
          <Route path="/face-data" element={<FaceDataPage theme={theme} />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={['admin', 'security_officer']} />}>
        <Route element={<DashboardLayout theme={theme} onToggleTheme={onToggleTheme} />}>
          <Route path="/settings" element={<SettingsPage theme={theme} />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
