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

      <div v-if="selectedStation" class="absolute bottom-12 left-1/2 transform -translate-x-1/2 bg-white/95 backdrop-blur-md p-6 rounded-2xl shadow-2xl border border-gray-200 w-96 text-center z-20 animate-fade-in-up">
        
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
            <p class="text-gray-600 text-sm flex justify-between">预计到达：<span class="text-green-600 font-bold">约 3 分钟</span></p>
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
import { ref } from 'vue';
import MapCanvas from '../components/MapCanvas.vue';

const selectedStation = ref(null); // 现在存的是整个站点对象
const selectedLine = ref('');      // 存用户选的具体哪条线
const isWaiting = ref(false);

const handleStationSelect = (station) => {
  if (isWaiting.value) return; 
  
  selectedStation.value = station;
  selectedLine.value = ''; // 每次点新站点，清空上一次选的线路
  
  // 智能体验优化：如果这个站只有 1 条线经过，自动帮乘客选中，省去一次点击！
  if (station.lines && station.lines.length === 1) {
    selectedLine.value = station.lines[0];
  }
};

const cancelSelection = () => {
  selectedStation.value = null;
  selectedLine.value = '';
};

const confirmWaiting = () => {
  if (!selectedLine.value) return; // 没选线路不让点确认
  isWaiting.value = true;
};

const cancelWaiting = () => {
  isWaiting.value = false;
  selectedStation.value = null;
  selectedLine.value = '';
};
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