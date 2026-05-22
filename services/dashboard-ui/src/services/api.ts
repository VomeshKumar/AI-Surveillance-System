const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001'

let authorizationHeader: string | null = null

export function setApiAccessToken(accessToken: string, tokenType = 'bearer') {
  authorizationHeader = `${tokenType} ${accessToken}`
}

export function clearApiAccessToken() {
  authorizationHeader = null
}

export function getApiAuthorizationHeader() {
  return authorizationHeader
}

export async function apiFetch(input: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)

  if (authorizationHeader) {
    headers.set('Authorization', authorizationHeader)
  }

  return fetch(`${API_BASE_URL}${input}`, {
    ...init,
    headers,
  })
}
