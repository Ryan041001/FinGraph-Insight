import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { saveWatchlistItem } from '../product/storage'
import WatchlistView from './WatchlistView.vue'

const routerLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>'
}

describe('WatchlistView', () => {
  it('shows an empty state when there are no watched companies', () => {
    const wrapper = mount(WatchlistView)

    expect(wrapper.text()).toContain('暂无关注企业')
  })

  it('renders saved companies and removes them from the list', async () => {
    saveWatchlistItem({
      companyName: '浙江数科控股有限公司',
      industry: '金融科技',
      riskLevel: 'high',
      summary: '存在需要复核的风险关系。',
      updatedAt: '2026-05-27T00:00:00.000Z'
    })

    const wrapper = mount(WatchlistView, {
      global: {
        stubs: {
          RouterLink: routerLinkStub
        }
      }
    })

    expect(wrapper.text()).toContain('浙江数科控股有限公司')
    expect(wrapper.text()).toContain('金融科技 · 高风险')
    expect(wrapper.find('a').attributes('href')).toBe('/workbench?company=%E6%B5%99%E6%B1%9F%E6%95%B0%E7%A7%91%E6%8E%A7%E8%82%A1%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8')

    await wrapper.find('button').trigger('click')

    expect(wrapper.text()).toContain('暂无关注企业')
    expect(wrapper.text()).not.toContain('存在需要复核的风险关系。')
  })
})
