import { createRouter, createWebHistory, type RouterHistory } from 'vue-router'
import ReportsView from './views/ReportsView.vue'
import RiskWorkbench from './views/RiskWorkbench.vue'
import WatchlistView from './views/WatchlistView.vue'

export const productNavItems = [
  { path: '/workbench', label: '风险工作台' },
  { path: '/watchlist', label: '关注清单' },
  { path: '/reports', label: '研判报告' }
] as const

const routeComponents = {
  '/workbench': RiskWorkbench,
  '/watchlist': WatchlistView,
  '/reports': ReportsView
} as const

export function createAppRouter(history: RouterHistory = createWebHistory(import.meta.env.BASE_URL)) {
  return createRouter({
    history,
    routes: [
      { path: '/', redirect: '/workbench' },
      ...productNavItems.map(({ path }) => ({
        path,
        component: routeComponents[path]
      }))
    ]
  })
}
