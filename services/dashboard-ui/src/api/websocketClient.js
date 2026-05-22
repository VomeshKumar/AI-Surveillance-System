/**
 * Reconnecting WebSocket client for real-time surveillance events.
 *
 * Usage:
 *   import { connectWebSocket, onWsEvent, disconnectWebSocket } from './websocketClient'
 *
 *   connectWebSocket()
 *   const unsub = onWsEvent('NEW_DETECTION', (data) => { ... })
 *   // later:
 *   unsub()
 *   disconnectWebSocket()
 */

const WS_BASE_URL =
  (import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8001') + '/ws'

const RECONNECT_INTERVAL_MS = 3000
const MAX_RECONNECT_ATTEMPTS = 20

/** @type {WebSocket | null} */
let socket = null
let reconnectTimer = null
let reconnectAttempts = 0
let intentionalClose = false
let connectionUsers = 0

/**
 * Event listeners keyed by message `type`.
 * @type {Map<string, Set<Function>>}
 */
const listeners = new Map()

// -------------------------------------------------------
// Public API
// -------------------------------------------------------

/**
 * Open the WebSocket connection (idempotent — safe to call multiple times).
 */
export function connectWebSocket() {
  connectionUsers += 1

  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }

  intentionalClose = false
  reconnectAttempts = 0
  _open()
}

/**
 * Gracefully close the connection and stop reconnecting.
 */
export function disconnectWebSocket() {
  connectionUsers = Math.max(0, connectionUsers - 1)
  if (connectionUsers > 0) {
    return
  }

  intentionalClose = true
  clearTimeout(reconnectTimer)

  if (socket) {
    socket.close()
    socket = null
  }
}

/**
 * Subscribe to a specific WebSocket event type.
 *
 * @param {string} eventType  e.g. 'NEW_DETECTION', 'ALERT_ACKNOWLEDGED'
 * @param {Function} callback Called with the parsed message object.
 * @returns {Function} Unsubscribe function.
 */
export function onWsEvent(eventType, callback) {
  if (!listeners.has(eventType)) {
    listeners.set(eventType, new Set())
  }

  listeners.get(eventType).add(callback)

  // Return unsubscribe handle
  return () => {
    const set = listeners.get(eventType)
    if (set) {
      set.delete(callback)
      if (set.size === 0) listeners.delete(eventType)
    }
  }
}

/**
 * Subscribe to ALL incoming WebSocket messages (regardless of type).
 *
 * @param {Function} callback Called with every parsed message.
 * @returns {Function} Unsubscribe function.
 */
export function onAnyWsEvent(callback) {
  return onWsEvent('*', callback)
}

/**
 * Returns true when the WebSocket is open and ready.
 * @returns {boolean}
 */
export function isWsConnected() {
  return socket !== null && socket.readyState === WebSocket.OPEN
}

// -------------------------------------------------------
// Internal helpers
// -------------------------------------------------------

function _open() {
  try {
    socket = new WebSocket(WS_BASE_URL)
  } catch (err) {
    console.error('[WS] Failed to create WebSocket:', err)
    _scheduleReconnect()
    return
  }

  socket.onopen = () => {
    console.info('[WS] Connected to', WS_BASE_URL)
    reconnectAttempts = 0
  }

  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      const type = message.type || 'UNKNOWN'

      // Dispatch to type-specific listeners
      const typeListeners = listeners.get(type)
      if (typeListeners) {
        typeListeners.forEach((cb) => cb(message))
      }

      // Dispatch to wildcard listeners
      const wildcardListeners = listeners.get('*')
      if (wildcardListeners) {
        wildcardListeners.forEach((cb) => cb(message))
      }
    } catch (err) {
      console.warn('[WS] Failed to parse message:', err)
    }
  }

  socket.onclose = (event) => {
    console.info('[WS] Disconnected — code:', event.code)
    socket = null

    if (!intentionalClose) {
      _scheduleReconnect()
    }
  }

  socket.onerror = (err) => {
    console.error('[WS] Error:', err)
    // onclose will fire after onerror, which triggers reconnect
  }
}

function _scheduleReconnect() {
  if (intentionalClose) return
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.error('[WS] Max reconnect attempts reached. Giving up.')
    return
  }

  reconnectAttempts++
  const delay = Math.min(RECONNECT_INTERVAL_MS * reconnectAttempts, 15000)
  console.info(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`)

  clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(_open, delay)
}
