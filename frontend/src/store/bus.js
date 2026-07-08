// Pinia 状态管理 — 存储实时位置、车辆变线状态
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBusStore = defineStore('bus', () => {
  // 所有车辆实时位置
  const buses = ref([])

  // 当前选中线路
  const activeRouteId = ref(null)

  // 客流热力数据
  const heatmapData = ref([])

  // 调度变线记录
  const dispatchRecords = ref([])

  /** 更新车辆位置 */
  function updateBusPosition(busId, lat, lng) {
    const bus = buses.value.find(b => b.id === busId)
    if (bus) {
      bus.latitude = lat
      bus.longitude = lng
    }
  }

  /** 设置车辆变线状态 */
  function setBusReroute(busId, newRouteId) {
    const bus = buses.value.find(b => b.id === busId)
    if (bus) {
      bus.route_id = newRouteId
      bus.status = 3 // 变线中
    }
  }

  return {
    buses,
    activeRouteId,
    heatmapData,
    dispatchRecords,
    updateBusPosition,
    setBusReroute,
  }
})
