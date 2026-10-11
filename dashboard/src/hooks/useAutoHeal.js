import { useCallback, useEffect, useRef, useState } from 'react'

const BUFFER = 120          // 120 ticks x 5s = 10 minutes of history
const MAX_EVENTS = 150

function wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/stream`
}

/**
 * Live connection to the AutoHeal server.
 * No mock fallback: when the server is unreachable the UI says so instead of
 * inventing data.
 */
export default function useAutoHeal() {
  const [connected, setConnected] = useState(false)
  const [frame, setFrame] = useState(null)
  const [buffer, setBuffer] = useState([])
  const [events, setEvents] = useState([])
  const [meta, setMeta] = useState(null)
  const [rounds, setRounds] = useState([])
  const [campaigns, setCampaigns] = useState([])
  const wsRef = useRef(null)
  const retryRef = useRef(0)
  const timerRef = useRef(null)

  const mergeEvents = useCallback((incoming) => {
    if (!incoming?.length) return
    setEvents((prev) => {
      const seen = new Set(prev.map((e) => e.id))
      const fresh = incoming.filter((e) => !seen.has(e.id))
      if (!fresh.length) return prev
      return [...prev, ...fresh].slice(-MAX_EVENTS)
    })
  }, [])

  const refreshRounds = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([fetch('/api/rounds'), fetch('/api/campaigns?limit=5')])
      if (r.ok) setRounds(await r.json())
      if (c.ok) setCampaigns(await c.json())
    } catch {
      /* server unreachable — the connection banner already says so */
    }
  }, [])

  useEffect(() => {
    let disposed = false

    const connect = () => {
      const ws = new WebSocket(wsUrl())
      wsRef.current = ws
      ws.onopen = () => {
        retryRef.current = 0
        setConnected(true)
        refreshRounds()
      }
      ws.onmessage = (msg) => {
        let data
        try {
          data = JSON.parse(msg.data)
        } catch {
          return
        }
        if (data.type === 'hello') {
          setMeta(data)
          mergeEvents(data.events)
          return
        }
        if (data.type === 'tick') {
          setFrame(data)
          setBuffer((prev) => [...prev, data].slice(-BUFFER))
          mergeEvents(data.events)
          if (data.events?.some((e) => ['RECOVERED', 'FAILED', 'SUMMARY', 'TEARDOWN', 'DETECT', 'INJECT'].includes(e.phase))) {
            refreshRounds()
          }
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (disposed) return
        const delay = Math.min(1000 * 2 ** retryRef.current, 10000)
        retryRef.current += 1
        timerRef.current = setTimeout(connect, delay)
      }
      ws.onerror = () => ws.close()
    }

    connect()
    const poll = setInterval(refreshRounds, 10000)
    return () => {
      disposed = true
      clearInterval(poll)
      clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [mergeEvents, refreshRounds])

  const api = useCallback(async (path, body) => {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`)
    refreshRounds()
    return data
  }, [refreshRounds])

  return { connected, frame, buffer, events, meta, rounds, campaigns, api }
}
