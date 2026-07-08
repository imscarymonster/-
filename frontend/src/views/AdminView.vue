<template>
  <div class="h-screen bg-gray-100 flex overflow-hidden">
    
    <div class="w-64 bg-gray-900 text-white p-6 flex flex-col shadow-2xl z-10">
      <h2 class="text-2xl font-black tracking-widest text-blue-400 mb-10">
        OptiBus <br><span class="text-sm text-gray-400 font-normal">智能调度总控台</span>
      </h2>
      
      <nav class="flex flex-col space-y-2 flex-grow">
        <button 
          @click="activeTab = 'monitor'" 
          :class="['px-4 py-3 rounded-lg text-left font-bold transition-all flex items-center gap-3', activeTab === 'monitor' ? 'bg-blue-600 shadow-md text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200']"
        >
          <span>🗺️</span> 实时监控看板
        </button>
        
        <button 
          @click="activeTab = 'schedule'" 
          :class="['px-4 py-3 rounded-lg text-left font-bold transition-all flex items-center gap-3', activeTab === 'schedule' ? 'bg-blue-600 shadow-md text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200']"
        >
          <span>🚌</span> 车辆排班管理
        </button>
        
        <button 
          @click="activeTab = 'warning'" 
          :class="['px-4 py-3 rounded-lg text-left font-bold transition-all flex items-center gap-3', activeTab === 'warning' ? 'bg-blue-600 shadow-md text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200']"
        >
          <span>⚠️</span> 运力重构预警
        </button>
      </nav>

      <button @click="handleLogout" class="mt-auto text-gray-500 hover:text-red-400 font-bold text-sm text-left transition-colors flex items-center gap-2">
        <span>🚪</span> 安全退出登录
      </button>
    </div>

    <div class="flex-1 p-8 overflow-y-auto">
      
      <div v-if="activeTab === 'monitor'" class="animate-fade-in">
        <div class="grid grid-cols-3 gap-6 mb-6">
          <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <p class="text-gray-500 text-sm font-bold mb-1">当前在线车辆</p>
            <div class="flex items-end space-x-2"><span class="text-4xl font-black text-gray-800">12</span><span class="text-gray-400 font-medium mb-1">辆</span></div>
          </div>
          <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <p class="text-gray-500 text-sm font-bold mb-1">全网平均候车时长</p>
            <div class="flex items-end space-x-2"><span class="text-4xl font-black text-green-500">4.2</span><span class="text-gray-400 font-medium mb-1">分钟</span></div>
          </div>
          <div class="bg-white p-6 rounded-2xl shadow-sm border border-red-100 bg-red-50">
            <p class="text-red-500 text-sm font-bold mb-1">系统运力拥堵预警</p>
            <div class="flex items-end space-x-2"><span class="text-4xl font-black text-red-600">1号线</span><span class="text-red-400 font-medium mb-1">过载</span></div>
          </div>
        </div>
        
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <h3 class="text-lg font-bold text-gray-800 mb-4">📍 园区全路网实时拓扑图</h3>
          <MapCanvas :isAdmin="true" /> 
        </div>
      </div>

      <div v-if="activeTab === 'schedule'" class="animate-fade-in bg-white p-8 rounded-2xl shadow-sm border border-gray-100 h-full">
        <div class="flex justify-between items-center mb-6">
          <h3 class="text-xl font-black text-gray-800">今日车辆排班计划</h3>
          <button class="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold text-sm hover:bg-blue-700">＋ 新增排班</button>
        </div>
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-gray-50 text-gray-500 text-sm border-b border-gray-200">
              <th class="p-4 rounded-tl-lg">车牌号</th>
              <th class="p-4">负责线路</th>
              <th class="p-4">当班司机</th>
              <th class="p-4">当前状态</th>
              <th class="p-4 rounded-tr-lg">操作</th>
            </tr>
          </thead>
          <tbody class="text-gray-700">
            <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              <td class="p-4 font-bold text-blue-600">京A·BD101</td>
              <td class="p-4"><span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-bold">1号线</span></td>
              <td class="p-4">张师傅 (工号: driver01)</td>
              <td class="p-4"><span class="flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-green-500"></div> 行驶中</span></td>
              <td class="p-4"><button @click="editDriver('京A·BD101')" class="text-blue-500 hover:underline text-sm">编辑</button></td>
            </tr>
            <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              <td class="p-4 font-bold text-green-600">京A·BD202</td>
              <td class="p-4"><span class="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-bold">2号线</span></td>
              <td class="p-4">李师傅 (工号: driver02)</td>
              <td class="p-4"><span class="flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-green-500"></div> 行驶中</span></td>
              <td class="p-4"><button @click="editDriver('京A·BD202')" class="text-blue-500 hover:underline text-sm">编辑</button></td>
            </tr>
            <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              <td class="p-4 font-bold text-gray-600">京A·BD303</td>
              <td class="p-4"><span class="bg-gray-200 text-gray-600 px-2 py-1 rounded text-xs font-bold">待命备勤</span></td>
              <td class="p-4">王师傅 (工号: driver03)</td>
              <td class="p-4"><span class="flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-gray-400"></div> 场站休息</span></td>
              <td class="p-4"><button @click="dispatchVehicle('京A·BD303')" class="text-blue-500 hover:underline text-sm">派车</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="activeTab === 'warning'" class="animate-fade-in space-y-6">
        <div class="bg-red-50 p-6 rounded-2xl border border-red-200 flex justify-between items-center shadow-sm">
          <div>
            <h3 class="text-xl font-black text-red-600 mb-2 flex items-center gap-2"><span>🚨</span> 紧急情况：1号线运力告急！</h3>
            <p class="text-gray-700">系统检测到 <span class="font-bold">图书馆站、中传专享楼</span> 产生大量滞留乘客，排队人数超阀值。</p>
          </div>
          <button @click="sendDispatchAlert" class="px-6 py-3 bg-red-600 text-white rounded-xl font-black text-lg hover:bg-red-700 active:scale-95 shadow-lg shadow-red-600/30 transition-all">
            一键全网派发调度指令
          </button>
        </div>

        <div class="bg-white p-8 rounded-2xl shadow-sm border border-gray-100">
          <h3 class="text-lg font-bold text-gray-800 mb-4">系统建议调度方案</h3>
          <ul class="space-y-3 text-gray-600">
            <li class="flex items-center gap-3"><div class="w-2 h-2 rounded-full bg-blue-500"></div> 建议将场站待命的 <strong>京A·BD303</strong> 立即发往 1号线 支援。</li>
            <li class="flex items-center gap-3"><div class="w-2 h-2 rounded-full bg-green-500"></div> 建议 2号线 <strong>京A·BD202</strong> 卸客后，临时变更线路前往 1号线。</li>
          </ul>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import MapCanvas from '../components/MapCanvas.vue';

const router = useRouter();
// 控制当前显示哪个模块的变量，默认显示 map (监控看板)
const activeTab = ref('monitor'); 

const handleLogout = () => {
  localStorage.removeItem('adminToken');
  router.push('/login');
};

// 模拟发送调度指令
const sendDispatchAlert = () => {
  alert('指令已发送！正在通知所有司机端及调度中心...');
  // 现实中，这里会通过 WebSocket 向后端发送信号，后端再把信号推给所有手机端司机，司机端就会响起那段你写的语音！
};
// 更换司机逻辑
const editDriver = (busPlate) => {
  const newDriver = prompt(`请输入为 ${busPlate} 更换的新司机工号：`);
  if (newDriver) {
    alert(`修改成功！${busPlate} 已指派给工号 ${newDriver}。`);
  }
};

// 派车支援逻辑
const dispatchBus = (busPlate) => {
  const targetLine = prompt(`请确认将待命车辆 ${busPlate} 派往哪条线路（输入 1号线/2号线）：`);
  if (targetLine) {
    alert(`派车指令已下达！${busPlate} 即刻前往 ${targetLine} 支援。`);
  }
};
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