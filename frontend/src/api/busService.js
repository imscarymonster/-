// frontend/src/api/busService.js
import apiClient from './request';

export default {
  // 1. 获取所有车辆的实时位置
  getBusLocations() {
    return apiClient.get('/buses/locations');
  },
  
  // 2. 获取某个站点的预计到站时间
  getStationETA(stationId) {
    return apiClient.get(`/eta/${stationId}`);
  },

  // 3. (管理员用) 发送调度指令
  sendDispatchCommand(data) {
    return apiClient.post('/admin/dispatch', data);
  }
};