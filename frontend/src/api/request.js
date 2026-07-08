// frontend/src/api/request.js
import axios from 'axios';

// 创建一个 axios 实例，相当于给所有请求都配了一个“传令官”
const apiClient = axios.create({
  // 这里填后端队友给你的 API 地址，目前留空或者写个 localhost
  baseURL: 'http://localhost:8080/api', 
  timeout: 5000, // 超时时间，防止后端死机导致前端无限转圈
});

export default apiClient;