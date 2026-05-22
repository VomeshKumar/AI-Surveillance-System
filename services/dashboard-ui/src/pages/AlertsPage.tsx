import { AlertTriangle, CheckCheck, Clock3, Expand, MapPin, RefreshCw, Shrink, Siren, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../services/api'
import { connectWebSocket, disconnectWebSocket, onWsEvent } from '../api/websocketClient'
import { fetchCameras, type Camera } from '../api/cameras'

interface AlertsPageProps {
  theme: 'light' | 'dark'
}

interface AlertItem {
  id: number
  alert_type: string
  camera_id: string
  person_id: number | null
  person_name: string | null
  severity: string | null
  threat_level: string | null
  category: string | null
  description: string | null
  status: string
  resolved_by: string | null
  notes: string | null
  suspect_image_url: string | null
  evidence_image_url: string | null
  timestamp: string
}

interface ApiErrorPayload {
  detail?: string
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatLabel(value: string | null | undefined) {
  if (!value) {
    return 'Not available'
  }

  if (value === 'pending' || value === 'active') {
    return 'Active'
  }

  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function getStatusTone(status: string, isDark: boolean) {
  if (status === 'resolved') {
    return isDark ? 'bg-emerald-500/15 text-emerald-300' : 'bg-emerald-100 text-emerald-700'
  }

  if (status === 'acknowledged') {
    return isDark ? 'bg-amber-500/15 text-amber-200' : 'bg-amber-100 text-amber-700'
  }

  if (status === 'false_alarm') {
    return isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-700'
  }

  return isDark ? 'bg-rose-500/15 text-rose-300' : 'bg-rose-100 text-rose-700'
}

function getSeverityTone(severity: string | null, isDark: boolean) {
  if (severity === 'high' || severity === 'critical') {
    return isDark ? 'bg-rose-500/15 text-rose-300' : 'bg-rose-100 text-rose-700'
  }

  if (severity === 'medium') {
    return isDark ? 'bg-amber-500/15 text-amber-200' : 'bg-amber-100 text-amber-700'
  }

  return isDark ? 'bg-cyan-500/15 text-cyan-300' : 'bg-cyan-100 text-cyan-700'
}

async function parseApiError(response: Response) {
  try {
    const payload = (await response.json()) as ApiErrorPayload
    return payload.detail || 'Unable to complete the alert update right now'
  } catch {
    return 'Unable to complete the alert update right now'
  }
}

export default function AlertsPage({ theme }: AlertsPageProps) {
  const isDark = theme === 'dark'
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [counts, setCounts] = useState({ pending: 0, acknowledged: 0, resolved: 0, false_alarm: 0 })
  const [cameras, setCameras] = useState<Camera[]>([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [cameraFilter, setCameraFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [alertImageUrls, setAlertImageUrls] = useState<Record<string, string>>({})
  const [draftNotes, setDraftNotes] = useState<Record<number, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [activeActionId, setActiveActionId] = useState<number | null>(null)
  const [isLive, setIsLive] = useState(false)
  const [activeAlertId, setActiveAlertId] = useState<number | null>(null)
  const loadAlertsRef = useRef<() => Promise<void>>(null as any)
  const loadCountsRef = useRef<() => Promise<void>>(null as any)
  const alertRefs = useRef<Record<number, HTMLElement | null>>({})
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const filteredAlerts = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase()

    return alerts.filter((alert) => {
      // status matching is now handled by the API, so we only filter locally
      // if the user types in the search box.
      const matchesQuery =
        !normalizedQuery ||
        [
          String(alert.id),
          alert.person_name ?? '',
          alert.camera_id,
          alert.alert_type,
          alert.description ?? '',
          alert.category ?? '',
          alert.severity ?? '',
        ].some((value) => value.toLowerCase().includes(normalizedQuery))

      return matchesQuery
    })
  }, [alerts, searchQuery])

  const cameraNameById = useMemo(
    () =>
      Object.fromEntries(
        cameras.map((camera) => [
          camera.camera_id,
          camera.location ? `${camera.camera_name} (${camera.location})` : camera.camera_name,
        ]),
      ),
    [cameras],
  )

  const cameraOptions = useMemo(() => {
    const optionMap = new Map<string, string>()

    cameras.forEach((camera) => {
      optionMap.set(
        camera.camera_id,
        camera.location ? `${camera.camera_name} (${camera.location})` : camera.camera_name,
      )
    })

    alerts.forEach((alert) => {
      if (!optionMap.has(alert.camera_id)) {
        optionMap.set(alert.camera_id, alert.camera_id)
      }
    })

    return Array.from(optionMap.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((left, right) => left.label.localeCompare(right.label))
  }, [alerts, cameras])

  const activeAlert = useMemo(
    () => alerts.find((alert) => alert.id === activeAlertId) ?? null,
    [activeAlertId, alerts],
  )

  const loadAlerts = async () => {
    setIsLoading(true)
    setErrorMessage('')

    try {
      const params = new URLSearchParams()
      params.append('limit', '100')
      if (statusFilter !== 'all') {
        params.append('status', statusFilter)
      }
      if (cameraFilter !== 'all') {
        params.append('camera_id', cameraFilter)
      }

      const response = await apiFetch(`/api/v1/alerts?${params.toString()}`)

      if (!response.ok) {
        setErrorMessage(await parseApiError(response))
        setIsLoading(false)
        return
      }

      const payload = (await response.json()) as AlertItem[]
      setAlerts(payload)
      setDraftNotes(
        Object.fromEntries(payload.map((alert) => [alert.id, alert.notes ?? ''])),
      )
      setIsLoading(false)
    } catch {
      setErrorMessage('Unable to load alerts right now')
      setIsLoading(false)
    }
  }

  const loadCounts = async () => {
    try {
      const response = await apiFetch('/api/v1/alerts/stats')
      if (response.ok) {
        setCounts(await response.json())
      }
    } catch {
      // Fail silently
    }
  }

  const loadCameras = async () => {
    try {
      const payload = await fetchCameras()
      setCameras(payload)
    } catch {
      // Keep alerts usable even if camera metadata fails to load.
    }
  }

  useEffect(() => {
    void loadAlerts()
    void loadCounts()
  }, [statusFilter, cameraFilter])

  useEffect(() => {
    void loadCameras()
  }, [])

  useEffect(() => {
    const targetAlertId = Number(searchParams.get('alertId'))
    if (!targetAlertId || isLoading) {
      return
    }

    const target = alertRefs.current[targetAlertId]
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setActiveAlertId(targetAlertId)
    }
  }, [isLoading, searchParams, filteredAlerts])

  useEffect(() => {
    if (!activeAlert) {
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveAlertId(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeAlert])

  useEffect(() => {
    const imageUrlsToCleanup: string[] = []
    let isCancelled = false

    const loadAlertImages = async () => {
      const imageTargets = alerts.flatMap((alert) => {
        const targets: Array<{ key: string; url: string }> = []

        if (alert.suspect_image_url) {
          targets.push({ key: `suspect-${alert.id}`, url: alert.suspect_image_url })
        }

        if (alert.evidence_image_url) {
          targets.push({ key: `evidence-${alert.id}`, url: alert.evidence_image_url })
        }

        return targets
      })

      if (!imageTargets.length) {
        setAlertImageUrls({})
        return
      }

      const imageEntries = await Promise.all(
        imageTargets.map(async (target) => {
          try {
            const response = await apiFetch(target.url)
            if (!response.ok) {
              return [target.key, ''] as const
            }

            const blob = await response.blob()
            const objectUrl = URL.createObjectURL(blob)
            imageUrlsToCleanup.push(objectUrl)
            return [target.key, objectUrl] as const
          } catch {
            return [target.key, ''] as const
          }
        }),
      )

      if (!isCancelled) {
        setAlertImageUrls(
          Object.fromEntries(imageEntries.filter(([, imageUrl]) => Boolean(imageUrl))),
        )
      }
    }

    void loadAlertImages()

    return () => {
      isCancelled = true
      imageUrlsToCleanup.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [alerts])

  // ── WebSocket: Real-time alert updates ─────────────────────────────────────
  // Keep the ref in sync so the WS handler always calls the latest version
  useEffect(() => {
    loadAlertsRef.current = loadAlerts
    loadCountsRef.current = loadCounts
  })

  useEffect(() => {
    connectWebSocket()
    setIsLive(true)

    const refreshData = () => {
      void loadAlertsRef.current?.()
      void loadCountsRef.current?.()
    }

    const unsub = onWsEvent('NEW_DETECTION', refreshData)
    const unsubAlertCreated = onWsEvent('ALERT_CREATED', refreshData)
    const unsubAlertResolved = onWsEvent('ALERT_RESOLVED', refreshData)
    const unsubAlertAcknowledged = onWsEvent('ALERT_ACKNOWLEDGED', refreshData)

    return () => {
      unsub()
      unsubAlertCreated()
      unsubAlertResolved()
      unsubAlertAcknowledged()
      disconnectWebSocket()
      setIsLive(false)
    }
  }, [])

  const handleAlertAction = async (alertId: number, action: 'acknowledge' | 'resolve' | 'false-alarm', status: string) => {
    setActiveActionId(alertId)
    setErrorMessage('')

    try {
      const response = await apiFetch(`/api/v1/alerts/${alertId}/${action}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          status,
          notes: draftNotes[alertId]?.trim() || null,
        }),
      })

      if (!response.ok) {
        setErrorMessage(await parseApiError(response))
        setActiveActionId(null)
        return
      }

      const updatedAlert = (await response.json()) as AlertItem
      setAlerts((current) => {
        // We no longer filter out immediately so the user can see the status change.
        // On next re-fetch (e.g. filter change), it will be gone from the active list.
        return current.map((alert) => (alert.id === alertId ? updatedAlert : alert))
      })
      void loadCounts()
      setDraftNotes((current) => ({
        ...current,
        [alertId]: updatedAlert.notes ?? current[alertId] ?? '',
      }))
      setActiveActionId(null)
    } catch {
      setErrorMessage('Unable to update alert right now')
      setActiveActionId(null)
    }
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: 'Open Alerts', value: counts.pending, accent: 'Immediate response queue', icon: Siren },
          { label: 'Acknowledged', value: counts.acknowledged, accent: 'Assigned for investigation', icon: Clock3 },
          { label: 'Resolved', value: counts.resolved, accent: 'Closed by operators', icon: CheckCheck },
          { label: 'False Alarms', value: counts.false_alarm, accent: 'Reviewed and dismissed', icon: XCircle },
        ].map((metric) => {
          const Icon = metric.icon

          return (
            <article
              key={metric.label}
              className={`rounded-lg border p-5 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
                isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{metric.label}</p>
                  <p className={`mt-3 text-3xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{metric.value}</p>
                  <p className={`mt-2 text-sm ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`}>{metric.accent}</p>
                </div>
                <div className={`rounded-2xl p-3 ${isDark ? 'bg-slate-800 text-cyan-300' : 'bg-slate-50 text-emerald-700'}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
            </article>
          )
        })}
      </section>

      <section
        className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
          isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
        }`}
      >
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <div className={`rounded-2xl p-3 ${isDark ? 'bg-cyan-400/10 text-cyan-300' : 'bg-emerald-50 text-emerald-700'}`}>
              <AlertTriangle className="h-6 w-6" />
            </div>
          <div>
              <div className="flex items-center gap-3">
                <h1 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Alerts</h1>
                {isLive && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-2.5 py-1 text-xs font-semibold text-emerald-400">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400"></span>
                    LIVE
                  </span>
                )}
              </div>
              <p className={`mt-2 max-w-2xl text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Review live incidents, track camera-triggered detections, and update each alert as acknowledged, resolved, or false alarm.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => void loadAlerts()}
            className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-2 text-sm font-semibold transition-colors ${
              isDark
                ? 'border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700'
                : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <RefreshCw className="h-4 w-4" />
            Refresh Queue
          </button>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1.5fr_0.8fr_0.8fr]">
          <input
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search by person, camera, alert type, description"
            className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
              isDark
                ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
            }`}
          />

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
              isDark ? 'border-slate-700 bg-slate-800 text-slate-100' : 'border-slate-200 bg-slate-50 text-slate-900'
            }`}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="false_alarm">False alarm</option>
          </select>

          <select
            value={cameraFilter}
            onChange={(event) => setCameraFilter(event.target.value)}
            className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
              isDark ? 'border-slate-700 bg-slate-800 text-slate-100' : 'border-slate-200 bg-slate-50 text-slate-900'
            }`}
          >
            <option value="all">All cameras</option>
            {cameraOptions.map((camera) => (
              <option key={camera.value} value={camera.value}>
                {camera.label}
              </option>
            ))}
          </select>
        </div>

        {errorMessage ? (
          <div
            className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${
              isDark ? 'border-rose-500/30 bg-rose-500/10 text-rose-200' : 'border-rose-200 bg-rose-50 text-rose-700'
            }`}
          >
            {errorMessage}
          </div>
        ) : null}

        <div className="mt-6 space-y-4">
          {isLoading ? (
            <div
              className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              Loading alerts...
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div
              className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              No alerts found for the current filters.
            </div>
          ) : (
            filteredAlerts.map((alert) => {
              const isPending = alert.status === 'pending'
              const isAcknowledged = alert.status === 'acknowledged'
              const isActionBusy = activeActionId === alert.id

              return (
                <article
                  key={alert.id}
                  ref={(element) => {
                    alertRefs.current[alert.id] = element
                  }}
                  className={`rounded-[1.5rem] border p-5 ${
                    activeAlertId === alert.id
                      ? isDark
                        ? 'border-cyan-300 bg-slate-800 ring-2 ring-cyan-300/40'
                        : 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-300'
                      : isDark
                        ? 'border-slate-700 bg-slate-800'
                        : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                    <div className="flex-1 space-y-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className={`text-lg font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                          {alert.person_name || 'Unknown Match'}
                        </h2>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${getStatusTone(alert.status, isDark)}`}>
                          {formatLabel(alert.status)}
                        </span>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${getSeverityTone(alert.severity, isDark)}`}>
                          {formatLabel(alert.severity)}
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            isDark ? 'bg-slate-700 text-slate-200' : 'bg-white text-slate-700 ring-1 ring-slate-200'
                          }`}
                        >
                          Alert #{alert.id}
                        </span>
                      </div>

                      <div className={`grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                        <p>
                          <span className="font-semibold">Camera:</span>{' '}
                          {cameraNameById[alert.camera_id] ?? alert.camera_id}
                        </p>
                        <p><span className="font-semibold">Type:</span> {formatLabel(alert.alert_type)}</p>
                        <p><span className="font-semibold">Category:</span> {formatLabel(alert.category)}</p>
                        <p><span className="font-semibold">Threat:</span> {formatLabel(alert.threat_level)}</p>
                        <p><span className="font-semibold">Detected:</span> {formatDate(alert.timestamp)}</p>
                        <p><span className="font-semibold">Resolved By:</span> {alert.resolved_by || 'Pending assignment'}</p>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div
                          className={`rounded-2xl border p-4 ${
                            isDark ? 'border-slate-700 bg-slate-900 text-slate-300' : 'border-slate-200 bg-white text-slate-700'
                          }`}
                        >
                          <p className={`mb-3 font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Suspect Face Data</p>
                          <div
                            className={`flex h-48 items-center justify-center overflow-hidden rounded-2xl border ${
                              isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                            }`}
                          >
                            {alertImageUrls[`suspect-${alert.id}`] ? (
                              <img
                                src={alertImageUrls[`suspect-${alert.id}`]}
                                alt={`Suspect face for alert ${alert.id}`}
                                className="h-full w-full object-cover"
                              />
                            ) : (
                              <span className={`px-4 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                                Suspect photo not available.
                              </span>
                            )}
                          </div>
                        </div>

                        <div
                          className={`rounded-2xl border p-4 ${
                            isDark ? 'border-slate-700 bg-slate-900 text-slate-300' : 'border-slate-200 bg-white text-slate-700'
                          }`}
                        >
                          <p className={`mb-3 font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Captured Evidence</p>
                          <div
                            className={`flex h-48 items-center justify-center overflow-hidden rounded-2xl border ${
                              isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                            }`}
                          >
                            {alertImageUrls[`evidence-${alert.id}`] ? (
                              <img
                                src={alertImageUrls[`evidence-${alert.id}`]}
                                alt={`Evidence for alert ${alert.id}`}
                                className="h-full w-full object-cover"
                              />
                            ) : (
                              <span className={`px-4 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                                Evidence photo not available.
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div
                        className={`rounded-2xl border px-4 py-3 text-sm ${
                          isDark ? 'border-slate-700 bg-slate-900 text-slate-300' : 'border-slate-200 bg-white text-slate-700'
                        }`}
                      >
                        <p className={`font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Description</p>
                        <p className="mt-2 leading-6">{alert.description || 'No additional incident description available.'}</p>
                      </div>

                      <div
                        className={`rounded-2xl border px-4 py-3 text-sm ${
                          isDark ? 'border-slate-700 bg-slate-900 text-slate-300' : 'border-slate-200 bg-white text-slate-700'
                        }`}
                      >
                        <label className={`mb-2 block font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                          Operator Notes
                        </label>
                        <textarea
                          rows={3}
                          value={draftNotes[alert.id] ?? ''}
                          onChange={(event) =>
                            setDraftNotes((current) => ({
                              ...current,
                              [alert.id]: event.target.value,
                            }))
                          }
                          placeholder="Add investigation notes or closure details"
                          className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
                            isDark
                              ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                              : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
                          }`}
                        />
                      </div>
                    </div>

                    <div className="flex min-w-[16rem] flex-col gap-3">
                      <button
                        type="button"
                        onClick={() => setActiveAlertId(alert.id)}
                        className={`inline-flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold transition-colors ${
                          isDark
                            ? 'border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-700'
                            : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                        }`}
                        aria-label={`Open alert ${alert.id} in full screen`}
                      >
                        <Expand className="h-4 w-4" />
                        Maximize
                      </button>

                      <button
                        type="button"
                        onClick={() => navigate(`/track?alertId=${alert.id}`)}
                        className={`inline-flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold transition-colors ${
                          isDark
                            ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200 hover:bg-cyan-400/20'
                            : 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                        }`}
                        aria-label={`Track alert ${alert.id}`}
                      >
                        <MapPin className="h-4 w-4" />
                        Track
                      </button>

                      {isPending ? (
                        <button
                          type="button"
                          disabled={isActionBusy}
                          onClick={() => void handleAlertAction(alert.id, 'acknowledge', 'acknowledged')}
                          className={`rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${
                            isDark ? 'bg-amber-400 text-slate-950 hover:bg-amber-300' : 'bg-amber-500 text-white hover:bg-amber-600'
                          } disabled:cursor-not-allowed disabled:opacity-70`}
                        >
                          {isActionBusy ? 'Updating...' : 'Acknowledge'}
                        </button>
                      ) : null}

                      {(isPending || isAcknowledged) ? (
                        <button
                          type="button"
                          disabled={isActionBusy}
                          onClick={() => void handleAlertAction(alert.id, 'resolve', 'resolved')}
                          className={`rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${
                            isDark ? 'bg-emerald-500 text-slate-950 hover:bg-emerald-400' : 'bg-emerald-700 text-white hover:bg-emerald-600'
                          } disabled:cursor-not-allowed disabled:opacity-70`}
                        >
                          {isActionBusy ? 'Updating...' : 'Mark Resolved'}
                        </button>
                      ) : null}

                      {(isPending || isAcknowledged) ? (
                        <button
                          type="button"
                          disabled={isActionBusy}
                          onClick={() => void handleAlertAction(alert.id, 'false-alarm', 'false_alarm')}
                          className={`rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${
                            isDark ? 'bg-slate-700 text-slate-100 hover:bg-slate-600' : 'bg-slate-900 text-white hover:bg-slate-800'
                          } disabled:cursor-not-allowed disabled:opacity-70`}
                        >
                          {isActionBusy ? 'Updating...' : 'Mark False Alarm'}
                        </button>
                      ) : null}

                      <div
                        className={`rounded-2xl border px-4 py-3 text-sm ${
                          isDark ? 'border-slate-700 bg-slate-900 text-slate-400' : 'border-slate-200 bg-white text-slate-600'
                        }`}
                      >
                        <p className={`font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Current Notes</p>
                        <p className="mt-2 leading-6">{alert.notes || 'No notes saved yet.'}</p>
                      </div>
                    </div>
                  </div>
                </article>
              )
            })
          )}
        </div>
      </section>

      {activeAlert ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/95 p-4">
          <article
            className={`flex h-full w-full max-w-7xl flex-col rounded-3xl border p-6 shadow-2xl ${
              isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
            }`}
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className={`text-2xl font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  {activeAlert.person_name || 'Unknown Match'} • Alert #{activeAlert.id}
                </h2>
                <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {cameraNameById[activeAlert.camera_id] ?? activeAlert.camera_id} • {formatDate(activeAlert.timestamp)} • Press ESC to exit
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setActiveAlertId(null)
                    navigate(`/track?alertId=${activeAlert.id}`)
                  }}
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                    isDark
                      ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200 hover:bg-cyan-400/20'
                      : 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                  }`}
                >
                  <MapPin className="h-4 w-4" />
                  Track
                </button>

                <button
                  type="button"
                  onClick={() => setActiveAlertId(null)}
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                    isDark
                      ? 'border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700'
                      : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <Shrink className="h-4 w-4" />
                  Exit
                </button>
              </div>
            </div>

            <div className="grid flex-1 gap-4 overflow-y-auto xl:grid-cols-[1.6fr_1fr]">
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div
                    className={`rounded-2xl border p-4 ${
                      isDark ? 'border-slate-700 bg-slate-800 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-700'
                    }`}
                  >
                    <p className={`mb-3 font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Suspect Face Data</p>
                    <div
                      className={`flex h-72 items-center justify-center overflow-hidden rounded-2xl border ${
                        isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
                      }`}
                    >
                      {alertImageUrls[`suspect-${activeAlert.id}`] ? (
                        <img
                          src={alertImageUrls[`suspect-${activeAlert.id}`]}
                          alt={`Suspect face for alert ${activeAlert.id}`}
                          className="h-full w-full object-contain"
                        />
                      ) : (
                        <span className={`px-4 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                          Suspect photo not available.
                        </span>
                      )}
                    </div>
                  </div>

                  <div
                    className={`rounded-2xl border p-4 ${
                      isDark ? 'border-slate-700 bg-slate-800 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-700'
                    }`}
                  >
                    <p className={`mb-3 font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Captured Evidence</p>
                    <div
                      className={`flex h-72 items-center justify-center overflow-hidden rounded-2xl border ${
                        isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
                      }`}
                    >
                      {alertImageUrls[`evidence-${activeAlert.id}`] ? (
                        <img
                          src={alertImageUrls[`evidence-${activeAlert.id}`]}
                          alt={`Evidence for alert ${activeAlert.id}`}
                          className="h-full w-full object-contain"
                        />
                      ) : (
                        <span className={`px-4 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                          Evidence photo not available.
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div
                  className={`rounded-2xl border p-4 text-sm ${
                    isDark ? 'border-slate-700 bg-slate-800 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-700'
                  }`}
                >
                  <p className={`mb-2 font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Description</p>
                  <p>{activeAlert.description || 'No additional incident description available.'}</p>
                </div>
              </div>

              <div
                className={`rounded-2xl border p-4 text-sm ${
                  isDark ? 'border-slate-700 bg-slate-800 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-700'
                }`}
              >
                <div className="space-y-2">
                  <p><span className="font-semibold">Status:</span> {formatLabel(activeAlert.status)}</p>
                  <p><span className="font-semibold">Severity:</span> {formatLabel(activeAlert.severity)}</p>
                  <p><span className="font-semibold">Category:</span> {formatLabel(activeAlert.category)}</p>
                  <p><span className="font-semibold">Type:</span> {formatLabel(activeAlert.alert_type)}</p>
                  <p><span className="font-semibold">Threat:</span> {formatLabel(activeAlert.threat_level)}</p>
                  <p><span className="font-semibold">Resolved By:</span> {activeAlert.resolved_by || 'Pending assignment'}</p>
                </div>
                <div className="mt-4 border-t pt-4">
                  <p className={`font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Current Notes</p>
                  <p className="mt-2 leading-6">{activeAlert.notes || 'No notes saved yet.'}</p>
                </div>
              </div>
            </div>
          </article>
        </div>
      ) : null}
    </div>
  )
}
