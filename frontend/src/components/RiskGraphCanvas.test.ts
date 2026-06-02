import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { GraphEdge, GraphNode } from '../api/types'
import RiskGraphCanvas from './RiskGraphCanvas.vue'

const chartMock = vi.hoisted(() => ({
  dispose: vi.fn(),
  off: vi.fn(),
  on: vi.fn(),
  setOption: vi.fn()
}))

const initMock = vi.hoisted(() => vi.fn(() => chartMock))

vi.mock('echarts/core', () => ({
  init: initMock,
  use: vi.fn()
}))

const nodes: GraphNode[] = [
  {
    id: 'company',
    label: '浙江数科控股有限公司',
    type: 'Company',
    risk_level: 'normal',
    properties: {}
  },
  {
    id: 'event',
    label: '异常担保事件',
    type: 'Event',
    risk_level: 'high',
    properties: {}
  }
]

const edges: GraphEdge[] = [
  {
    id: 'rel-risk',
    source: 'company',
    target: 'event',
    type: 'RISK_EVENT',
    label: '风险事件',
    confidence: 0.92,
    status: 'confirmed',
    properties: {},
    provenance: {}
  }
]

describe('RiskGraphCanvas', () => {
  it('renders product-safe graph labels and emits selected edges', () => {
    const wrapper = mount(RiskGraphCanvas, {
      props: {
        nodes,
        edges,
        highlightedRelationIds: ['rel-risk']
      }
    })

    const option = chartMock.setOption.mock.calls[chartMock.setOption.mock.calls.length - 1]?.[0]
    const link = option.series[0].links[0]
    expect(option.series[0].roam).toBe('scale')
    expect(option.series[0].data).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'company', draggable: true }),
      expect.objectContaining({ id: 'event', draggable: true })
    ]))
    expect(option.legend[0].data).toEqual(['企业', '事件'])
    expect(link.label.formatter).toBe('风险事件')
    expect(link.lineStyle.width).toBe(4)
    expect(JSON.stringify(option)).not.toContain('risk_event')
    expect(JSON.stringify(option)).not.toContain('Company')
    expect(JSON.stringify(option)).not.toContain('Event')

    const clickHandler = chartMock.on.mock.calls.find(([eventName]) => eventName === 'click')?.[1]
    clickHandler({ dataType: 'edge', data: { id: 'rel-risk' } })

    expect(wrapper.emitted('select-edge')).toEqual([[edges[0]]])
  })
})
