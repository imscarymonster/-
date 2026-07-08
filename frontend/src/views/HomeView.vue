<template>
  <div class="h-screen bg-gray-100 flex flex-col items-center justify-center space-y-8">
    <h1 class="text-4xl font-black text-gray-800 tracking-wider">🚌 OptiBus 系统入口</h1>
    
    <div class="flex space-x-6">
      <button @click="$router.push('/passenger')" class="w-48 h-48 bg-white rounded-3xl shadow-xl hover:shadow-2xl transition-all flex flex-col items-center justify-center space-y-4 group">
        <span class="text-5xl group-hover:scale-110 transition-transform">🙋‍♂️</span>
        <span class="text-xl font-bold text-gray-700">我是乘客</span>
      </button>
      
      <button @click="$router.push('/driver')" class="w-48 h-48 bg-gray-800 rounded-3xl shadow-xl hover:shadow-2xl transition-all flex flex-col items-center justify-center space-y-4 group">
        <span class="text-5xl group-hover:scale-110 transition-transform">🧑‍✈️</span>
        <span class="text-xl font-bold text-white">我是司机</span>
      </button>

    </div>
  </div>
</template>