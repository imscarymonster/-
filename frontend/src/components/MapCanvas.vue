<template>
  <div class="map-container relative">
    <svg viewBox="0 0 1200 700" class="electronic-map">
      
      <path
        v-for="line in routes"
        :key="line.id"
        :d="line.path"
        :stroke="line.color"
        fill="none"
        :stroke-width="12"
        stroke-linejoin="round"
        stroke-linecap="round"
        class="route-line"
      />

      <g
        v-for="station in stations"
        :key="station.id"
        class="station-group"
        @click="handleStationClick(station)"
      >
        <circle 
          v-if="!station.isTransfer"
          :cx="station.x" 
          :cy="station.y" 
          r="10" 
          fill="#fff" 
          :stroke="station.color" 
          stroke-width="4" 
          class="station-dot" 
        />

        <g v-else class="transfer-capsule">
          <rect 
            :x="station.x - 12" 
            :y="station.y - 25" 
            width="24" 
            height="50" 
            rx="12" 
            fill="#fff" 
            stroke="#6c757d" 
            stroke-width="4" 
          />
          <circle :cx="station.x" :cy="station.y - 12" r="3" fill="#adb5bd" />
          <circle :cx="station.x" :cy="station.y + 12" r="3" fill="#adb5bd" />
        </g>

        <text 
          :x="getTextX(station)" 
          :y="getTextY(station)" 
          :text-anchor="getTextAnchor(station)" 
          class="station-text"
        >
          <tspan :x="getTextX(station)" class="text-cn">
            {{ station.nameCN }}
          </tspan>
          <tspan :x="getTextX(station)" dy="16" class="text-en">
            {{ station.nameEN }}
          </tspan>
        </text>
      </g>
      <template v-if="isAdmin">
  <g>
    <circle r="15" fill="#fff" stroke="#102c4c" stroke-width="4" />
    <text x="-9" y="5" font-size="16">🚌</text>
    <animateMotion 
      dur="24s" 
      repeatCount="indefinite"
      path="M 100 500 L 840 500 L 840 315 L 1000 315 L 1000 500 L 1000 315 L 840 315 L 840 500 L 100 500"
    />
  </g>

  <g>
    <circle r="15" fill="#fff" stroke="#7ab829" stroke-width="4" />
    <text x="-9" y="5" font-size="16">🚌</text>
    <animateMotion 
      dur="18s" 
      repeatCount="indefinite"
      path="M 100 100 L 980 100 Q 1000 100 1000 120 L 1000 265 Q 1000 285 980 285 L 370 285 Q 350 285 350 265 L 350 100 Z"
    />
  </g>
</template>
    </svg>
  </div>
</template>

<script setup>
// 声明我们要向外发射一个叫 stationClick 的事件
const emit = defineEmits(['stationClick']);

defineProps({
  isAdmin: {
    type: Boolean,
    default: false
  }
});
import { ref } from 'vue';

// ---------------------------------
// 1. 严格映射原图的路径拓扑 (修复了你指出的所有走向问题)
// ---------------------------------
const routes = ref([
  { 
    id: 'line2', name: '2号线', color: '#7ab829', 
    path: 'M 100 100 L 980 100 Q 1000 100 1000 120 L 1000 265 Q 1000 285 980 285 L 370 285 Q 350 285 350 265 L 350 100' 
  },
  { 
    id: 'faculty', name: '教师专线', color: '#c42126', 
    // 修复 3: 红线在 X=720 (公共实验楼) 精准停住，绝不往右多出半点
    path: 'M 350 620 L 350 320 Q 350 300 370 300 L 720 300' 
  },
  { 
    id: 'line1', name: '1号线', color: '#102c4c', 
    // 修复 2 & 4: 
    // 线路A (底部主轴): 双创(100) -> 1号食堂(840) -> 向上拐弯切入平行的北体(Y=315)
    // 线路B (十字分支): 会堂(260) -> 向上直行 -> 向右拐弯(先左再下逻辑) -> 一路贯穿北体、游泳馆 -> 下落至自强路
    path: 'M 100 500 L 840 500 L 840 315 M 260 620 L 260 335 Q 260 315 280 315 L 980 315 Q 1000 315 1000 335 L 1000 500' 
  }
]);

const getLineColor = (lineName) => {
  return routes.value.find(r => r.name === lineName)?.color || '#999';
};

// ---------------------------------
// 2. 站点 1:1 像素级定位与排版
// ---------------------------------
const stations = ref([
  // 顶部 (Green) Y=100
  // 修复 1: 名字正式更为“北邮”
  { id: 1, nameCN: '北邮专享楼', nameEN: 'BUPT Exclusive Building', x: 100, y: 100, color: '#7ab829', lines: ['2号线'], textPos: 'bottom' },
  { id: 2, nameCN: '电科专享楼', nameEN: 'UESTC Exclusive Building', x: 200, y: 100, color: '#7ab829', lines: ['2号线'], textPos: 'top' },
  { id: 3, nameCN: '体育场', nameEN: 'Stadium', x: 350, y: 100, color: '#7ab829', lines: ['2号线'], textPos: 'top' },
  { id: 4, nameCN: '图书馆', nameEN: 'Library', x: 540, y: 100, color: '#7ab829', lines: ['2号线'], textPos: 'top' },
  { id: 5, nameCN: '民大专享楼', nameEN: 'MUC Exclusive Building', x: 720, y: 100, color: '#7ab829', lines: ['2号线'], textPos: 'top' },
  { id: 6, nameCN: '黎安书院', nameEN: "Li'an Academy", x: 1000, y: 100, color: '#7ab829', lines: ['2号线'], textPos: 'top' },
  
  // 中部平行枢纽 (Y=300)
  { id: 7, nameCN: '中传专享楼', nameEN: 'CUC Exclusive Building', x: 350, y: 300, isTransfer: true, lines: ['1号线', '2号线', '教师专线'], textPos: 'left' },
  { id: 8, nameCN: '公共教学楼', nameEN: 'Public Teaching Building', x: 540, y: 300, isTransfer: true, lines: ['1号线', '2号线', '教师专线'], textPos: 'top' },
  { id: 9, nameCN: '公共实验楼', nameEN: 'Public Laboratory Building', x: 720, y: 300, isTransfer: true, lines: ['1号线', '2号线', '教师专线'], textPos: 'top' },
  { id: 10, nameCN: '北体专享楼', nameEN: 'BSU Exclusive Building', x: 840, y: 300, isTransfer: true, lines: ['1号线', '2号线'], textPos: 'top' },
  // 修复 4: 游泳馆严丝合缝地插在北体和大学生活动中心之间 (X=920)
  { id: 11, nameCN: '综合体育中心游泳馆', nameEN: 'Natatorium of Complex Sports Gymnasium', x: 920, y: 300, isTransfer: true, lines: ['1号线', '2号线'], textPos: 'bottom' },
  { id: 12, nameCN: '大学生活动中心', nameEN: 'Student Activity Center', x: 1000, y: 300, isTransfer: true, lines: ['1号线', '2号线'], textPos: 'top' },
  
  // 底部 (Blue) Y=500
  { id: 13, nameCN: '双创中心', nameEN: 'Innovation Center', x: 100, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  // 修复 2: 会堂文字移至左侧，防止压线
  { id: 14, nameCN: '会堂', nameEN: 'Auditorium', x: 260, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'left' },
  // 修复 3: 生活一区/二区 2号门分列红线(X=350)两侧，且只归属于1号线
  { id: 15, nameCN: '生活一区2号门', nameEN: 'No.2 Gate Area I', x: 450, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  { id: 16, nameCN: '生活二区2号门', nameEN: 'No.2 Gate Area II', x: 580, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  // 修复 4: 1号食堂放置在拐弯点，其后路线直插上方北体
  { id: 17, nameCN: '1号食堂', nameEN: 'Student Canteen I', x: 840, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  { id: 18, nameCN: '自强路站', nameEN: 'Ziqiang Road Stop', x: 1000, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'right' },
  
  // 底部垂直分支 (Y=620)
  { id: 19, nameCN: '生活一区食堂', nameEN: 'Canteen Area I', x: 260, y: 620, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  { id: 20, nameCN: '立德路站', nameEN: 'Lide Road Stop', x: 350, y: 620, color: '#c42126', lines: ['教师专线'], textPos: 'bottom' },
]);

// 智能文字坐标排版系统
const getTextX = (s) => {
  if (s.textPos === 'left') return s.x - 22;
  if (s.textPos === 'right') return s.x + 22;
  return s.x;
};
const getTextY = (s) => {
  if (s.textPos === 'left' || s.textPos === 'right') return s.y - 4; 
  if (s.textPos === 'top') return s.isTransfer ? s.y - 42 : s.y - 20;
  if (s.textPos === 'bottom') return s.isTransfer ? s.y + 35 : s.y + 24;
  return s.y;
};
const getTextAnchor = (s) => {
  if (s.textPos === 'left') return 'end';
  if (s.textPos === 'right') return 'start';
  return 'middle';
};

// ---------------------------------
// 3. 交互逻辑层
// ---------------------------------

const handleStationClick = (station) => {
  // 提取站点的中文名，通过我们在 118行 定义的 emit 发射出去
  emit('stationClick', station);
};



</script>

<style scoped>
.map-container {
  width: 100%;
  max-width: 1350px;
  margin: 0 auto;
  background-color: #f4f6f9;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid #e9ecef;
}

.electronic-map {
  width: 100%;
  height: auto;
  display: block;
}

.route-line {
  opacity: 0.95;
}

.station-group {
  cursor: pointer;
}

.station-dot, .transfer-capsule rect {
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.station-text {
  user-select: none;
  pointer-events: none; 
}

.text-cn {
  font-size: 14px;
  font-weight: 900;
  fill: #111;
}
.text-en {
  font-size: 10px;
  font-weight: 500;
  fill: #6c757d;
}

.station-group:hover .station-dot {
  r: 13;
  stroke-width: 6;
  filter: drop-shadow(0 0 6px rgba(0,0,0,0.15));
}
.station-group:hover .transfer-capsule rect {
  stroke-width: 6;
  stroke: #343a40;
  filter: drop-shadow(0 0 6px rgba(0,0,0,0.15));
}
.station-group:hover .text-cn {
  fill: #000;
  font-size: 15px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}
</style>