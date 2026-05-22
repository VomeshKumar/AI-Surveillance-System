import { apiFetch } from './api'

export async function requestShutdownToken(): Promise<{ token: string, expires_in_seconds: number }> {
  const response = await apiFetch('/api/v1/system/shutdown-token', {
    method: 'POST',
  })
  
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to generate shutdown token')
  }
  
  return response.json()
}

export async function initiateShutdown(token: string): Promise<{ message: string }> {
  const response = await apiFetch('/api/v1/system/shutdown', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ token })
  })
  
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to initiate shutdown')
  }
  
  return response.json()
}

export async function requestRestartToken(): Promise<{ token: string, expires_in_seconds: number }> {
  const response = await apiFetch('/api/v1/system/restart-token', {
    method: 'POST',
  })
  
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to generate restart token')
  }
  
  return response.json()
}

export async function initiateRestart(token: string): Promise<{ message: string }> {
  const response = await apiFetch('/api/v1/system/restart', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ token })
  })
  
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to initiate restart')
  }
  
  return response.json()
}
