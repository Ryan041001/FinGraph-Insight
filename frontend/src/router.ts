import DataOpsView from './views/DataOpsView.vue'
import ExtractionLabView from './views/ExtractionLabView.vue'
import MarketInsightView from './views/MarketInsightView.vue'
import OverviewView from './views/OverviewView.vue'
import { createRouter, createWebHistory, type RouterHistory } from 'vue-router'
import ReportsView from './views/ReportsView.vue'
import RiskWorkbench from './views/RiskWorkbench.vue'
import WatchlistView from './views/WatchlistView.vue'

export const productNavItems = [
  { path: '/overview', label: '项目总览' },
  { path: '/workbench', label: '风险工作台' },
  { path: '/extraction', label: '抽取实验室' },
  { path: '/market', label: '行情研判' },
  { path: '/data-ops', label: '数据任务' },
  { path: '/watchlist', label: '关注清单' },
  { path: '/reports', label: '研判报告' }
] as const

const routeComponents = {
  '/overview': OverviewView,
  '/workbench': RiskWorkbench,
  '/extraction': ExtractionLabView,
  '/market': MarketInsightView,
  '/data-ops': DataOpsView,
  '/watchlist': WatchlistView,
  '/reports': ReportsView
} as const

export function createAppRouter(history: RouterHistory = createWebHistory(import.meta.env.BASE_URL)) {
  return createRouter({
    history,
    routes: [
      { path: '/', redirect: '/overview' },
      ...productNavItems.map(({ path }) => ({
        path,
        component: routeComponents[path]
      }))
    ]
  })
}
