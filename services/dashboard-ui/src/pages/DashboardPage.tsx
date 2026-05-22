import { Activity, AlertTriangle, Camera, Shield } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { connectWebSocket, disconnectWebSocket, onWsEvent } from '../api/websocketClient'
import { apiFetch } from '../services/api'

interface DashboardPageProps {
  theme: 'light' | 'dark'
}

interface DashboardMetricSummary {
  active_alerts: number
  online_cameras: number
  resolved_cases: number
  face_data_records: number
}

interface DashboardOperationPoint {
  label: string
  value: number
}

interface DashboardActivityItem {
  id: string
  message: string
  timestamp: string
}

interface DashboardSummaryResponse {
  metrics: DashboardMetricSummary
  operations: DashboardOperationPoint[]
  recent_activity: DashboardActivityItem[]
}

const emptySummary: DashboardSummaryResponse = {
  metrics: {
    active_alerts: 0,
    online_cameras: 0,
    resolved_cases: 0,
    face_data_records: 0,
  },
  operations: [],
  recent_activity: [],
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function DashboardPage({ theme }: DashboardPageProps) {
  const isDark = theme === 'dark'
  const [summary, setSummary] = useState<DashboardSummaryResponse>(emptySummary)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const loadDashboardRef = useRef<() => Promise<void>>(null as any)

  const loadDashboard = async () => {
    try {
      const response = await apiFetch('/api/v1/dashboard/summary')

      if (!response.ok) {
        throw new Error('Unable to load dashboard summary right now')
      }

      const payload = (await response.json()) as DashboardSummaryResponse
      setSummary(payload)
      setErrorMessage('')
      setIsLoading(false)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to load dashboard summary right now')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDashboardRef.current = loadDashboard
  })

  useEffect(() => {
    void loadDashboard()

    const intervalId = window.setInterval(() => {
      void loadDashboardRef.current?.()
    }, 15000)

    connectWebSocket()

    const unsubscribers = [
      onWsEvent('NEW_DETECTION', () => void loadDashboardRef.current?.()),
      onWsEvent('ALERT_CREATED', () => void loadDashboardRef.current?.()),
      onWsEvent('ALERT_ACKNOWLEDGED', () => void loadDashboardRef.current?.()),
      onWsEvent('ALERT_RESOLVED', () => void loadDashboardRef.current?.()),
      onWsEvent('ALERT_FALSE_ALARM', () => void loadDashboardRef.current?.()),
    ]

    return () => {
      window.clearInterval(intervalId)
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      disconnectWebSocket()
    }
  }, [])

  const metrics = useMemo(
    () => [
      { label: 'Active Alerts', value: summary.metrics.active_alerts, icon: AlertTriangle, isAlertCounter: true },
      { label: 'Online Cameras', value: summary.metrics.online_cameras, icon: Camera },
      { label: 'Resolved Cases', value: summary.metrics.resolved_cases, icon: Activity },
      { label: 'Face Data Records', value: summary.metrics.face_data_records, icon: Shield },
    ],
    [summary.metrics],
  )

  const maxOperationValue = useMemo(
    () => Math.max(...summary.operations.map((point) => point.value), 1),
    [summary.operations],
  )

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon

          return (
            <article
              key={metric.label}
              className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] transition-colors ${
                isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
              }`}
            >
              <div className="mb-4 flex items-center justify-between">
                <span className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{metric.label}</span>
                <Icon className={`h-5 w-5 ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`} />
              </div>
              <div className="flex items-center gap-3">
                <div className={`text-3xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  {isLoading ? '--' : metric.value}
                </div>
                {metric.isAlertCounter && !isLoading && metric.value > 0 ? (
                  <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-rose-600 px-2 py-1 text-xs font-bold text-white">
                    {metric.value > 99 ? '99+' : metric.value}
                  </span>
                ) : null}
              </div>
            </article>
          )
        })}
      </section>

      {errorMessage ? (
        <div
          className={`rounded-2xl border px-4 py-3 text-sm ${
            isDark ? 'border-rose-500/30 bg-rose-500/10 text-rose-200' : 'border-rose-200 bg-rose-50 text-rose-700'
          }`}
        >
          {errorMessage}
        </div>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="mb-6 flex items-center justify-between">
            <h2 className={`text-xl font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Operations</h2>
            <span className={`text-sm font-medium ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`}>Live</span>
          </div>

          {summary.operations.length === 0 ? (
            <div
              className={`flex h-56 items-center justify-center rounded-2xl border border-dashed text-sm ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              No operational activity available yet.
            </div>
          ) : (
            <div className="flex h-56 items-end gap-3">
              {summary.operations.map((point) => (
                <div key={point.label} className="flex flex-1 flex-col items-center justify-end gap-2">
                  <div
                    className={`w-full rounded-t-2xl ${isDark ? 'bg-cyan-400/70' : 'bg-emerald-300'}`}
                    style={{
                      height: `${Math.max(12, (point.value / maxOperationValue) * 100)}%`,
                    }}
                    title={`${point.label}: ${point.value}`}
                  />
                  <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{point.label}</span>
                </div>
              ))}
            </div>
          )}
        </article>

        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <h2 className={`mb-5 text-xl font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Recent Activity</h2>
          <div className="space-y-4">
            {summary.recent_activity.length === 0 ? (
              <div
                className={`rounded-2xl border border-dashed px-4 py-6 text-sm ${
                  isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
                }`}
              >
                No recent activity available yet.
              </div>
            ) : (
              summary.recent_activity.map((item) => (
                <div
                  key={item.id}
                  className={`rounded-2xl px-4 py-3 text-sm ${
                    isDark ? 'bg-slate-800 text-slate-200' : 'bg-slate-50 text-slate-700'
                  }`}
                >
                  <p className="font-medium">{item.message}</p>
                  <p className={`mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {formatDateTime(item.timestamp)}
                  </p>
                </div>
              ))
            )}
          </div>
        </article>
      </section>
    </div>
  )
}
