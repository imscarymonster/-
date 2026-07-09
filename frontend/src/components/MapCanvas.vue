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

        <g v-else class="transfer-capsule" :transform="station.isHorizontal ? `rotate(90 ${station.x} ${station.y})` : ''">
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
      
<template v-if="showBuses">
      <g v-for="bus in activeBuses" :key="bus.busId" class="transition-all duration-500 ease-linear">
        <circle
          :cx="getBusX(bus)"
          :cy="getBusY(bus)"
          r="12"
          fill="#ffffff"
          stroke="#3b82f6"
          stroke-width="4"
          class="shadow-lg"
        />
        <text
          :x="getBusX(bus)"
          :y="getBusY(bus) - 18"
          text-anchor="middle"
          class="text-[10px] font-bold fill-blue-800"
        >
          {{ bus.busId }}
        </text>
      </g>
    </template>
    </svg><div class="absolute bottom-1 sm:bottom-3 right-1 sm:right-3 bg-white/75 backdrop-blur-sm py-1 px-1.5 sm:py-1.5 sm:px-2.5 rounded-lg shadow-sm border border-gray-200/60 flex items-center gap-1.5 sm:gap-3 text-[9px] sm:text-xs font-semibold text-gray-600 pointer-events-none z-20 leading-none">
      <div class="flex items-center gap-1"><div class="w-5 sm:w-7 h-1.5 sm:h-2 bg-[#102c4c] rounded-full"></div>1号线</div>
      <div class="flex items-center gap-1"><div class="w-5 sm:w-7 h-1.5 sm:h-2 bg-[#7ab829] rounded-full"></div>2号线</div>
      <div class="flex items-center gap-1"><div class="w-5 sm:w-7 h-1.5 sm:h-2 bg-[#c42126] rounded-full"></div>教师</div>
      <div class="flex items-center gap-1"><div class="w-2.5 sm:w-3.5 h-2.5 sm:h-3.5 rounded-full border-2 border-[#102c4c] bg-white"></div>站点</div>
      <div class="flex items-center gap-1">
        <div class="w-2 sm:w-3 h-4 sm:h-5 rounded-full border-[1.5px] border-gray-400 bg-white flex flex-col justify-center gap-px items-center">
          <div class="w-0.5 h-0.5 bg-gray-400 rounded-full"></div><div class="w-0.5 h-0.5 bg-gray-400 rounded-full"></div>
        </div>
        换乘
      </div>
    </div>
    
  </div>

</template>

<script setup>
// 1. 合并所有的 Props（开关都在这里）
const props = defineProps({
  showBuses: {
    type: Boolean,
    default: true // 默认显示小蓝圈
  },
  isAdmin: {
    type: Boolean,
    default: false
  }
});

// 2. 声明向外发射的事件
const emit = defineEmits(['stationClick', 'updateBusCount']);

// 3. 引入 Vue 和工具
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';

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
    // 完美还原从左侧下沉，绕过立德路站，再从右侧上浮的真实轨迹
      path: 'M 100 500 L 338 500 Q 342 500 342 508 L 342 620 A 8 8 0 0 0 358 620 L 358 508 Q 358 500 362 500 L 840 500 L 840 315 M 260 620 L 260 335 Q 260 315 280 315 L 980 315 Q 1000 315 1000 335 L 1000 500' 
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
  { id: 15, nameCN: '生活一区2号门', nameEN: 'No.2 Gate Area I', x: 305, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  { id: 16, nameCN: '生活二区2号门', nameEN: 'No.2 Gate Area II', x: 420, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  // 修复 4: 1号食堂放置在拐弯点，其后路线直插上方北体
  { id: 17, nameCN: '1号食堂', nameEN: 'Student Canteen I', x: 840, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  { id: 18, nameCN: '自强路站', nameEN: 'Ziqiang Road Stop', x: 1000, y: 500, color: '#102c4c', lines: ['1号线'], textPos: 'right' },
  
  // 底部垂直分支 (Y=620)
  { id: 19, nameCN: '生活一区食堂', nameEN: 'Canteen Area I', x: 260, y: 620, color: '#102c4c', lines: ['1号线'], textPos: 'bottom' },
  { id: 20, nameCN: '立德路站', nameEN: 'Lide Road Stop', x: 350, y: 620, color: '#c42126', lines: ['1号线', '教师专线'], textPos: 'bottom', isTransfer: true, isHorizontal: true },
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



// ==========================================
// 1. 终极坐标系转换引擎 (来自后端兄弟的降维打击)
// ==========================================
const MIN_X = -924;
const MAX_X = 811;
const MIN_Y = -516;
const MAX_Y = 857;

// 计算总跨度
const SPAN_X = MAX_X - MIN_X; // 1735
const SPAN_Y = MAX_Y - MIN_Y; // 1373

// 前端 SVG 画布的写死尺寸
const SVG_WIDTH = 1200;
const SVG_HEIGHT = 700;

// 计算缩放比例尺
const scaleX = SVG_WIDTH / SPAN_X;
const scaleY = SVG_HEIGHT / SPAN_Y;

// X轴转换：消除负数偏移，再乘以比例尺
const getSvgX = (realX) => {
  return (realX - MIN_X) * scaleX;
};

// Y轴转换：必须用最大值减去真实值 (Y轴翻转)，再乘以比例尺
const getSvgY = (realY) => {
  return (MAX_Y - realY) * scaleY;
};

// ==========================================
// 2. Axios 自动轮询雷达 (每 1.5 秒扫描一次)
// ==========================================
const activeBuses = ref([]); // 用来装后端发来的真车数据
let radarInterval = null;    // 雷达定时器

// 找到你原本获取小车数据的那个函数（比如 fetchBusLocations），在拿到数据后加上这一句：
const fetchBusLocations = async () => {
  try {
    const res = await axios.get('/api/buses/locations');
    activeBuses.value = res.data.buses;
    
    // 🚀 核心新增：把当前数组的长度（有几辆车）发射给外面的父组件！
    emit('updateBusCount', activeBuses.value.length); 
    
  } catch (error) {
    console.error("获取车辆数据失败", error);
  }
};

// 当地图一打开，立刻启动雷达
onMounted(() => {
  fetchBusLocations(); // 先扫第一眼
  radarInterval = setInterval(fetchBusLocations, 800); // 800ms 高频轮询，配合连续 progress 实现平滑移动
});

// 当退出地图时，记得关掉雷达，省电！
onUnmounted(() => {
  if (radarInterval) clearInterval(radarInterval);
});


// ==========================================
// 💡 SVG 原生路径定义 — 每条线路的完整行驶轨迹（匹配 SVG 实际绘制线条）
// ==========================================

// line1 完整 SVG 路径（顺向，匹配后端 line1_cw 的 ROUTES_SEQUENCE）
// 路径沿着 SVG 实际绘制的蓝色线条行进
const LINE1_SVG_PATH = [
  { name: '中传专享楼',     x: 350, y: 300 },  // 0
  { name: null,             x: 350, y: 315 },  // 1  下行到分支线
  { name: null,             x: 358, y: 315 },  // 2  沿分支右行
  { name: null,             x: 358, y: 500 },  // 3  下行到主线(立德路站凹陷东侧)
  { name: '生活二区2号门',   x: 420, y: 500 },  // 4
  { name: '生活一区2号门',   x: 305, y: 500 },  // 5  向左折返
  { name: '会堂',           x: 260, y: 500 },  // 6
  { name: '双创中心',       x: 100, y: 500 },  // 7
  { name: '会堂',           x: 260, y: 500 },  // 8  折返
  { name: null,             x: 260, y: 560 },  // 9  沿垂直线下行
  { name: '生活一区食堂',   x: 260, y: 620 },  // 10
  { name: null,             x: 260, y: 560 },  // 11 上行
  { name: null,             x: 260, y: 500 },  // 12 回到主线
  { name: null,             x: 338, y: 500 },  // 13 沿主线右行
  { name: null,             x: 342, y: 508 },  // 14 凹陷曲线
  { name: null,             x: 342, y: 620 },  // 15 凹陷底部(立德路站)
  { name: null,             x: 358, y: 620 },  // 16 凹陷底部东侧
  { name: null,             x: 358, y: 508 },  // 17 凹陷曲线上行
  { name: null,             x: 362, y: 500 },  // 18 回到主线
  { name: '1号食堂',        x: 840, y: 500 },  // 19
  { name: null,             x: 840, y: 400 },  // 20 沿垂直线段上行
  { name: null,             x: 840, y: 315 },  // 21 到达分支线(北体)
  { name: null,             x: 980, y: 315 },  // 22 沿分支右行
  { name: null,             x: 1000, y: 335 }, // 23 曲线
  { name: '自强路站',       x: 1000, y: 500 }, // 24
  // ---- 折返 ----
  { name: null,             x: 1000, y: 335 }, // 25
  { name: null,             x: 980, y: 315 },  // 26
  { name: null,             x: 840, y: 315 },  // 27
  { name: null,             x: 840, y: 400 },  // 28
  { name: null,             x: 840, y: 500 },  // 29
  { name: null,             x: 362, y: 500 },  // 30
  { name: null,             x: 358, y: 508 },  // 31
  { name: null,             x: 358, y: 620 },  // 32
  { name: null,             x: 342, y: 620 },  // 33
  { name: null,             x: 342, y: 508 },  // 34
  { name: null,             x: 338, y: 500 },  // 35
  { name: null,             x: 350, y: 620 },  // 36 凹陷底部中点(沿教师线走廊上行)
  { name: null,             x: 350, y: 320 },  // 37 沿教师线走廊
  { name: '中传专享楼',     x: 350, y: 300 },  // 38
];

// line1 逆向路径就是顺向的反转
const LINE1_CCW_SVG_PATH = [...LINE1_SVG_PATH].reverse();

// line2 完整 SVG 路径（顺向，匹配后端 line2_cw 的 ROUTES_SEQUENCE）
// 绿线从枢纽出发：上行→左拐至北邮→折返→沿绿线右行→右下曲线→底边左行回枢纽
const LINE2_SVG_PATH = [
  { name: '中传专享楼',          x: 350, y: 300 }, // 0
  { name: null,                  x: 350, y: 265 }, // 1  上到绿线底部拐角
  { name: null,                  x: 350, y: 100 }, // 2  绿线左竖条顶部
  { name: '体育场',              x: 350, y: 100 }, // 3  出发向左
  { name: '电科专享楼',          x: 200, y: 100 }, // 4
  { name: '北邮专享楼',          x: 100, y: 100 }, // 5  左端尽头
  // ---- 折返 ----
  { name: '电科专享楼',          x: 200, y: 100 }, // 6  折返右行
  { name: '体育场',              x: 350, y: 100 }, // 7
  { name: '图书馆',              x: 540, y: 100 }, // 8  继续右行
  { name: '民大专享楼',          x: 720, y: 100 }, // 9
  { name: '黎安书院',            x: 1000, y: 100 }, // 10
  // ---- 右下曲线 ----
  { name: null,                  x: 1000, y: 120 }, // 11
  { name: null,                  x: 1000, y: 265 }, // 12
  // ---- 底边左行（绿线 Y≈285，站点标记在 Y=300） ----
  { name: '大学生活动中心',      x: 1000, y: 285 }, // 13
  { name: '综合体育中心游泳馆',  x: 920, y: 285 },  // 14
  { name: '北体专享楼',          x: 840, y: 285 },  // 15
  { name: '公共实验楼',          x: 720, y: 285 },  // 16
  { name: '公共教学楼',          x: 540, y: 285 },  // 17
  { name: null,                  x: 370, y: 285 },  // 18
  { name: null,                  x: 350, y: 265 },  // 19 绿线底部拐角
  { name: '中传专享楼',          x: 350, y: 300 },  // 20 回到枢纽
];
const LINE2_CCW_SVG_PATH = [...LINE2_SVG_PATH].reverse();

// 教师专线 SVG 路径（匹配后端 teacher_cw）
// 红线：枢纽↔公共教学楼/公共实验楼（右上），枢纽↔立德路站（南下）
const TEACHER_SVG_PATH = [
  { name: '中传专享楼',   x: 350, y: 300 },
  { name: null,           x: 350, y: 320 },  // 下行接入红线
  { name: null,           x: 370, y: 300 },  // 沿红线曲线右行
  { name: '公共教学楼',   x: 540, y: 300 },
  { name: '公共实验楼',   x: 720, y: 300 },
  // ---- 折返 ----
  { name: '公共教学楼',   x: 540, y: 300 },
  { name: null,           x: 370, y: 300 },
  { name: null,           x: 350, y: 320 },
  { name: '中传专享楼',   x: 350, y: 300 },
  // ---- 立德路站支线 ----
  { name: null,           x: 350, y: 320 },
  { name: null,           x: 350, y: 620 },
  { name: '立德路站',     x: 350, y: 620 },
  // ---- 返回枢纽 ----
  { name: null,           x: 350, y: 320 },
  { name: null,           x: 350, y: 300 },
  { name: '中传专享楼',   x: 350, y: 300 },
];
const TEACHER_CCW_SVG_PATH = [...TEACHER_SVG_PATH].reverse();

const ROUTE_SVG_PATHS = {
  'line1_cw': LINE1_SVG_PATH,
  'line1_ccw': LINE1_CCW_SVG_PATH,
  'line2_cw': LINE2_SVG_PATH,
  'line2_ccw': LINE2_CCW_SVG_PATH,
  'teacher_cw': TEACHER_SVG_PATH,
  'teacher_ccw': TEACHER_CCW_SVG_PATH,
};

// ==========================================
// 💡 沿 SVG 原生路径插值 — 消除"走空白"
// ==========================================

// 预计算 SVG 路径的累计距离（缓存）
const _pathDistanceCache = {};

function _buildPathCache(path) {
  const dists = [0];
  for (let i = 1; i < path.length; i++) {
    const dx = path[i].x - path[i-1].x;
    const dy = path[i].y - path[i-1].y;
    dists.push(dists[i-1] + Math.sqrt(dx*dx + dy*dy));
  }
  return { path, dists, totalLen: dists[dists.length - 1] };
}

function _getPathCache(routeKey) {
  if (!_pathDistanceCache[routeKey]) {
    const path = ROUTE_SVG_PATHS[routeKey];
    if (path) _pathDistanceCache[routeKey] = _buildPathCache(path);
  }
  return _pathDistanceCache[routeKey];
}

function _findStationIndices(path, stationName) {
  const indices = [];
  for (let i = 0; i < path.length; i++) {
    if (path[i].name === stationName) indices.push(i);
  }
  return indices;
}

/**
 * 在 SVG 路径上，找到从 fromStation 到 toStation 之间进度为 progress 的精确坐标。
 * 如果找不到路径，fallback 到简单直线插值。
 */
function _interpolateOnSvgPath(routeKey, fromStation, toStation, progress) {
  const cache = _getPathCache(routeKey);
  if (!cache) return null;

  const { path, dists, totalLen } = cache;

  // 找到 from 和 to 在路径中的位置
  const fromIndices = _findStationIndices(path, fromStation);
  const toIndices = _findStationIndices(path, toStation);

  if (fromIndices.length === 0 || toIndices.length === 0) return null;

  // 找到 from → to 的最近配对（沿着路径前进方向）
  let bestFromIdx = -1, bestToIdx = -1, bestDist = Infinity;
  for (const fi of fromIndices) {
    for (const ti of toIndices) {
      if (ti <= fi) continue; // to 必须在 from 之后
      const segDist = dists[ti] - dists[fi];
      if (segDist > 0 && segDist < bestDist) {
        bestDist = segDist;
        bestFromIdx = fi;
        bestToIdx = ti;
      }
    }
  }

  if (bestFromIdx < 0 || bestToIdx < 0) return null;

  const segStartDist = dists[bestFromIdx];
  const segLen = dists[bestToIdx] - segStartDist;
  if (segLen <= 0) return { x: path[bestFromIdx].x, y: path[bestFromIdx].y };

  const targetDist = segStartDist + segLen * progress;

  // 沿着路径二分查找目标距离对应的坐标
  for (let i = bestFromIdx; i < bestToIdx; i++) {
    if (targetDist >= dists[i] && targetDist <= dists[i+1]) {
      const t = (targetDist - dists[i]) / (dists[i+1] - dists[i] || 1);
      return {
        x: path[i].x + (path[i+1].x - path[i].x) * t,
        y: path[i].y + (path[i+1].y - path[i].y) * t,
      };
    }
  }

  return { x: path[bestToIdx].x, y: path[bestToIdx].y };
}

// 获取站点 SVG 坐标（用于 fallback）
const getStationCoords = (stationName) => {
  const station = stations.value.find(s => s.nameCN === stationName);
  if (!station) return { x: 0, y: 0 };
  return { x: station.x, y: station.y };
};

// 💡 统一入口：优先使用 SVG 路径插值，fallback 到简单直线
const getBusPosition = (bus) => {
  const routeKey = bus.routeKey || '';
  const fromStation = (bus.fromStation || '').trim();
  const toStation = (bus.toStation || '').trim();
  const progress = bus.progress ?? 0.5;

  // 已到站：停在起点站位置
  if (bus.status === 'arrived' || !toStation || fromStation === toStation) {
    return getStationCoords(fromStation);
  }

  // 优先尝试 SVG 路径插值
  if (routeKey && ROUTE_SVG_PATHS[routeKey]) {
    const result = _interpolateOnSvgPath(routeKey, fromStation, toStation, progress);
    if (result) return result;
  }

  // Fallback: 简单直线插值
  const from = getStationCoords(fromStation);
  const to = getStationCoords(toStation);
  return {
    x: from.x + (to.x - from.x) * progress,
    y: from.y + (to.y - from.y) * progress,
  };
};

// 完美桥接给 HTML
const getBusX = (bus) => getBusPosition(bus).x;
const getBusY = (bus) => getBusPosition(bus).y;
  

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