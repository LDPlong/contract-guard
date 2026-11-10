import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/laws',
      name: 'laws',
      component: () => import('@/views/LawLibraryView.vue'),
    },
    {
      path: '/review/:docId',
      name: 'review',
      component: () => import('@/views/ReviewView.vue'),
      props: true,
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

export default router
