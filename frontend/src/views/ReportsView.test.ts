import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { saveReport } from '../product/storage'
import ReportsView from './ReportsView.vue'

function saveReportFixture(id: string, companyName: string, createdAt: string) {
  saveReport({
    id,
    companyName,
    riskLevel: id === 'risk-report' ? 'high' : 'low',
    summary: `${companyName} 风险研判摘要。`,
    factors: [{
      level: id === 'risk-report' ? 'high' : 'low',
      title: `${companyName} 关键风险因素`,
      description: '建议结合证据来源复核。'
    }],
    evidence: [{
      title: '风险事件',
      text: `${companyName} 相关公开证据。`,
      source: '图谱来源',
      confidence: 0.92,
      date: '2024-05-01'
    }],
    createdAt
  })
}

describe('ReportsView', () => {
  it('shows an empty state when there are no reports', () => {
    const wrapper = mount(ReportsView)

    expect(wrapper.text()).toContain('暂无研判报告')
  })

  it('shows saved reports newest first and switches report details', async () => {
    saveReportFixture('old-report', '杭州风控科技有限公司', '2026-05-26T00:00:00.000Z')
    saveReportFixture('risk-report', '浙江数科控股有限公司', '2026-05-27T00:00:00.000Z')

    const wrapper = mount(ReportsView)
    const reportButtons = wrapper.findAll('.report-list-item')

    expect(reportButtons.map((button) => button.text())).toEqual([
      expect.stringContaining('浙江数科控股有限公司'),
      expect.stringContaining('杭州风控科技有限公司')
    ])
    expect(wrapper.find('.report-detail').text()).toContain('浙江数科控股有限公司 风险研判摘要。')
    expect(wrapper.text()).not.toContain('课程项目演示')

    await reportButtons[1].trigger('click')

    expect(wrapper.find('.report-detail').text()).toContain('杭州风控科技有限公司 风险研判摘要。')
    expect(wrapper.find('.report-detail').text()).toContain('杭州风控科技有限公司 相关公开证据。')
  })

  it('deletes the selected report and selects the next available report', async () => {
    saveReportFixture('old-report', '杭州风控科技有限公司', '2026-05-26T00:00:00.000Z')
    saveReportFixture('risk-report', '浙江数科控股有限公司', '2026-05-27T00:00:00.000Z')

    const wrapper = mount(ReportsView)

    await wrapper.find('button.danger').trigger('click')

    expect(wrapper.text()).not.toContain('浙江数科控股有限公司 风险研判摘要。')
    expect(wrapper.find('.report-detail').text()).toContain('杭州风控科技有限公司 风险研判摘要。')
  })
})
