import { apiFetch } from '../services/api'

export interface Camera {
  id: number
  camera_id: string
  camera_name: string
  location?: string
  status: string
  rtsp_url?: string
  created_at: string
  updated_at: string
}

export interface CameraCreatePayload {
  camera_id: string
  camera_name: string
  location?: string
  status?: string
  rtsp_url?: string
}

export async function fetchCameras(): Promise<Camera[]> {
  const response = await apiFetch('/api/v1/cameras')
  if (!response.ok) {
    throw new Error('Failed to fetch cameras')
  }
  return response.json()
}

export async function createCamera(payload: CameraCreatePayload): Promise<Camera> {
  const response = await apiFetch('/api/v1/cameras', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || 'Failed to add camera')
  }

  return response.json()
}

export async function deleteCamera(cameraId: string): Promise<void> {
  const response = await apiFetch(`/api/v1/cameras?camera_id=${encodeURIComponent(cameraId)}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || 'Failed to delete camera')
  }
}

export interface StreamDiagnostic {
  camera_id: string
  clients: number
  frames_received: number
  fps_in: number
  latest_sequence: number
  frame_age_ms: number | null
  is_stale: boolean
  reconnecting: boolean
  decode_errors: number
  redis_errors: number
  last_error: string | null
  worker_running: boolean
}

export async function fetchStreamDiagnostics(): Promise<StreamDiagnostic[]> {
  const response = await apiFetch('/api/v1/cameras/stream/diagnostics')
  if (!response.ok) {
    throw new Error('Failed to fetch stream diagnostics')
  }

  const payload = await response.json()
  return payload.streams ?? []
}
