// API 接口调用模块
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// ==================== 乘客接口 ====================

/** 获取所有线路 */
export function getRoutes() {
  return api.get('/routes')
}

/** 获取指定线路的站点列表 */
export function getStations(routeId) {
  return api.get(`/routes/${routeId}/stations`)
}

/** 获取车辆实时位置与到站倒计时 */
export function getBusRealtime(busId) {
  return api.get(`/buses/${busId}/realtime`)
}

// ==================== 司机接口 ====================

/** 获取当前司机的调度指令 */
export function getDispatch(driverId) {
  return api.get(`/drivers/${driverId}/dispatch`)
}

/** 司机确认接受调度 */
export function acceptDispatch(driverId, dispatchId) {
  return api.post(`/drivers/${driverId}/dispatch/${dispatchId}/accept`)
}

// ==================== 管理接口 ====================

/** 获取全网瞬时客流热力分布 */
export function getHeatmap() {
  return api.get('/admin/heatmap')
}

/** 获取所有车辆实时状态 */
export function getAllBuses() {
  return api.get('/admin/buses')
}

/** 获取效能统计指标 */
export function getStats() {
  return api.get('/admin/stats')
}

export default api
