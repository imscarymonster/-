<!-- 车辆图标组件 -->
<template>
  <div class="bus-icon" :style="{ left: x + '%', top: y + '%' }">
    🚌
  </div>
</template>

<script setup>
defineProps({
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
})
</script>
