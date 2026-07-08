import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      // 1. 乘客入口：直接设为首页 (无需登录)
      path: '/',
      name: 'Passenger',
      component: () => import('../views/PassengerView.vue')
    },
    {
      // 2. 统一登录页
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue')
    },
    {
      // 3. 管理员大屏 (需要 admin 权限)
      path: '/admin',
      name: 'Admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      // 4. 司机控制台 (需要 driver 权限)
      path: '/driver',
      name: 'Driver',
      component: () => import('../views/DriverView.vue'),
      meta: { requiresAuth: true, role: 'driver' }
    }
  ]
})

// 智能门卫：多角色权限校验
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth) {
    // 检查是不是去司机端
    if (to.meta.role === 'driver') {
      if (localStorage.getItem('driverToken')) {
        next(); // 有司机令牌，放行
      } else {
        next('/login'); // 没令牌，去登录
      }
    } 
    // 检查是不是去管理端
    else if (to.meta.role === 'admin') {
      if (localStorage.getItem('adminToken')) {
        next(); // 有管理员令牌，放行
      } else {
        next('/login'); // 没令牌，去登录
      }
    }
  } else {
    // 乘客页和登录页不需要权限，直接放行
    next();
  }
})

export default router