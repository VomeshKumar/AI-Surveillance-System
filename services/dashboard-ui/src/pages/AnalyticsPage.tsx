import { useEffect, useMemo, useRef, useState } from 'react'
import { connectWebSocket, disconnectWebSocket, onWsEvent } from '../api/websocketClient'
import { apiFetch } from '../services/api'

interface AnalyticsPageProps {
  theme: 'light' | 'dark'
}

interface AnalyticsMetricItem {
  label: string
  value: string
}

interface AnalyticsTrendPoint {
  label: string
  value: number
}

interface AnalyticsSummaryResponse {
  metrics: AnalyticsMetricItem[]
  trend: AnalyticsTrendPoint[]
}

const emptySummary: AnalyticsSummaryResponse = {
  metrics: [],
  trend: [],
}

export default function AnalyticsPage({ theme }: AnalyticsPageProps) {
  const isDark = theme === 'dark'
  const [summary, setSummary] = useState<AnalyticsSummaryResponse>(emptySummary)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const loadAnalyticsRef = useRef<() => Promise<void>>(null as any)

  const loadAnalytics = async () => {
    try {
      const response = await apiFetch('/api/v1/dashboard/analytics')

      if (!response.ok) {
        throw new Error('Unable to load analytics right now')
      }

      const payload = (await response.json()) as AnalyticsSummaryResponse
      setSummary(payload)
      setErrorMessage('')
      setIsLoading(false)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to load analytics right now')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAnalyticsRef.current = loadAnalytics
  })

  useEffect(() => {
    void loadAnalytics()

    const intervalId = window.setInterval(() => {
      void loadAnalyticsRef.current?.()
    }, 15000)

    connectWebSocket()

    const unsubscribers = [
      onWsEvent('NEW_DETECTION', () => void loadAnalyticsRef.current?.()),
      onWsEvent('ALERT_ACKNOWLEDGED', () => void loadAnalyticsRef.current?.()),
      onWsEvent('ALERT_RESOLVED', () => void loadAnalyticsRef.current?.()),
      onWsEvent('ALERT_FALSE_ALARM', () => void loadAnalyticsRef.current?.()),
    ]

    return () => {
      window.clearInterval(intervalId)
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      disconnectWebSocket()
    }
  }, [])

  const maxTrendValue = useMemo(
    () => Math.max(...summary.trend.map((point) => point.value), 1),
    [summary.trend],
  )

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        {(summary.metrics.length ? summary.metrics : [{ label: 'Loading', value: '--' }]).map((metric) => (
          <article
            key={metric.label}
            className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
              isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
            }`}
          >
            <div className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{metric.label}</div>
            <div className={`mt-3 text-3xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
              {isLoading ? '--' : metric.value}
            </div>
          </article>
        ))}
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

      <section
        className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
          isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
        }`}
      >
        <h1 className={`mb-6 text-2xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Analysis</h1>

        {summary.trend.length === 0 ? (
          <div
            className={`flex h-64 items-center justify-center rounded-2xl border border-dashed text-sm ${
              isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
            }`}
          >
            No analytics trend data available yet.
          </div>
        ) : (
          <div className="flex h-64 items-end gap-3">
            {summary.trend.map((point) => (
              <div key={point.label} className="flex flex-1 flex-col items-center justify-end gap-2">
                <div
                  className={`w-full rounded-t-2xl ${isDark ? 'bg-cyan-400/75' : 'bg-emerald-300'}`}
                  style={{ height: `${Math.max(12, (point.value / maxTrendValue) * 100)}%` }}
                  title={`${point.label}: ${point.value}`}
                />
                <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{point.label}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
