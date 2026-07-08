// WebSocket 通信工具
const WS_BASE = `ws://${window.location.host}/ws`

let socket = null
const listeners = new Map()

/** 建立 WebSocket 连接 */
export function connectWS(clientType = 'passenger') {
  if (socket && socket.readyState === WebSocket.OPEN) return socket

  socket = new WebSocket(`${WS_BASE}/${clientType}`)

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data)
    const { type } = data
    if (listeners.has(type)) {
      listeners.get(type).forEach(cb => cb(data.payload))
    }
  }

  socket.onclose = () => {
    // 断线重连
    setTimeout(() => connectWS(clientType), 3000)
  }

  return socket
}

/** 订阅消息类型 */
export function onMessage(type, callback) {
  if (!listeners.has(type)) {
    listeners.set(type, [])
  }
  listeners.get(type).push(callback)
}

/** 发送消息 */
export function sendMessage(type, payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type, payload }))
  }
}

/** 断开连接 */
export function disconnectWS() {
  if (socket) {
    socket.close()
    socket = null
  }
}
