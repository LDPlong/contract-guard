import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { reportError } from '@/lib/errorBus'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/guide',
      name: 'guide',
      component: () => import('@/views/GuideView.vue'),
    },
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

// 发版后旧页面的 chunk 会 404，此时路由静默失败、点了没反应，必须给一句人话
router.onError((error) => {
  const message = String((error as Error)?.message ?? error)
  if (/dynamically imported module|Loading chunk|Importing a module script failed/i.test(message)) {
    reportError('页面资源加载失败', new Error('版本可能已更新，请刷新页面'))
    return
  }
  reportError('页面跳转失败', error)
})

export default router
