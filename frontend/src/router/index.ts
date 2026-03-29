import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('@/pages/ChatPage.vue'),
    },
    {
      path: '/shared/:token',
      name: 'shared',
      component: () => import('@/pages/SharedPage.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/pages/AdminPage.vue'),
    },
  ],
})

export default router
