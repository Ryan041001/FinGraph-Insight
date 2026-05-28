import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { EvidenceItem } from '../product/types'
import EvidenceDrawer from './EvidenceDrawer.vue'

const evidence: EvidenceItem[] = [
  {
    id: 'evidence-risk',
    relationId: 'rel-risk',
    title: '风险事件',
    text: '公开信息显示存在异常担保。',
    source: '图谱来源',
    confidence: 0.92,
    date: '2024-05-01'
  },
  {
    id: 'evidence-investment',
    relationId: 'rel-investment',
    title: '投资',
    text: '披露完成融资。',
    source: '证券时报',
    confidence: 0.88,
    date: '2024-03-15'
  }
]

describe('EvidenceDrawer', () => {
  it('shows all evidence until a relation is selected', () => {
    const wrapper = mount(EvidenceDrawer, {
      props: {
        evidence,
        selectedRelationId: ''
      }
    })

    expect(wrapper.text()).toContain('全部证据')
    expect(wrapper.text()).toContain('风险事件')
    expect(wrapper.text()).toContain('投资')
    expect(wrapper.text()).toContain('证券时报')
  })

  it('filters evidence for the selected relation', () => {
    const wrapper = mount(EvidenceDrawer, {
      props: {
        evidence,
        selectedRelationId: 'rel-risk'
      }
    })

    expect(wrapper.text()).toContain('选中关系证据')
    expect(wrapper.text()).toContain('风险事件')
    expect(wrapper.text()).not.toContain('披露完成融资。')
  })
})
