<template>
  <div class="h-screen bg-gray-100 flex overflow-hidden">

    <button
      @click="sidebarOpen = !sidebarOpen"
      class="lg:hidden fixed top-4 left-4 z-30 bg-gray-900 text-white p-2 rounded-lg shadow-lg"
    >
      <span class="text-xl">{{ sidebarOpen ? '✕' : '☰' }}</span>
    </button>

    <div
      :class="[
        'bg-gray-900 text-white p-6 flex flex-col shadow-2xl z-20 transition-all duration-300',
        sidebarOpen ? 'fixed inset-y-0 left-0 w-56 translate-x-0' : 'fixed inset-y-0 left-0 w-56 -translate-x-full',
        'lg:static lg:translate-x-0 lg:w-56 xl:w-64'
      ]"
    >
      <h2 class="text-xl xl:text-2xl font-black tracking-widest text-blue-400 mb-6 xl:mb-10">
        OptiBus <br><span class="text-xs xl:text-sm text-gray-400 font-normal">智能调度总控台</span>
      </h2>

      <nav class="flex flex-col space-y-2 flex-grow">
        <button
          @click="activeTab = 'monitor'; sidebarOpen = false"
          :class="['px-3 xl:px-4 py-3 rounded-lg text-left font-bold transition-all flex items-center gap-2 xl:gap-3 text-sm xl:text-base', activeTab === 'monitor' ? 'bg-blue-600 shadow-md text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200']"
        >
          <span>🗺️</span> 实时监控看板
        </button>
        <button
          @click="activeTab = 'schedule'; sidebarOpen = false"
          :class="['px-3 xl:px-4 py-3 rounded-lg text-left font-bold transition-all flex items-center gap-2 xl:gap-3 text-sm xl:text-base', activeTab === 'schedule' ? 'bg-blue-600 shadow-md text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200']"
        >
          <span>🚌</span> 车辆排班管理
        </button>
        <button
          @click="activeTab = 'warning'; sidebarOpen = false"
          :class="['px-3 xl:px-4 py-3 rounded-lg text-left font-bold transition-all flex items-center gap-2 xl:gap-3 text-sm xl:text-base', activeTab === 'warning' ? 'bg-blue-600 shadow-md text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200']"
        >
          <span>⚠️</span> 运力重构预警
        </button>
      </nav>

      <button @click="handleLogout" class="mt-auto text-gray-500 hover:text-red-400 font-bold text-xs xl:text-sm text-left transition-colors flex items-center gap-2">
        <span>🚪</span> 安全退出登录
      </button>
    </div>

    <div v-if="sidebarOpen" @click="sidebarOpen = false" class="lg:hidden fixed inset-0 bg-black/50 z-10"></div>

    <div class="flex-1 p-4 sm:p-6 xl:p-8 overflow-y-auto pt-16 lg:pt-8">

      <!-- ============ 监控看板 ============ -->
      <div v-if="activeTab === 'monitor'" class="animate-fade-in">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-6 mb-6">
          <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <p class="text-gray-500 text-sm font-bold mb-3">各线路在线车辆</p>
            <div class="space-y-2">
              <div v-for="b in busCountsList" :key="b.name" class="flex items-center justify-between">
                <span class="text-sm font-bold" :style="{color: b.color}">{{ b.name }}</span>
                <span class="text-xl font-black text-gray-800">{{ b.count }} <span class="text-xs text-gray-400 font-normal">辆</span></span>
              </div>
              <div v-if="busCountsList.length === 0" class="text-gray-400 text-sm">加载中...</div>
            </div>
          </div>
          <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center">
            <div class="text-center">
              <span class="text-3xl">🚧</span>
              <p class="text-gray-400 text-sm font-bold mt-1">平均候车时长功能待开发</p>
            </div>
          </div>
          <div :class="['p-6 rounded-2xl shadow-sm border', congestionList.length > 0 ? 'bg-red-50 border-red-100' : 'bg-white border-gray-100']">
            <p :class="['text-sm font-bold mb-1', congestionList.length > 0 ? 'text-red-500' : 'text-gray-500']">系统运力拥堵预警</p>
            <div v-if="congestionList.length > 0" class="flex items-end space-x-2">
              <span class="text-2xl font-black text-red-600">{{ congestionList.map(c => c.display).join('、') }}</span>
              <span class="text-red-400 font-medium mb-0.5">过载</span>
            </div>
            <div v-else class="flex items-end space-x-2">
              <span class="text-2xl font-black text-green-500">暂无预警</span>
            </div>
          </div>
        </div>
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <h3 class="text-lg font-bold text-gray-800 mb-4">📍 园区全路网实时拓扑图</h3>
          <MapCanvas :isAdmin="true" />
        </div>
      </div>

      <!-- ============ 车辆排班 ============ -->
      <div v-if="activeTab === 'schedule'" class="animate-fade-in bg-white p-8 rounded-2xl shadow-sm border border-gray-100 h-full flex items-center justify-center">
        <div class="text-center">
          <span class="text-6xl">🚧</span>
          <h3 class="text-2xl font-black text-gray-400 mt-4">该功能正在开发中</h3>
          <p class="text-gray-400 mt-2">车辆排班管理即将上线</p>
        </div>
      </div>

      <!-- ============ 运力重构预警 ============ -->
      <div v-if="activeTab === 'warning'" class="animate-fade-in space-y-6">
        <div class="mt-4 p-4 bg-gray-50 rounded-lg">
          <h4 class="font-bold text-gray-700 mb-2">当前各线路排队情况：</h4>
          <div class="flex gap-4">
            <div class="text-sm">1号线: <span class="text-red-600 font-bold">{{ lineStats['line1_cw'] || 0 }} 人</span></div>
            <div class="text-sm">2号线: <span class="text-green-600 font-bold">{{ lineStats['line2_cw'] || 0 }} 人</span></div>
          </div>
        </div>

        <div class="bg-red-50 p-6 rounded-2xl border border-red-200 shadow-sm">
          <h3 class="text-xl font-black text-red-600 mb-2 flex items-center gap-2"><span>🚨</span> 紧急情况：1号线运力告急！</h3>
          <p class="text-gray-700 mb-4">系统检测到 <span class="font-bold">图书馆站、中传专享楼</span> 产生大量滞留乘客，排队人数超阀值。</p>
          <div class="flex flex-wrap gap-3">
            <button @click="simulateMassiveCrowd" class="px-5 py-3 border-2 border-red-600 text-red-600 font-bold rounded-xl hover:bg-red-50 active:scale-95 transition-all flex items-center gap-2">
              <span>⚠️</span> 模拟1号线极端爆满
            </button>
            <button @click="triggerDispatch" :disabled="dispatching" class="px-5 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 disabled:bg-gray-400 active:scale-95 transition-all">
              {{ dispatching ? '调度执行中...' : '📋 授权系统执行调度方案' }}
            </button>
            <button @click="resetLine1" :disabled="resetting" class="px-5 py-3 bg-green-600 text-white font-bold rounded-xl hover:bg-green-700 disabled:bg-gray-400 active:scale-95 transition-all">
              {{ resetting ? '恢复中...' : '✅ 模拟1号线恢复正常' }}
            </button>
          </div>
        </div>

        <div class="bg-white p-8 rounded-2xl shadow-sm border border-gray-100">
          <h3 class="text-lg font-bold text-gray-800 mb-4">系统建议调度方案</h3>
          <ul class="space-y-3 text-gray-600">
            <li class="flex items-center gap-3"><div class="w-2 h-2 rounded-full bg-blue-500"></div> 呼叫 <strong>2号线</strong> 的两辆车立即前往 <strong>1号线</strong> 支援。</li>
            <li class="flex items-center gap-3"><div class="w-2 h-2 rounded-full bg-green-500"></div> 支援车辆到达 <strong>中传专享楼</strong> 后自动变线，无需人工干预。</li>
          </ul>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import axios from 'axios';
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import MapCanvas from '../components/MapCanvas.vue';

const router = useRouter();
const activeTab = ref('monitor');
const sidebarOpen = ref(false);

const handleLogout = () => {
  localStorage.removeItem('adminToken');
  router.push('/login');
};

// ============ 实时数据 ============
const lineStats = ref({});
const congestionList = ref([]);
const busCountsList = ref([]);

const fetchDashboard = async () => {
  try {
    const res = await axios.get('/api/dispatch/dashboard');
    congestionList.value = res.data.congestion || [];
    busCountsList.value = res.data.routeBusCounts || [];
  } catch (err) {
    console.error("获取看板数据失败", err);
  }
};

const fetchLineStats = async () => {
  try {
    const res = await axios.get('/api/dispatch/stats');
    lineStats.value = res.data;
  } catch (err) {
    console.error("获取统计数据失败", err);
  }
};

// ============ 模拟1号线极端爆满 ============
const simulateMassiveCrowd = async () => {
  const confirmMsg = "确定要向【公共教学楼】注入 40 名排队乘客吗？这将立刻触发后端的跨线调度！";
  if (!confirm(confirmMsg)) return;

  console.log("🔥 开始分批注入 40 名乘客...");
  let successCount = 0;
  const BATCH_SIZE = 12;
  const TOTAL = 40;
  const ts = Date.now();

  for (let i = 0; i < TOTAL; i += BATCH_SIZE) {
    const batch = [];
    for (let j = i; j < Math.min(i + BATCH_SIZE, TOTAL); j++) {
      batch.push(
        axios.post('/api/dispatch/passenger_action', {
          user_id: `mock_burst_${ts}_${j}`,
          route_key: 'line1_cw',
          action: 'join',
          station_id: '公共教学楼'
        }).then(() => successCount++)
        .catch(() => {})
      );
    }
    await Promise.all(batch);
    console.log(`  已注入 ${Math.min(i + BATCH_SIZE, TOTAL)}/${TOTAL}`);
  }

  console.log(`🎯 注入完毕！成功 ${successCount}/${TOTAL}`);
  const toast = document.createElement('div');
  toast.innerHTML = `🔥 成功注入 ${successCount} 名排队乘客！后端开始调度...`;
  toast.style.cssText = "position:fixed; top:20px; right:20px; background:#ef4444; color:white; padding:15px 20px; border-radius:8px; z-index:9999; font-weight:bold; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); transition: opacity 0.5s;";
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 500); }, 4000);
};

// ============ 授权系统执行调度方案 ============
const dispatching = ref(false);

const triggerDispatch = async () => {
  dispatching.value = true;
  try {
    const res = await axios.post('/api/dispatch/trigger_scan');
    alert(`✅ 调度扫描已执行！\n${res.data.message || '系统已自动调配车辆。'}`);
  } catch (e) {
    alert('调度执行失败: ' + (e.response?.data?.detail || e.message));
  }
  dispatching.value = false;
};

// ============ 模拟1号线恢复正常 ============
const resetting = ref(false);

const resetLine1 = async () => {
  if (!confirm('确定要清除1号线所有排队乘客，并将调度的车辆归还原线路吗？')) return;
  resetting.value = true;
  try {
    const res = await axios.post('/api/dispatch/reset_line1');
    alert(`✅ ${res.data.message || '1号线已恢复正常！'}`);
    fetchDashboard();
    fetchLineStats();
  } catch (e) {
    alert('恢复失败: ' + (e.response?.data?.detail || e.message));
  }
  resetting.value = false;
};

// ============ 生命周期 ============
onMounted(() => {
  fetchDashboard();
  fetchLineStats();
  setInterval(fetchDashboard, 3000);
  setInterval(fetchLineStats, 3000);
});
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
