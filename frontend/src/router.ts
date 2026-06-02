import { createRouter, createWebHistory, type RouterHistory } from 'vue-router'

export const productNavItems = [
  { path: '/overview', label: '项目总览' },
  { path: '/workbench', label: '风险工作台' },
  { path: '/data-ops', label: '数据任务' },
  { path: '/watchlist', label: '关注清单' },
  { path: '/reports', label: '研判报告' }
] as const

const routeComponents = {
  '/overview': () => import('./views/OverviewView.vue'),
  '/workbench': () => import('./views/RiskWorkbench.vue'),
  '/market': () => import('./views/MarketInsightView.vue'),
  '/data-ops': () => import('./views/DataOpsView.vue'),
  '/watchlist': () => import('./views/WatchlistView.vue'),
  '/reports': () => import('./views/ReportsView.vue')
} as const

export function createAppRouter(history: RouterHistory = createWebHistory(import.meta.env.BASE_URL)) {
  return createRouter({
    history,
    routes: [
      { path: '/', redirect: '/overview' },
      ...productNavItems.map(({ path }) => ({
        path,
        component: routeComponents[path]
      })),
      {
        path: '/extraction',
        redirect: '/workbench'
      },
      {
        path: '/market',
        component: routeComponents['/market']
      }
    ]
  })
}
