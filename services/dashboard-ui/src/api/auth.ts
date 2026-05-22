import type { UserRole } from '../context/AuthContext'
import { apiFetch } from '../services/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001'

interface LoginResponse {
  access_token: string
  token_type: string
  name: string
}

interface ApiMessageResponse {
  detail?: string
  message?: string
}

interface JwtPayload {
  sub?: string
  role?: string
}

export interface AuthenticatedLogin {
  name: string
  role: UserRole
  accessToken: string
  tokenType: string
}

export interface ForgotPasswordPayload {
  email: string
}

export interface ResetPasswordPayload {
  email: string
  otp: string
  newPassword: string
  confirmPassword: string
}

export interface ChangePasswordPayload {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

function decodeJwtPayload(token: string): JwtPayload {
  const parts = token.split('.')
  if (parts.length < 2) {
    throw new Error('Invalid token format')
  }

  const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
  return JSON.parse(window.atob(padded)) as JwtPayload
}

function mapBackendRole(role: string | undefined): UserRole | null {
  if (role === 'admin') {
    return 'admin'
  }

  if (role === 'security' || role === 'guard' || role === 'security_officer') {
    return 'security_officer'
  }

  return null
}

export async function loginWithBackend(username: string, password: string): Promise<AuthenticatedLogin> {
  const formBody = new URLSearchParams()
  formBody.set('username', username)
  formBody.set('password', password)

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formBody.toString(),
  })

  let payload: LoginResponse | { detail?: string }

  try {
    payload = (await response.json()) as LoginResponse | { detail?: string }
  } catch {
    payload = {}
  }

  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail || 'Unable to sign in right now')
  }

  const loginPayload = payload as LoginResponse
  const tokenPayload = decodeJwtPayload(loginPayload.access_token)
  const mappedRole = mapBackendRole(tokenPayload.role)

  if (!mappedRole || !tokenPayload.sub) {
    throw new Error('This account is not allowed in the current dashboard')
  }

  return {
    name: loginPayload.name?.trim() || tokenPayload.sub,
    role: mappedRole,
    accessToken: loginPayload.access_token,
    tokenType: loginPayload.token_type,
  }
}

export async function requestPasswordResetOtp(payload: ForgotPasswordPayload): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  let responsePayload: ApiMessageResponse = {}

  try {
    responsePayload = (await response.json()) as ApiMessageResponse
  } catch {
    responsePayload = {}
  }

  if (!response.ok) {
    throw new Error(responsePayload.detail || 'Unable to send OTP right now')
  }

  return responsePayload.message || 'OTP sent successfully'
}

export async function resetPasswordWithOtp(payload: ResetPasswordPayload): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  let responsePayload: ApiMessageResponse = {}

  try {
    responsePayload = (await response.json()) as ApiMessageResponse
  } catch {
    responsePayload = {}
  }

  if (!response.ok) {
    throw new Error(responsePayload.detail || 'Unable to reset password right now')
  }

  return responsePayload.message || 'Password updated successfully'
}

export async function changePassword(payload: ChangePasswordPayload): Promise<string> {
  const response = await apiFetch('/api/v1/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  let responsePayload: ApiMessageResponse = {}

  try {
    responsePayload = (await response.json()) as ApiMessageResponse
  } catch {
    responsePayload = {}
  }

  if (!response.ok) {
    throw new Error(responsePayload.detail || 'Unable to change password right now')
  }

  return responsePayload.message || 'Password changed successfully'
}
