import type { WSMessage } from '../types'

type MessageHandler = (msg: WSMessage) => void

export class WSClient {
  private ws: WebSocket | null = null
  private url: string
  private handlers: MessageHandler[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 3000
  private shouldReconnect = true

  constructor(path: string) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = `${protocol}//${window.location.host}${path}`
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.shouldReconnect = true
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      console.log(`[WS] Connected: ${this.url}`)
      // Start ping interval
      this.pingInterval = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send('ping')
        }
      }, 30000)
    }

    this.ws.onmessage = (event) => {
      if (event.data === 'pong') return
      try {
        const msg: WSMessage = JSON.parse(event.data)
        this.handlers.forEach(h => h(msg))
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    this.ws.onclose = () => {
      console.log(`[WS] Disconnected: ${this.url}`)
      this.cleanup()
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay)
      }
    }

    this.ws.onerror = (e) => {
      console.error(`[WS] Error: ${this.url}`, e)
    }
  }

  private pingInterval: ReturnType<typeof setInterval> | null = null

  private cleanup() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  disconnect() {
    this.shouldReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.cleanup()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  onMessage(handler: MessageHandler) {
    this.handlers.push(handler)
  }

  removeHandler(handler: MessageHandler) {
    this.handlers = this.handlers.filter(h => h !== handler)
  }
}

export const packetWS = new WSClient('/ws/packets')
export const interceptWS = new WSClient('/ws/intercepted')
