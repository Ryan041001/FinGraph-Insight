import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { askGraphRag, askText2Cypher } from '../api/qa'
import QueryWorkbenchPanel from './QueryWorkbenchPanel.vue'

vi.mock('../api/qa', () => ({
  askGraphRag: vi.fn(),
  askText2Cypher: vi.fn()
}))

const askGraphRagMock = vi.mocked(askGraphRag)
const askText2CypherMock = vi.mocked(askText2Cypher)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('QueryWorkbenchPanel', () => {
  it('submits Text2Cypher questions with the current company context', async () => {
    askText2CypherMock.mockResolvedValue({
      cypher: 'MATCH (c:Company {name: "浙江数科控股有限公司"}) RETURN c',
      safety: {},
      table: { columns: [], rows: [] },
      graph: { nodes: [], edges: [] }
    })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.findAll('form')[1].trigger('submit')
    await flushPromises()

    expect(askText2CypherMock).toHaveBeenCalledWith('浙江数科控股有限公司：查询这家公司的投资方和融资事件')
  })

  it('submits GraphRAG questions with the current company context', async () => {
    askGraphRagMock.mockResolvedValue({ answer: '存在融资关系。' })

    const wrapper = mount(QueryWorkbenchPanel, {
      props: {
        companyName: '浙江数科控股有限公司'
      }
    })

    await wrapper.findAll('form')[0].trigger('submit')
    await flushPromises()

    expect(askGraphRagMock).toHaveBeenCalledWith('浙江数科控股有限公司：这家公司有哪些投资方和风险点？')
    expect(wrapper.text()).toContain('存在融资关系。')
  })
})
