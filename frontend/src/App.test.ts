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

    expect(routePaths).toEqual(['/', '/reports', '/watchlist', '/workbench'])
    expect(routePaths).not.toContain('/graph')
    expect(routePaths).not.toContain('/extract')
    expect(routePaths).not.toContain('/qa')
    expect(routePaths).not.toContain('/risk')
    expect(routePaths).not.toContain('/analysis')
    expect(routePaths).not.toContain('/updates')
    expect(routePaths).not.toContain('/dashboard')
  })

  it('redirects root to the workbench', async () => {
    const router = createAppRouter(createMemoryHistory())
    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router]
      }
    })

    expect(router.currentRoute.value.path).toBe('/workbench')
    expect(wrapper.find('main h1').text()).toBe('风险工作台')
  })

  it('shows product navigation and hides engineering navigation', async () => {
    const wrapper = await mountAt('/workbench')

    expect(wrapper.text()).toContain('风险工作台')
    expect(wrapper.text()).toContain('关注清单')
    expect(wrapper.text()).toContain('研判报告')
    expect(wrapper.text()).not.toContain('实时抽取')
    expect(wrapper.text()).not.toContain('质量监控')
    expect(wrapper.text()).not.toContain('定时更新')
  })

  it.each([
    ['/workbench', '风险工作台'],
    ['/watchlist', '关注清单'],
    ['/reports', '研判报告']
  ])('renders %s page heading', async (path, heading) => {
    const wrapper = await mountAt(path)

    expect(wrapper.find('main h1').text()).toBe(heading)
  })
})
