import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import App from './App.vue'
import { createAppRouter } from './router'

describe('App product shell', () => {
  const mountAt = async (path: string) => {
    const router = createAppRouter(createMemoryHistory())
    router.push(path)
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router]
      }
    })
    await flushPromises()

    return wrapper
  }

  it('declares only product routes', () => {
    const router = createAppRouter(createMemoryHistory())
    const routePaths = router.getRoutes().map((route) => route.path).sort()

    expect(routePaths).toEqual(['/', '/extraction', '/market', '/overview', '/reports', '/watchlist', '/workbench'])
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
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/overview')
    expect(wrapper.find('main h1').text()).toBe('金融知识图谱与大模型工作台')
  })

  it('uses page-level lazy route components to keep the first bundle small', () => {
    const router = createAppRouter(createMemoryHistory())

    const productRoutes = router.getRoutes().filter((route) => route.path !== '/' && !route.redirect)

    expect(productRoutes).toHaveLength(5)
    for (const route of productRoutes) {
      expect(typeof route.components?.default).toBe('function')
    }
  })

  it('shows product navigation and hides engineering navigation', async () => {
    const wrapper = await mountAt('/workbench')
    const navText = wrapper.find('nav').text()

    expect(navText).toContain('风险工作台')
    expect(navText).toContain('关注清单')
    expect(navText).toContain('研判报告')
    expect(navText).not.toContain('数据任务')
    expect(navText).not.toContain('抽取实验室')
    expect(navText).not.toContain('行情研判')
  })

  it('redirects the legacy extraction lab route into the workbench flow', async () => {
    const router = createAppRouter(createMemoryHistory())
    router.push('/extraction')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router]
      }
    })
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/workbench')
    expect(wrapper.find('main h1').text()).toBe('风险工作台')
  })

  it.each([
    ['/overview', '金融知识图谱与大模型工作台'],
    ['/workbench', '风险工作台'],
    ['/market', '行情研判'],
    ['/watchlist', '关注清单'],
    ['/reports', '研判报告']
  ])('renders %s page heading', async (path, heading) => {
    const wrapper = await mountAt(path)

    expect(wrapper.find('main h1').text()).toBe(heading)
  })
})
