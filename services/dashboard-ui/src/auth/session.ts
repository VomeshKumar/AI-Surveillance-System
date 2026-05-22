import type { UserRole } from '../context/AuthContext'

export interface StoredAuthUser {
  name: string
  role: UserRole
  accessToken: string
  tokenType: string
}

interface JwtPayload {
  sub?: string
  role?: string
  exp?: number
}

export const ACCESS_TOKEN_STORAGE_KEY = 'accessToken'
export const AUTH_USER_STORAGE_KEY = 'authUser'
export const USER_ROLE_STORAGE_KEY = 'userRole'
export const TOKEN_TYPE_STORAGE_KEY = 'tokenType'

function isValidRole(role: unknown): role is UserRole {
  return role === 'admin' || role === 'security_officer'
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

function isTokenExpired(token: string) {
  const payload = decodeJwtPayload(token)

  if (typeof payload.exp !== 'number') {
    return true
  }

  return payload.exp * 1000 <= Date.now()
}

function clearStorageSession(storage: Storage) {
  storage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  storage.removeItem(AUTH_USER_STORAGE_KEY)
  storage.removeItem(USER_ROLE_STORAGE_KEY)
  storage.removeItem(TOKEN_TYPE_STORAGE_KEY)
}

function readSessionFromStorage(storage: Storage): StoredAuthUser | null {
  const accessToken = storage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  const name = storage.getItem(AUTH_USER_STORAGE_KEY)
  const role = storage.getItem(USER_ROLE_STORAGE_KEY)
  const tokenType = storage.getItem(TOKEN_TYPE_STORAGE_KEY)

  if (!accessToken && !name && !role && !tokenType) {
    return null
  }

  if (!accessToken || !name || !isValidRole(role) || !tokenType) {
    clearStorageSession(storage)
    return null
  }

  try {
    if (isTokenExpired(accessToken)) {
      clearStorageSession(storage)
      return null
    }
  } catch {
    clearStorageSession(storage)
    return null
  }

  return {
    name,
    role,
    accessToken,
    tokenType,
  }
}

export function restoreStoredAuthSession(): StoredAuthUser | null {
  const localSession = readSessionFromStorage(window.localStorage)
  if (localSession) {
    return localSession
  }

  return readSessionFromStorage(window.sessionStorage)
}

export function persistAuthSession(user: StoredAuthUser, rememberMe: boolean) {
  clearStoredAuthSession()

  const storage = rememberMe ? window.localStorage : window.sessionStorage

  storage.setItem(ACCESS_TOKEN_STORAGE_KEY, user.accessToken)
  storage.setItem(AUTH_USER_STORAGE_KEY, user.name)
  storage.setItem(USER_ROLE_STORAGE_KEY, user.role)
  storage.setItem(TOKEN_TYPE_STORAGE_KEY, user.tokenType)
}

export function clearStoredAuthSession() {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    clearStorageSession(storage)
  }
}
