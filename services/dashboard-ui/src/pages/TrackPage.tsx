import { Activity, AlertTriangle, Camera, Clock3, Loader2, MapPin, RadioTower } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { connectWebSocket, disconnectWebSocket, onWsEvent } from '../api/websocketClient'
import { fetchStreamDiagnostics, type StreamDiagnostic } from '../api/cameras'
import {
  fetchTrackingSession,
  fetchTrackingSessionForAlert,
  startTrackingSession,
  type TrackingSession,
} from '../api/tracking'

interface TrackPageProps {
  theme: 'light' | 'dark'
}

function formatDateTime(value: string | null) {
  if (!value) {
    return 'No detection yet'
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function TrackPage({ theme }: TrackPageProps) {
  const isDark = theme === 'dark'
  const [searchParams] = useSearchParams()
  const [session, setSession] = useState<TrackingSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [streamVersion, setStreamVersion] = useState(0)
  const [streamDiagnostics, setStreamDiagnostics] = useState<StreamDiagnostic[]>([])
  const [errorMessage, setErrorMessage] = useState('')
  const [lastRealtimeUpdateAt, setLastRealtimeUpdateAt] = useState<number | null>(null)
  const sessionRef = useRef<TrackingSession | null>(null)
  const refreshTimerRef = useRef<number | null>(null)

  useEffect(() => {
    sessionRef.current = session
  }, [session])

  useEffect(() => {
    if (session?.current_camera_id) {
      setStreamVersion((current) => current + 1)
    }
  }, [session?.current_camera_id])

  const loadSession = async () => {
    const alertId = Number(searchParams.get('alertId'))
    const sessionId = Number(searchParams.get('sessionId'))

    if (!alertId && !sessionId) {
      setErrorMessage('Open tracking from an alert using the Track button.')
      setIsLoading(false)
      return
    }

    try {
      setErrorMessage('')
      setIsLoading(true)
      const payload = sessionId
        ? await fetchTrackingSession(sessionId)
        : await startTrackingSession(alertId)
      setSession(payload)
      setIsLoading(false)
    } catch (error) {
      if (alertId) {
        try {
          const payload = await fetchTrackingSessionForAlert(alertId)
          setSession(payload)
          setIsLoading(false)
          return
        } catch {
          // Fall through to the original error message.
        }
      }
      setErrorMessage(error instanceof Error ? error.message : 'Unable to load tracking')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadSession()
  }, [searchParams])

  // Poll session data as a lightweight safety net if a WebSocket event is missed.
  useEffect(() => {
    if (!session?.id || session.status !== 'active') {
      return
    }

    const pollSession = async () => {
      try {
        const updated = await fetchTrackingSession(session.id)
        setSession(updated)
      } catch {
        // Polling should never interrupt tracking
      }
    }

    const intervalId = window.setInterval(pollSession, 1000)
    return () => window.clearInterval(intervalId)
  }, [session?.id, session?.status])

  useEffect(() => {
    const loadDiagnostics = async () => {
      try {
        setStreamDiagnostics(await fetchStreamDiagnostics())
      } catch {
        // Diagnostics should never interrupt tracking.
      }
    }

    void loadDiagnostics()
    const intervalId = window.setInterval(loadDiagnostics, 3000)
    return () => window.clearInterval(intervalId)
  }, [])

  useEffect(() => {
    connectWebSocket()

    const refreshActiveSession = (message: any) => {
      const current = sessionRef.current
      if (!current) {
        return
      }

      const data = message.data || {}
      const sameSession = data.session_id === current.id
      const sameAlert = data.alert_id && data.alert_id === current.alert_id
      const samePerson = data.person_id === current.person_id

      if (message.type === 'TRACKING_UPDATED' && sameSession && samePerson && data.camera_id) {
        const incomingTime = data.detected_at ? new Date(data.detected_at).getTime() : Date.now()
        const currentTime = current.last_detection_at ? new Date(current.last_detection_at).getTime() : 0

        if (Number.isNaN(incomingTime) || incomingTime >= currentTime) {
          setLastRealtimeUpdateAt(Date.now())
          setSession((existing) => {
            if (!existing || existing.id !== current.id || existing.person_id !== current.person_id) {
              return existing
            }
            const cameraChanged = existing.current_camera_id !== data.camera_id

            return {
              ...existing,
              current_camera_id: data.camera_id,
              current_camera_name: data.camera_name ?? (cameraChanged ? null : existing.current_camera_name),
              current_camera_location: data.camera_location ?? (cameraChanged ? null : existing.current_camera_location),
              last_detection_at: data.detected_at ?? existing.last_detection_at,
            }
          })

          if (refreshTimerRef.current) {
            window.clearTimeout(refreshTimerRef.current)
          }
          refreshTimerRef.current = window.setTimeout(() => {
            void fetchTrackingSession(current.id)
              .then(setSession)
              .catch(() => undefined)
          }, 250)
        }
        return
      }

      if (sameSession || sameAlert || samePerson) {
        void fetchTrackingSession(current.id)
          .then(setSession)
          .catch(() => undefined)
      }
    }

    const unsubscribers = [
      onWsEvent('TRACKING_UPDATED', refreshActiveSession),
      onWsEvent('TRACKING_ENDED', refreshActiveSession),
      onWsEvent('ALERT_RESOLVED', refreshActiveSession),
      onWsEvent('ALERT_FALSE_ALARM', refreshActiveSession),
    ]

    return () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current)
      }
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      disconnectWebSocket()
    }
  }, [])

  const currentCameraLabel = session?.current_camera_name || session?.current_camera_id || 'Searching cameras'
  const isActive = session?.status === 'active'
  const lastDetectionMs = session?.last_detection_at ? new Date(session.last_detection_at).getTime() : 0
  const hasRecentDetection = Boolean(isActive && lastDetectionMs && Date.now() - lastDetectionMs < 4000)
  const trackingStatusLabel = isActive
    ? hasRecentDetection ? 'Live' : 'Searching'
    : session?.ended_reason || 'Waiting'
  const streamUrl = session?.current_camera_id
    ? `http://localhost:8001/api/v1/cameras/stream?camera_id=${encodeURIComponent(session.current_camera_id)}&v=${streamVersion}`
    : ''
  const activeDiagnostic = streamDiagnostics.find((item) => item.camera_id === session?.current_camera_id)

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: 'Tracked Person', value: session?.person_name || 'Not selected', icon: MapPin },
          { label: 'Current Camera', value: currentCameraLabel, icon: Camera },
          { label: 'Tracking Status', value: trackingStatusLabel, icon: Activity },
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
                <div className="min-w-0">
                  <p className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{metric.label}</p>
                  <p className={`mt-3 truncate text-2xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                    {isLoading ? '--' : metric.value}
                  </p>
                </div>
                <Icon className={`h-5 w-5 ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`} />
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
          <div className="mb-5 flex items-center justify-between gap-4">
            <div>
              <h1 className={`text-2xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Track Dashboard</h1>
              <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Alert #{session?.alert_id ?? '--'} • Latest detection: {formatDateTime(session?.last_detection_at ?? null)}
              </p>
            </div>
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
                isActive
                  ? isDark ? 'bg-emerald-500/15 text-emerald-300' : 'bg-emerald-100 text-emerald-700'
                  : isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-700'
              }`}
            >
              <RadioTower className="h-3.5 w-3.5" />
              {isActive ? 'Tracking Live' : 'Tracking Ended'}
            </span>
          </div>

          {lastRealtimeUpdateAt ? (
            <p className={`mb-3 text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              Realtime tracking sync received {Math.max(0, Math.round((Date.now() - lastRealtimeUpdateAt) / 1000))}s ago.
            </p>
          ) : null}

          {activeDiagnostic ? (
            <div
              className={`mb-4 grid gap-2 rounded-lg border px-3 py-2 text-xs sm:grid-cols-4 ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-600'
              }`}
            >
              <span>FPS: {activeDiagnostic.fps_in}</span>
              <span>Latency: {activeDiagnostic.frame_age_ms ?? '--'} ms</span>
              <span>Clients: {activeDiagnostic.clients}</span>
              <span>{activeDiagnostic.reconnecting || activeDiagnostic.is_stale ? 'Reconnecting' : 'Healthy'}</span>
            </div>
          ) : null}

          <div
            className={`flex aspect-video items-center justify-center overflow-hidden rounded-lg border ${
              isDark ? 'border-slate-700 bg-slate-950' : 'border-slate-200 bg-slate-100'
            }`}
          >
            {isLoading ? (
              <Loader2 className={`h-8 w-8 animate-spin ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`} />
            ) : streamUrl && isActive ? (
              <img
                key={session?.current_camera_id}
                src={streamUrl}
                loading="eager"
                decoding="async"
                alt={`Live tracking feed for ${session?.person_name || 'person'}`}
                className="h-full w-full object-contain"
              />
            ) : (
              <div className="px-6 text-center">
                <AlertTriangle className={`mx-auto h-8 w-8 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <p className={`mt-3 text-sm font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  {isActive ? 'No current detection available' : 'Tracking session closed'}
                </p>
                <p className={`mt-1 text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  The feed will switch automatically when the person appears on any active camera.
                </p>
              </div>
            )}
          </div>
        </article>

        <aside
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <h2 className={`mb-4 text-xl font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Movement History</h2>
          <div className="space-y-3">
            {session?.movement_history.length ? (
              session.movement_history.map((event) => (
                <div
                  key={event.id}
                  className={`rounded-lg border px-4 py-3 text-sm ${
                    isDark ? 'border-slate-700 bg-slate-800 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <Clock3 className={`mt-0.5 h-4 w-4 ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`} />
                    <div>
                      <p className="font-semibold">{event.camera_name || event.camera_id}</p>
                      <p className={`mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {event.camera_location || event.camera_id} • {formatDateTime(event.detected_at)}
                      </p>
                      {event.confidence !== null ? (
                        <p className={`mt-1 text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                          Confidence: {Math.round(event.confidence * 100)}%
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div
                className={`rounded-lg border border-dashed px-4 py-8 text-center text-sm ${
                  isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
                }`}
              >
                Waiting for first camera detection.
              </div>
            )}
          </div>
        </aside>
      </section>
    </div>
  )
}
