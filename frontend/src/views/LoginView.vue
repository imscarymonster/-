<template>
  <div class="h-screen bg-gray-900 flex items-center justify-center">
    <div class="bg-white p-6 sm:p-10 rounded-2xl shadow-2xl w-[calc(100%-2rem)] max-w-sm relative overflow-hidden mx-auto">
      <div class="absolute top-0 left-0 w-full h-2 bg-blue-600"></div>
      
      <h2 class="text-3xl font-black text-gray-800 mb-2">系统登录</h2>
      <p class="text-gray-500 text-sm mb-8">OptiBus 内部员工认证中心</p>
      
      <div class="space-y-5">
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-1">系统账号</label>
          <input 
            v-model="username" 
            type="text" 
            class="w-full px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
            placeholder="管理员(admin) 或 司机(driver01)"
          />
        </div>
        
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-1">登录密码</label>
          <input 
            v-model="password" 
            type="password" 
            class="w-full px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
            placeholder="请输入 123456"
          />
        </div>

        <p v-if="errorMessage" class="text-red-500 text-sm font-bold animate-pulse">{{ errorMessage }}</p>

        <button 
          @click="handleLogin" 
          class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 active:scale-95 transition-all mt-4"
        >
          验证身份并登录
        </button>
      </div>
      </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const username = ref('');
const password = ref('');
const errorMessage = ref('');

const handleLogin = () => {
  if (username.value === 'admin' && password.value === '123456') {
    localStorage.setItem('adminToken', 'optibus-admin-token');
    router.push('/admin');
  } 
  else if (username.value === 'driver01' && password.value === '123456') {
    localStorage.setItem('driverToken', 'optibus-driver-token');
    localStorage.setItem('driverId', 'driver01');
    router.push('/driver');
  } 
  else {
    errorMessage.value = '账号或密码错误，请重试！';
  }
};
</script>