<template>
  <div class="h-screen flex flex-col bg-gray-50 relative">
    <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center shadow-sm z-10 relative">
      <div class="flex items-center gap-2">
        <span class="text-2xl">🚏</span>
        <h1 class="text-xl font-bold text-gray-800">OptiBus 乘客选站终端</h1>
      </div>
    </header>

    <main class="flex-1 flex justify-center items-center overflow-hidden relative">
      <MapCanvas :isAdmin="false" @stationClick="handleStationSelect" />

      <div v-if="selectedStation" class="absolute bottom-4 sm:bottom-12 left-1/2 transform -translate-x-1/2 bg-white/95 backdrop-blur-md p-4 sm:p-6 rounded-2xl shadow-2xl border border-gray-200 w-[calc(100%-1rem)] max-w-sm text-center z-20 animate-fade-in-up">
        
        <div v-if="!isWaiting">
          <h2 class="text-xl font-black text-gray-800 mb-2">确认候车信息</h2>
          <p class="text-gray-600 mb-4">当前站点：<span class="font-bold text-gray-900 text-lg">{{ selectedStation.nameCN }}</span></p>
          
          <div class="mb-6 text-left bg-gray-50 p-3 rounded-xl border border-gray-100">
            <p class="text-sm font-bold text-gray-700 mb-3">请选择您要乘坐的线路：</p>
            <div class="flex flex-wrap gap-2 justify-center">
              <button
                v-for="line in selectedStation.lines" 
                :key="line"
                @click="selectedLine = line"
                :class="[
                  'px-4 py-2 rounded-lg font-bold text-sm border-2 transition-all active:scale-95',
                  selectedLine === line
                    ? 'border-blue-600 bg-blue-50 text-blue-700' 
                    : 'border-gray-200 bg-white text-gray-500 hover:border-blue-300 hover:text-blue-600'
                ]"
              >
                {{ line }}
              </button>
            </div>
          </div>

          <div class="flex gap-3">
            <button @click="cancelSelection" class="flex-1 py-3 bg-gray-100 text-gray-600 font-bold rounded-xl hover:bg-gray-200 transition-all">
              点错了
            </button>
            <button 
              @click="confirmWaiting" 
              :disabled="!selectedLine"
              class="flex-1 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-400 disabled:cursor-not-allowed transition-all shadow-lg"
            >
              确认乘车
            </button>
          </div>
        </div>

        <div v-else class="space-y-4">
          <div class="animate-pulse flex justify-center items-center gap-2 text-blue-600 mb-2">
            <span class="text-2xl animate-spin">⏳</span>
            <span class="font-bold text-lg">正在为您调度车辆</span>
          </div>
          <div class="bg-blue-50 rounded-lg p-3 border border-blue-100 text-left space-y-2">
            <p class="text-gray-600 text-sm flex justify-between">当前候车：<span class="font-bold text-gray-800">{{ selectedStation.nameCN }}</span></p>
            <p class="text-gray-600 text-sm flex justify-between">目标线路：<span class="font-bold text-blue-600">{{ selectedLine }}</span></p>
            <p class="text-gray-600 text-sm flex justify-between">预计到达: <span class="text-green-600 font-bold">{{ etaText }}</span></p>
          </div>

          <button @click="cancelWaiting" class="w-full py-3 bg-red-50 text-red-600 font-bold rounded-xl hover:bg-red-100 transition-all border border-red-200 active:scale-95">
            撤销乘车 (离开)
          </button>
        </div>

      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue';
import MapCanvas from '../components/MapCanvas.vue';
import axios from 'axios'; // 记得引入 axios，如果你用的是封装的 request.js，可以替换掉这行

const selectedStation = ref(null);
const selectedLine = ref('');
const isWaiting = ref(false);

// 🚀 新增：用来存储真实的预计到达时间
const etaText = ref('计算中...'); 
let etaTimer = null; // 用来存定时器

const handleStationSelect = (station) => {
  if (isWaiting.value) return;
  selectedStation.value = station;
  selectedLine.value = '';
  
  if (station.lines && station.lines.length === 1) {
    selectedLine.value = station.lines[0];
  }
};

const cancelSelection = () => {
  selectedStation.value = null;
  selectedLine.value = '';
};

// 🚀 专门去后端拿 ETA 数据的函数
const fetchETA = async () => {
  if (!selectedStation.value || !selectedLine.value) return;

  try {
    // 把中文线路名转成后端需要的 route_key 格式（如 1号线 → line1_cw）
    const routeKey = getRouteKey(selectedLine.value);
    const url = `/api/eta/${encodeURIComponent(selectedStation.value.nameCN)}?route=${routeKey}`;
    const res = await axios.get(url);
    const data = res.data;

    // 后端返回 { stationId, etaMinutes, busId, message? }
    if (data.etaMinutes !== null && data.etaMinutes !== undefined) {
      etaText.value = `约 ${data.etaMinutes} 分钟`;
    } else {
      etaText.value = data.message || '暂无可用车辆';
    }
  } catch (error) {
    console.error('获取预计到达时间失败:', error);
    etaText.value = '获取失败';
  }
};

// 🚀 1. 在 <script setup> 顶部附近，给这个手机生成一个随机的用户 ID
const currentUserId = ref('user_' + Math.random().toString(36).substring(2, 9));

// 💡 辅助函数：把中文线路名转成后端需要的 route_key
const getRouteKey = (lineName) => {
  if (lineName.includes('1号') || lineName === '1号线') return 'line1_cw';
  if (lineName.includes('2号') || lineName === '2号线') return 'line2_cw';
  if (lineName.includes('教师')) return 'teacher_cw';
  return lineName;
};

// ==========================================
// 🚀 2. 确认乘车 (加入排队) - 终极适配版
// ==========================================
const confirmWaiting = async () => {
  if (!selectedLine.value) return;
  isWaiting.value = true;
  etaText.value = '计算中...';

  try {
    await axios.post('/api/dispatch/passenger_action', {
      user_id: currentUserId.value,
      route_key: getRouteKey(selectedLine.value),
      action: 'join',
      station_id: selectedStation.value.nameCN
    });
    console.log('✅ 已通知后端大脑：加入排队！');
  } catch (error) {
    console.error('❌ 发送排队信息失败:', error);
  }

  fetchETA();
  etaTimer = setInterval(fetchETA, 3000);
};

// ==========================================
// 🚀 3. 撤销乘车 (离开排队) - 优雅降级秒关版
// ==========================================
const cancelWaiting = async () => {
  const stationName = selectedStation.value?.nameCN;
  const lineName = selectedLine.value;

  // UI 瞬间关闭，不卡顿
  isWaiting.value = false;
  selectedStation.value = null;
  selectedLine.value = '';
  if (etaTimer) clearInterval(etaTimer); 

  // 后台悄悄发请求撤销
  if (stationName && lineName) {
    try {
      await axios.post('/api/dispatch/passenger_action', {
        user_id: currentUserId.value,
        route_key: getRouteKey(lineName),
        action: 'leave',
        station_id: stationName
      });
      console.log('✅ 已通知后端大脑：离开排队！');
    } catch (error) {
      console.error('❌ 发送取消排队信息失败:', error);
    }
  }
};

// 🚀 页面销毁时清理定时器，防止内存泄漏
onUnmounted(() => {
  if (etaTimer) clearInterval(etaTimer);
});
</script>

<style scoped>
.animate-fade-in-up {
  animation: fadeInUp 0.3s ease-out forwards;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translate(-50%, 20px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
</style>