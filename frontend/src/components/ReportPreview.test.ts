import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { RiskWorkbenchModel } from '../product/types'
import ReportPreview from './ReportPreview.vue'

const model: RiskWorkbenchModel = {
  company: {
    id: 'company-001',
    name: '浙江数科控股有限公司',
    industry: '金融科技',
    legalRepresentative: '张三',
    tags: ['金融科技']
  },
  risk: {
    level: 'high',
    score: 86,
    summary: '该企业存在需要复核的风险关系。',
    factors: [{
      id: 'factor-risk',
      level: 'high',
      title: '存在风险事件',
      description: '建议结合证据来源复核。',
      relationIds: ['rel-risk']
    }]
  },
  graph: { nodes: [], edges: [] },
  evidence: [],
  paths: []
}

describe('ReportPreview', () => {
  it('renders a due diligence report preview and emits save action', async () => {
    const wrapper = mount(ReportPreview, {
      props: {
        model
      }
    })

    expect(wrapper.text()).toContain('浙江数科控股有限公司 风险尽调摘要')
    expect(wrapper.text()).toContain('该企业存在需要复核的风险关系。')
    expect(wrapper.text()).toContain('存在风险事件')

    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('save-report')).toEqual([[]])
  })
})
