import { describe, expect, it } from 'vitest'
import { plainTextFromMarkdown } from './text'

describe('plainTextFromMarkdown', () => {
  it('removes common markdown markers while preserving readable content', () => {
    expect(plainTextFromMarkdown('## 摘要\n- **风险点**：`担保关系`\n[证据](https://example.com)')).toBe(
      '摘要\n风险点：担保关系\n证据'
    )
  })
})
