import { useEffect } from 'react'
import { PanelLeftClose, PanelLeftOpen, X } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import { type UserRole } from '../../context/AuthContext'
import { getAccessibleDashboardRoutes } from '../../routes/routeConfig'

interface DashboardSidebarProps {
  role: UserRole
  theme: 'light' | 'dark'
  isOpen: boolean
  isCollapsed: boolean
  onClose: () => void
  onOpen: () => void
  onToggleCollapsed: () => void
  activeAlertCount?: number
}

export default function DashboardSidebar({
  role,
  theme,
  isOpen,
  isCollapsed,
  onClose,
  onOpen,
  onToggleCollapsed,
  activeAlertCount = 0,
}: DashboardSidebarProps) {
  const isDark = theme === 'dark'
  const routes = getAccessibleDashboardRoutes(role)
  const location = useLocation()

  useEffect(() => {
    onClose()
  }, [location.pathname, onClose])

  useEffect(() => {
    if (!isOpen) {
      document.body.style.overflow = ''
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleEscape)

    return () => {
      window.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, onClose])

  return (
    <>
      <button
        type="button"
        onClick={onOpen}
        className={`fixed left-3 top-[94px] z-30 rounded-full border p-2 shadow-[0_8px_24px_rgba(15,23,42,0.18)] transition-colors sm:left-5 sm:top-[102px] lg:hidden ${
          isDark
            ? 'border-slate-700 bg-slate-900 text-slate-100'
            : 'border-slate-200 bg-white text-slate-900'
        }`}
        aria-label="Open sidebar"
      >
        <PanelLeftOpen className="h-5 w-5" />
      </button>

      {isOpen ? (
        <button
          type="button"
          aria-label="Close sidebar overlay"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-full max-w-[20rem] -translate-x-full px-3 pb-4 pt-[84px] transition-transform duration-300 ease-out sm:max-w-[22rem] sm:px-5 sm:pb-6 sm:pt-[92px] lg:sticky lg:top-6 lg:z-auto lg:block lg:h-[calc(100vh-8rem)] lg:max-w-none lg:translate-x-0 lg:self-start lg:px-0 lg:pb-0 lg:pt-0 ${
          isCollapsed ? 'lg:w-[5.5rem]' : 'lg:w-[19rem]'
        } ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div
          className={`flex h-full flex-col overflow-hidden rounded-lg border shadow-[0_3px_10px_rgba(15,23,42,0.5)] transition-colors ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className={`hidden items-center justify-between border-b px-4 py-4 lg:flex ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
            <div className={`${isCollapsed ? 'hidden' : 'block'}`}>
              <span className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                Navigation
              </span>
              <p className={`mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Dashboard shortcuts</p>
            </div>
            <button
              type="button"
              onClick={onToggleCollapsed}
              className={`rounded-full p-2 transition-colors ${isDark ? 'text-slate-100 hover:bg-slate-800' : 'text-slate-900 hover:bg-slate-100'} ${
                isCollapsed ? 'mx-auto' : ''
              }`}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
          </div>

          <div className={`flex items-center justify-between border-b px-5 py-5 lg:hidden ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
            <div>
              <span className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                Navigation
              </span>
              <p className={`mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Move through the dashboard</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className={`rounded-full p-2 transition-colors ${
                isDark ? 'text-slate-100 hover:bg-slate-800' : 'text-slate-900 hover:bg-slate-100'
              }`}
              aria-label="Close sidebar"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <nav className={`flex flex-1 flex-col gap-2 overflow-y-auto px-4 py-4 lg:py-6 ${isCollapsed ? 'lg:px-3' : 'lg:px-5'}`}>
            {routes.map((route) => {
              const Icon = route.icon
              const showAlertBadge = route.path === '/alerts' && activeAlertCount > 0

              return (
                <NavLink
                  key={route.path}
                  to={route.path}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `relative flex items-center rounded-2xl px-4 py-3 text-sm font-semibold transition-all ${
                      isCollapsed ? 'justify-center gap-0 lg:px-3' : 'gap-3'
                    } ${
                      isActive
                        ? isDark
                          ? 'bg-slate-800 text-cyan-300 ring-1 ring-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
                          : 'bg-slate-50 text-emerald-900 ring-1 ring-slate-200'
                        : isDark
                          ? 'text-slate-300 hover:bg-slate-800 hover:text-slate-100'
                          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                  aria-label={route.label}
                  title={route.label}
                >
                  <Icon className="h-5 w-5" />
                  <span className={isCollapsed ? 'hidden' : 'inline'}>{route.label}</span>
                  {showAlertBadge ? (
                    <span
                      className={`ml-auto inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5 text-[11px] font-bold ${
                        isDark ? 'bg-rose-500 text-white' : 'bg-rose-600 text-white'
                      } ${isCollapsed ? 'lg:absolute lg:right-2 lg:top-2 lg:ml-0' : ''}`}
                    >
                      {activeAlertCount > 99 ? '99+' : activeAlertCount}
                    </span>
                  ) : null}
                </NavLink>
              )
            })}
          </nav>
        </div>
      </aside>
    </>
  )
}
