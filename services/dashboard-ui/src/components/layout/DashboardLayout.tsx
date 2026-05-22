import { useCallback, useEffect, useRef, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { AlertTriangle, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import Footer from './Footer'
import Navbar from './Navbar'
import DashboardSidebar from './DashboardSidebar'
import { requestShutdownToken, initiateShutdown } from '../../services/system'
import { apiFetch } from '../../services/api'
import { connectWebSocket, disconnectWebSocket, onWsEvent } from '../../api/websocketClient'

interface DashboardLayoutProps {
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

export default function DashboardLayout({ theme, onToggleTheme }: DashboardLayoutProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isShuttingDown, setIsShuttingDown] = useState(false)
  const [activeAlertCount, setActiveAlertCount] = useState(0)
  const [popupAlert, setPopupAlert] = useState<any | null>(null)
  const popupTimerRef = useRef<number | null>(null)
  
  const isDark = theme === 'dark'
  const handleCloseSidebar = useCallback(() => setIsSidebarOpen(false), [])
  const handleOpenSidebar = useCallback(() => setIsSidebarOpen(true), [])
  const handleToggleSidebarCollapsed = useCallback(
    () => setIsSidebarCollapsed((current) => !current),
    [],
  )

  const loadActiveAlertCount = useCallback(async () => {
    try {
      const response = await apiFetch('/api/v1/alerts/active-count')
      if (!response.ok) {
        return
      }

      const payload = (await response.json()) as { active_count: number }
      setActiveAlertCount(payload.active_count)
    } catch {
      // Keep the shell usable if the count endpoint is briefly unavailable.
    }
  }, [])

  useEffect(() => {
    void loadActiveAlertCount()
    connectWebSocket()

    const showNewAlertPopup = (message: any) => {
      const alert = message.alert
      if (!alert?.alert_id) {
        return
      }

      setPopupAlert({
        id: alert.alert_id,
        name: message.data?.name || alert.description || 'New alert',
        cameraId: alert.camera_id || message.data?.camera_id,
        severity: alert.severity,
        confidence: message.data?.confidence,
      })

      if (popupTimerRef.current) {
        window.clearTimeout(popupTimerRef.current)
      }
      popupTimerRef.current = window.setTimeout(() => setPopupAlert(null), 9000)
    }

    const updateCount = (message: any) => {
      const nextCount = message.data?.active_count
      if (typeof nextCount === 'number') {
        setActiveAlertCount(nextCount)
      } else {
        void loadActiveAlertCount()
      }
    }

    const unsubscribers = [
      onWsEvent('ALERT_CREATED', (message: any) => {
        updateCount(message)
        showNewAlertPopup(message)
      }),
      onWsEvent('NEW_DETECTION', updateCount),
      onWsEvent('ALERT_ACKNOWLEDGED', updateCount),
      onWsEvent('ALERT_RESOLVED', updateCount),
      onWsEvent('ALERT_FALSE_ALARM', updateCount),
    ]

    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      disconnectWebSocket()
      if (popupTimerRef.current) {
        window.clearTimeout(popupTimerRef.current)
      }
    }
  }, [loadActiveAlertCount])

  if (!user) {
    return null
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const handleShutdown = async () => {
    if (user.role !== 'admin') return

    const confirmed = window.confirm(
      "CRITICAL ACTION: This will shut down the entire AI Surveillance System and all microservices immediately.\n\nAre you absolutely sure you want to proceed?"
    )

    if (!confirmed) return

    try {
      setIsShuttingDown(true)
      const { token } = await requestShutdownToken()
      await initiateShutdown(token)
      
      alert("Shutdown command accepted. The system will halt in a few seconds. The UI will now disconnect.")
      
      // Clear session and redirect to landing
      logout()
      navigate('/', { replace: true })
    } catch (err: any) {
      setIsShuttingDown(false)
      alert("Shutdown failed: " + err.message)
    }
  }

  return (
    <div className={`relative flex min-h-screen flex-col transition-colors ${isDark ? 'bg-slate-950' : 'bg-[#f8faf9]'}`}>
      {isShuttingDown && (
        <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-slate-950/90 text-white backdrop-blur-sm">
          <div className="mb-4 h-16 w-16 animate-spin rounded-full border-4 border-red-500 border-t-transparent"></div>
          <h2 className="text-2xl font-bold text-red-500">System Shutting Down...</h2>
          <p className="mt-2 text-slate-400">Stopping all microservices gracefully. Please wait.</p>
        </div>
      )}
      <Navbar
        logoText="AIFLOW"
        navItems={[]}
        theme={theme}
        onLogoClick={() => navigate('/')}
        onToggleTheme={onToggleTheme}
        userName={user.name}
        onLogout={handleLogout}
        onShutdown={user.role === 'admin' ? handleShutdown : undefined}
      />

      <div className="mx-auto flex w-full max-w-[1600px] flex-1 gap-4 px-3 py-4 sm:gap-6 sm:px-5 sm:py-6 lg:px-8">
        <DashboardSidebar
          role={user.role}
          theme={theme}
          isOpen={isSidebarOpen}
          isCollapsed={isSidebarCollapsed}
          onClose={handleCloseSidebar}
          onOpen={handleOpenSidebar}
          onToggleCollapsed={handleToggleSidebarCollapsed}
          activeAlertCount={activeAlertCount}
        />

        <main className="min-w-0 flex-1 pt-16 transition-[width,margin] duration-300 ease-out sm:pt-20 lg:pt-0">
          <div className={`w-full transition-[max-width] duration-300 ease-out ${isSidebarCollapsed ? 'max-w-none' : 'max-w-6xl'}`}>
            <Outlet />
          </div>
        </main>
      </div>

      {popupAlert ? (
        <div className="fixed right-4 top-24 z-[80] w-[calc(100vw-2rem)] max-w-sm">
          <button
            type="button"
            onClick={() => {
              setPopupAlert(null)
              navigate(`/alerts?alertId=${popupAlert.id}`)
            }}
            className={`w-full rounded-lg border p-4 text-left shadow-2xl transition-transform hover:-translate-y-0.5 ${
              isDark ? 'border-rose-400/40 bg-slate-900 text-slate-100' : 'border-rose-200 bg-white text-slate-900'
            }`}
          >
            <div className="flex items-start gap-3">
              <span className={`rounded-full p-2 ${isDark ? 'bg-rose-500/15 text-rose-300' : 'bg-rose-50 text-rose-700'}`}>
                <AlertTriangle className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold">New Alert #{popupAlert.id}</span>
                <span className={`mt-1 block truncate text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                  {popupAlert.name} on {popupAlert.cameraId || 'unknown camera'}
                </span>
                <span className={`mt-2 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                  isDark ? 'bg-rose-500/15 text-rose-200' : 'bg-rose-100 text-rose-700'
                }`}>
                  {popupAlert.severity || 'Active'}
                </span>
              </span>
              <span
                role="button"
                tabIndex={0}
                onClick={(event) => {
                  event.stopPropagation()
                  setPopupAlert(null)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.stopPropagation()
                    setPopupAlert(null)
                  }
                }}
                className={`rounded-full p-1 ${isDark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100'}`}
              >
                <X className="h-4 w-4" />
              </span>
            </div>
          </button>
        </div>
      ) : null}

      <Footer companyName="AIFLOW" theme={theme} />
    </div>
  )
}
