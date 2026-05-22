/**
 * Lightweight alert store that connects to the WebSocket and
 * maintains an in-memory list of live alerts for the dashboard.
 *
 * Usage:
 *   import { alertStore } from './alertStore'
 *
 *   alertStore.subscribe((alerts) => { ... })
 *   alertStore.start()       // connects WS + fetches initial alerts
 *   alertStore.stop()        // disconnects WS
 */

import { connectWebSocket, disconnectWebSocket, onWsEvent } from '../api/websocketClient'
import { apiFetch } from '../services/api'

const MAX_ALERTS = 200

/** @type {Array<Object>} */
let alerts = []

/** @type {Set<Function>} */
const subscribers = new Set()

/** @type {Array<Function>} */
let unsubHandles = []

// -------------------------------------------------------
// Public API
// -------------------------------------------------------

export const alertStore = {
  /** Get current snapshot of alerts. */
  getAlerts() {
    return alerts
  },

  /**
   * Subscribe to alert list changes.
   * @param {Function} callback  Called with the full alerts array on every change.
   * @returns {Function} Unsubscribe function.
   */
  subscribe(callback) {
    subscribers.add(callback)
    return () => subscribers.delete(callback)
  },

  /**
   * Start the alert store: fetch existing alerts from the API and
   * open the WebSocket for live updates.
   */
  async start() {
    // 1) Fetch existing alerts from REST API
    try {
      const res = await apiFetch('/api/v1/alerts/?limit=100')
      if (res.ok) {
        alerts = await res.json()
        _notify()
      }
    } catch (err) {
      console.error('[AlertStore] Failed to fetch initial alerts:', err)
    }

    // 2) Connect WebSocket and wire event handlers
    connectWebSocket()

    unsubHandles.push(
      onWsEvent('NEW_DETECTION', (msg) => {
        if (msg.data) {
          alerts = [msg.data, ...alerts].slice(0, MAX_ALERTS)
          _notify()
        }
      }),

      onWsEvent('ALERT_ACKNOWLEDGED', (msg) => {
        const alertId = msg.data?.alert_id
        if (alertId) {
          alerts = alerts.map((a) =>
            a.id === alertId || a.alert_id === alertId
              ? { ...a, status: 'acknowledged' }
              : a
          )
          _notify()
        }
      }),

      onWsEvent('ALERT_RESOLVED', (msg) => {
        const alertId = msg.data?.alert_id
        if (alertId) {
          alerts = alerts.map((a) =>
            a.id === alertId || a.alert_id === alertId
              ? { ...a, status: 'resolved' }
              : a
          )
          _notify()
        }
      }),

      onWsEvent('ALERT_FALSE_ALARM', (msg) => {
        const alertId = msg.data?.alert_id
        if (alertId) {
          alerts = alerts.map((a) =>
            a.id === alertId || a.alert_id === alertId
              ? { ...a, status: 'false_alarm' }
              : a
          )
          _notify()
        }
      })
    )
  },

  /** Stop the alert store and disconnect WebSocket. */
  stop() {
    unsubHandles.forEach((unsub) => unsub())
    unsubHandles = []
    disconnectWebSocket()
  },
}

// -------------------------------------------------------
// Internal
// -------------------------------------------------------

function _notify() {
  subscribers.forEach((cb) => {
    try {
      cb(alerts)
    } catch (err) {
      console.error('[AlertStore] Subscriber error:', err)
    }
  })
}
