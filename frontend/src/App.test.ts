import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import App from './App.vue'
import { createAppRouter } from './router'

describe('App product shell', () => {
  const mountAt = async (path: string) => {
    const router = createAppRouter(createMemoryHistory())
    router.push(path)
    await router.isReady()

    return mount(App, {
      global: {
        plugins: [router]
      }
    })
  }

  it('declares only product routes', () => {
    const router = createAppRouter(createMemoryHistory())
    const routePaths = router.getRoutes().map((route) => route.path).sort()

    expect(routePaths).toEqual(['/', '/data-ops', '/extraction', '/market', '/overview', '/reports', '/watchlist', '/workbench'])
    expect(routePaths).not.toContain('/graph')
    expect(routePaths).not.toContain('/qa')
    expect(routePaths).not.toContain('/risk')
    expect(routePaths).not.toContain('/analysis')
    expect(routePaths).not.toContain('/updates')
    expect(routePaths).not.toContain('/dashboard')
  })

  it('redirects root to the overview', async () => {
    const router = createAppRouter(createMemoryHistory())
    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router]
      }
    })

    expect(router.currentRoute.value.path).toBe('/overview')
    expect(wrapper.find('main h1').text()).toBe('金融知识图谱与大模型工作台')
  })

  it('shows product navigation and hides engineering navigation', async () => {
    const wrapper = await mountAt('/workbench')

    expect(wrapper.text()).toContain('风险工作台')
    expect(wrapper.text()).toContain('抽取实验室')
    expect(wrapper.text()).toContain('数据任务')
    expect(wrapper.text()).toContain('关注清单')
    expect(wrapper.text()).toContain('研判报告')
  })

  it.each([
    ['/overview', '金融知识图谱与大模型工作台'],
    ['/workbench', '风险工作台'],
    ['/extraction', '抽取实验室'],
    ['/market', '行情研判'],
    ['/data-ops', '数据与任务'],
    ['/watchlist', '关注清单'],
    ['/reports', '研判报告']
  ])('renders %s page heading', async (path, heading) => {
    const wrapper = await mountAt(path)

    expect(wrapper.find('main h1').text()).toBe(heading)
  })
})
