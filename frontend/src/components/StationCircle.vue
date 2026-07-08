<!-- 站点圆圈组件 -->
<template>
  <div class="station-circle" :style="{ background: color }">
    <span class="station-name">{{ name }}</span>
  </div>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  color: { type: String, default: '#3388FF' },
})
</script>
