import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'

let _socket = null

function getSocket() {
  if (!_socket) {
    _socket = io('/', {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    })
  }
  return _socket
}

/**
 * Subscribe to a Socket.io event. Automatically cleans up on unmount.
 * @param {string} event
 * @param {(data: any) => void} handler
 */
export function useSocketEvent(event, handler) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    const socket = getSocket()
    const fn = (data) => handlerRef.current(data)
    socket.on(event, fn)
    return () => socket.off(event, fn)
  }, [event])
}

/**
 * Returns the shared socket instance for imperative emit() calls.
 */
export function useSocket() {
  return getSocket()
}

/**
 * Subscribe to project-specific real-time events.
 * @param {string} projectId
 * @param {{ onClipUpdate?: Function, onAnalysisUpdate?: Function }} callbacks
 * @returns {{ connected: boolean }}
 */
export function useProjectSocket(projectId, callbacks = {}) {
  const [connected, setConnected] = useState(false)
  const callbacksRef = useRef(callbacks)
  callbacksRef.current = callbacks

  useEffect(() => {
    if (!projectId) return

    const socket = getSocket()

    const onConnect    = () => setConnected(true)
    const onDisconnect = () => setConnected(false)

    const onClipUpdate = (data) => {
      if (data?.project_id === projectId || !data?.project_id) {
        callbacksRef.current.onClipUpdate?.(data)
      }
    }
    const onAnalysisUpdate = (data) => {
      if (data?.project_id === projectId || !data?.project_id) {
        callbacksRef.current.onAnalysisUpdate?.(data)
      }
    }

    if (socket.connected) setConnected(true)

    socket.on('connect',         onConnect)
    socket.on('disconnect',      onDisconnect)
    socket.on('clip_update',     onClipUpdate)
    socket.on('analysis_update', onAnalysisUpdate)

    return () => {
      socket.off('connect',         onConnect)
      socket.off('disconnect',      onDisconnect)
      socket.off('clip_update',     onClipUpdate)
      socket.off('analysis_update', onAnalysisUpdate)
    }
  }, [projectId])

  return { connected }
}
