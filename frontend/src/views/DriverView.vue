<template>
  <div class="h-screen bg-gray-900 flex flex-col items-center justify-center text-white relative">
    
    <button @click="handleLogout" class="absolute top-6 left-6 text-gray-400 hover:text-white text-xl transition-colors">
      ← 退出排班
    </button>

    <div class="text-center space-y-6">
      <p class="text-3xl text-gray-400 font-bold">当前任务</p>
      <h1 class="text-7xl font-black text-green-500 tracking-widest">
        2号线 <span class="text-5xl text-white">正常行驶</span>
      </h1>
      <p class="text-4xl font-bold mt-10">下一站：体育场</p>
    </div>

    <button @click="simulateDispatch" class="absolute bottom-12 px-8 py-4 bg-red-600 hover:bg-red-500 rounded-full text-xl font-bold transition-all active:scale-95 shadow-lg shadow-red-900">
      ⚠️ 模拟接收后台调度指令 (测试语音)
    </button>
    
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';

const router = useRouter();

// 1. 退出登录逻辑：撕毁通行证，踢回登录页
const handleLogout = () => {
  localStorage.removeItem('driverToken');
  router.push('/login');
};

// 2. 调度语音播报逻辑 (你的原版黑科技)
const simulateDispatch = () => {
  const text = "紧急调度指令：系统检测到1号线客流拥挤。请在送完本车乘客后，立即变更路线，前往1号线支援！";
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'zh-CN';
  utterance.rate = 1.1; // 语速稍快一点，更有调度的感觉
  window.speechSynthesis.speak(utterance);
};
</script>