import { apiFetch } from '../services/api'

export interface TrackingTransition {
  id: number
  camera_id: string
  camera_name: string | null
  camera_location: string | null
  confidence: number | null
  detected_at: string
}

export interface TrackingSession {
  id: number
  alert_id: number | null
  person_id: number
  person_name: string | null
  alert_type: string | null
  alert_description: string | null
  status: string
  current_camera_id: string | null
  current_camera_name: string | null
  current_camera_location: string | null
  last_detection_at: string | null
  started_at: string
  ended_at: string | null
  ended_reason: string | null
  movement_history: TrackingTransition[]
}

export async function startTrackingSession(alertId: number): Promise<TrackingSession> {
  const response = await apiFetch('/api/v1/track/sessions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ alert_id: alertId }),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || 'Unable to start tracking')
  }

  return response.json()
}

export async function fetchTrackingSession(sessionId: number): Promise<TrackingSession> {
  const response = await apiFetch(`/api/v1/track/sessions/${sessionId}`)
  if (!response.ok) {
    throw new Error('Unable to load tracking session')
  }
  return response.json()
}

export async function fetchTrackingSessionForAlert(alertId: number): Promise<TrackingSession> {
  const response = await apiFetch(`/api/v1/track/alerts/${alertId}`)
  if (!response.ok) {
    throw new Error('Unable to load tracking session')
  }
  return response.json()
}
