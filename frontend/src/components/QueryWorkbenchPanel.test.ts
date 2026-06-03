import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { streamUnifiedQa } from '../api/qa'
import QueryWorkbenchPanel from './QueryWorkbenchPanel.vue'
import type { UnifiedQaStreamHandlers } from '../api/qa'

vi.mock('../api/qa', () => ({
  streamUnifiedQa: vi.fn()
}))

const streamUnifiedQaMock = vi.mocked(streamUnifiedQa)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('QueryWorkbenchPanel', () => {
  it('renders one unified question entry without exposing routing modes', () => {
    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    expect(wrapper.text()).toContain('统一问答入口')
    expect(wrapper.find('[role="tablist"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('GraphRAG')
    expect(wrapper.text()).not.toContain('Text2Cypher')
  })

  it('submits one unified question with the current company context and renders audit result', async () => {
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      handlers.onMetadata?.({
        cypher: 'MATCH (c:Company {name: "浙江数科控股有限公司"}) RETURN c',
        safety: {},
        table: { columns: ['c'], rows: [['浙江数科控股有限公司']] },
        graph: { nodes: [], edges: [] },
        status: { rag: 'ok', text2cypher: 'ok' },
        messages: []
      })
      handlers.onDelta?.('**存在')
      handlers.onDelta?.('融资关系。**')
      handlers.onDone?.('**存在融资关系。**')
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(streamUnifiedQaMock).toHaveBeenCalledWith({
      question: '浙江数科控股有限公司：这家公司有哪些投资方和风险点？',
      entity: '浙江数科控股有限公司',
      companyName: '浙江数科控股有限公司'
    }, expect.any(Object))
    expect(wrapper.text()).toContain('存在融资关系。')
    expect(wrapper.text()).toContain('MATCH (c:Company')
    expect(wrapper.text()).toContain('浙江数科控股有限公司')
    expect(wrapper.find('.audit-card table').exists()).toBe(false)
    expect(wrapper.find('.cypher-code').text()).toContain('MATCH')
    expect(wrapper.find('.cypher-token-keyword').text()).toBe('MATCH')
    expect(wrapper.find('.cypher-token-label').text()).toBe(':Company')
    expect(wrapper.find('.cypher-token-property').text()).toBe('name')
  })

  it('shows a waiting prompt while the stream has not emitted answer text yet', async () => {
    const pending = new Promise<void>(() => {})
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      handlers.onMetadata?.({
        table: { columns: [], rows: [] },
        graph: { nodes: [], edges: [] },
        status: { rag: 'pending', text2cypher: 'generated' },
        messages: ['已开始生成回答。']
      })
      await pending
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('正在生成回答，请稍候...')
    expect(wrapper.text()).toContain('已开始生成回答。')
  })

  it('sanitizes controlled inline html while preserving safe content', async () => {
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      const answer = '<!-- html-render-start --><section><strong>风险卡</strong><script>alert(1)</script></section><!-- html-render-end -->'
      handlers.onMetadata?.({
        cypher: '',
        safety: {},
        table: { columns: [], rows: [] },
        graph: { nodes: [], edges: [] },
        status: { rag: 'ok', text2cypher: 'skipped' },
        messages: []
      })
      handlers.onDelta?.(answer)
      handlers.onDone?.(answer)
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.html()).toContain('风险卡')
    expect(wrapper.html()).not.toContain('<script>')
  })

  it('renders safe inline html returned directly by the answer and removes unsafe markup', async () => {
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      const answer = '<article style="border: 1px solid #bae6fd; padding: 8px;"><strong>投资方</strong><span>红杉资本</span><img src=x onerror=alert(1) /></article>'
      handlers.onMetadata?.({
        table: { columns: [], rows: [] },
        graph: { nodes: [], edges: [] },
        status: { rag: 'ok', text2cypher: 'ok' },
        messages: []
      })
      handlers.onDone?.(answer)
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.answer-content article').exists()).toBe(true)
    expect(wrapper.find('.answer-content article').attributes('style')).toContain('border')
    expect(wrapper.text()).toContain('红杉资本')
    expect(wrapper.html()).not.toContain('<img')
    expect(wrapper.html()).not.toContain('onerror')
  })

  it('buffers incomplete streamed html instead of rendering raw tags', async () => {
    let continueStream!: () => void
    const waitForNextChunk = new Promise<void>((resolve) => {
      continueStream = resolve
    })
    const finalAnswer = '<div style="border: 1px solid #bae6fd; padding: 8px;"><strong>风险卡</strong></div>'
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      handlers.onDelta?.('<div style="border: 1px solid #bae6fd; padding: 8px;">')
      await waitForNextChunk
      handlers.onDelta?.('<strong>风险卡</strong></div>')
      handlers.onDone?.(finalAnswer)
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.answer-content').html()).not.toContain('&lt;div')
    expect(wrapper.find('.answer-content').text()).not.toContain('<div')

    continueStream()
    await flushPromises()

    expect(wrapper.find('.answer-content div').attributes('style')).toContain('border')
    expect(wrapper.text()).toContain('风险卡')
  })

  it('renders a live preview for open marked html fragments', async () => {
    let finishStream!: () => void
    const waitForEndMarker = new Promise<void>((resolve) => {
      finishStream = resolve
    })
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      handlers.onDelta?.('<!-- html-render-start -->&lt;div style="border: 1px solid #bae6fd; padding: 8px;"&gt;<strong>实时预览</strong>')
      await waitForEndMarker
      const finalAnswer = '<!-- html-render-start --><div style="border: 1px solid #bae6fd; padding: 8px;"><strong>实时预览</strong></div><!-- html-render-end -->'
      handlers.onDone?.(finalAnswer)
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('实时预览')
    expect(wrapper.find('.answer-content div').attributes('style')).toContain('border')
    expect(wrapper.text()).not.toContain('html-render-start')
    expect(wrapper.find('.answer-content').html()).not.toContain('&lt;div')

    finishStream()
    await flushPromises()

    expect(wrapper.text()).toContain('实时预览')
    expect(wrapper.find('.answer-content div').attributes('style')).toContain('border')
  })

  it('renders mixed markdown and direct html blocks without leaking markdown markers', async () => {
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      const answer = [
        '## 结论',
        '<div style="border: 1px solid #bae6fd;"><table><tbody><tr><td>红杉资本</td></tr></tbody></table></div>',
        '- **风险点**：当前图谱正常'
      ].join('\n')
      handlers.onMetadata?.({
        table: { columns: [], rows: [] },
        graph: { nodes: [], edges: [] },
        status: { rag: 'ok', text2cypher: 'ok' },
        messages: []
      })
      handlers.onDone?.(answer)
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.answer-content h2').text()).toBe('结论')
    expect(wrapper.find('.answer-content table').text()).toContain('红杉资本')
    expect(wrapper.find('.answer-content li strong').text()).toBe('风险点')
    expect(wrapper.text()).not.toContain('## 结论')
  })

  it('labels and renders the real query graph returned by audit metadata', async () => {
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      handlers.onMetadata?.({
        cypher: 'MATCH (c:Company {name: "星河数据"}) RETURN c',
        safety: {},
        table: {
          columns: ['节点', '类型'],
          rows: [['星河数据', 'Company']]
        },
        graph: {
          nodes: [
            { id: 'company_fixture', label: '星河数据', type: 'Company', properties: {}, risk_level: 'normal' },
            { id: 'event_fixture', label: 'B轮融资事件', type: 'Event', properties: {}, risk_level: 'normal' }
          ],
          edges: [
            {
              id: 'rel_fixture',
              source: 'company_fixture',
              target: 'event_fixture',
              type: 'RECEIVED_FUNDING',
              label: '获得融资',
              confidence: 0.92,
              status: 'confirmed',
              properties: {},
              provenance: {}
            }
          ]
        },
        status: { rag: 'ok', text2cypher: 'ok' },
        messages: ['已在本地图谱执行查询并生成可视化。']
      })
      handlers.onDone?.('已完成。')
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '星河数据'
      },
      global: {
        stubs: {
          RiskGraphCanvas: {
            props: ['nodes', 'edges'],
            template: '<div data-testid="audit-graph">{{ nodes.map((node) => node.label).join(" ") }} {{ edges.length }}</div>'
          }
        }
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('真实查询图谱')
    expect(wrapper.get('[data-testid="audit-graph"]').text()).toContain('星河数据')
    expect(wrapper.get('[data-testid="audit-graph"]').text()).toContain('1')
  })

  it('renders markdown lists, inline code, links, and bold text safely', async () => {
    streamUnifiedQaMock.mockImplementation(async (_payload, handlers: UnifiedQaStreamHandlers) => {
      const answer = '## 结论\n- **风险点**：关注 `担保`。\n- 查看 [证据](https://example.com/risk)'
      handlers.onMetadata?.({
        table: { columns: [], rows: [] },
        graph: { nodes: [], edges: [] },
        status: { rag: 'ok', text2cypher: 'skipped' },
        messages: []
      })
      handlers.onDone?.(answer)
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.answer-content h2').text()).toBe('结论')
    expect(wrapper.find('.answer-content ul').exists()).toBe(true)
    expect(wrapper.find('.answer-content strong').text()).toContain('风险点')
    expect(wrapper.find('.answer-content code').text()).toBe('担保')
    expect(wrapper.find('.answer-content a').attributes('href')).toBe('https://example.com/risk')
  })
})
