<template>
  <section class="panel query-workbench">
    <div class="panel-title-row">
      <div>
        <span class="eyebrow">图谱问答</span>
        <h2>统一问答入口</h2>
      </div>
    </div>

    <form class="query-card" @submit.prevent="submitQuery">
      <label for="query-workbench-question">输入问题</label>
      <textarea id="query-workbench-question" v-model="question" name="query-workbench-question" rows="4" />
      <div class="query-footer">
        <span>结合当前企业上下文，生成 AI 回答并保留可审计查询结果。</span>
        <button type="submit" :disabled="loading">{{ loading ? '生成中' : '发送追问' }}</button>
      </div>
    </form>

    <article v-if="loading || result?.answer" class="answer-card">
      <strong>回答</strong>
      <p v-if="loading && !result?.answer" class="answer-waiting">正在生成回答，请稍候...</p>
      <div v-if="result?.answer" class="answer-content" v-html="renderedAnswer"></div>
    </article>

    <article v-if="result" class="answer-card audit-card">
      <strong>审计与可视化</strong>
      <p v-if="result.cypher"><code>{{ result.cypher }}</code></p>
      <small v-for="message in result.messages" :key="message">{{ message }}</small>
      <div v-if="tableRows.length > 0" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-for="column in tableColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in tableRows" :key="rowIndex">
              <td v-for="(cell, cellIndex) in normalizeRow(row)" :key="cellIndex">{{ formatCell(cell) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="hasAuditGraph" class="audit-graph-shell">
        <div class="audit-graph-header">
          <span>真实查询图谱</span>
          <small>由本次审计查询返回的 {{ auditGraphNodeCount }} 个节点、{{ auditGraphEdgeCount }} 条关系生成。</small>
        </div>
        <RiskGraphCanvas
          :nodes="result.graph.nodes"
          :edges="result.graph.edges"
          :highlighted-relation-ids="[]"
          class="audit-graph"
        />
      </div>
    </article>

    <p v-if="error" class="state-panel">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import DOMPurify from 'dompurify'
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { streamUnifiedQa } from '../api/qa'
import type { UnifiedQaResponse } from '../api/types'

const RiskGraphCanvas = defineAsyncComponent(() => import('./RiskGraphCanvas.vue'))

const props = defineProps<{
  companyName: string
}>()

const question = ref('这家公司有哪些投资方和风险点？')
const loading = ref(false)
const result = ref<UnifiedQaResponse | null>(null)
const error = ref('')
let requestSequence = 0

const renderedAnswer = computed(() => renderAnswer(result.value?.answer ?? ''))
const tableColumns = computed(() => result.value?.table?.columns ?? [])
const tableRows = computed(() => result.value?.table?.rows ?? [])
const auditGraphNodeCount = computed(() => result.value?.graph?.nodes.length ?? 0)
const auditGraphEdgeCount = computed(() => result.value?.graph?.edges.length ?? 0)
const hasAuditGraph = computed(() => auditGraphNodeCount.value > 0)

watch(() => props.companyName, () => {
  result.value = null
  error.value = ''
})

async function submitQuery() {
  const value = question.value.trim()
  if (!value || loading.value) {
    return
  }

  const requestId = ++requestSequence
  loading.value = true
  error.value = ''
  result.value = createEmptyResult()
  try {
    await streamUnifiedQa({
      question: `${props.companyName}：${value}`,
      entity: props.companyName,
      companyName: props.companyName
    }, {
      onMetadata: (metadata) => {
        if (requestId !== requestSequence) {
          return
        }
        result.value = mergeStreamResult(result.value, metadata)
      },
      onDelta: (text) => {
        if (requestId !== requestSequence || !text) {
          return
        }
        const current = result.value ?? createEmptyResult()
        result.value = { ...current, answer: `${current.answer}${text}` }
      },
      onDone: (text) => {
        if (requestId !== requestSequence) {
          return
        }
        const current = result.value ?? createEmptyResult()
        result.value = { ...current, answer: text || current.answer }
      },
      onError: (message) => {
        if (requestId === requestSequence) {
          error.value = message
        }
      }
    })
  } catch (err) {
    if (requestId === requestSequence) {
      error.value = err instanceof Error ? err.message : '问答生成失败'
    }
  } finally {
    if (requestId === requestSequence) {
      loading.value = false
    }
  }
}

function createEmptyResult(): UnifiedQaResponse {
  return {
    answer: '',
    cypher: '',
    safety: {},
    table: { columns: [], rows: [] },
    graph: { nodes: [], edges: [] },
    supporting_graph: { nodes: [], edges: [] },
    citations: [],
    document_context: [],
    retrieval: {},
    status: {},
    messages: []
  }
}

function mergeStreamResult(current: UnifiedQaResponse | null, metadata: Partial<UnifiedQaResponse>): UnifiedQaResponse {
  const base = current ?? createEmptyResult()
  return {
    ...base,
    ...metadata,
    answer: base.answer,
    table: metadata.table ?? base.table,
    graph: metadata.graph ?? base.graph,
    supporting_graph: metadata.supporting_graph ?? base.supporting_graph,
    citations: metadata.citations ?? base.citations,
    document_context: metadata.document_context ?? base.document_context,
    retrieval: metadata.retrieval ?? base.retrieval,
    status: metadata.status ?? base.status,
    messages: metadata.messages ?? base.messages
  }
}

function renderAnswer(answer: string) {
  const htmlBlockPattern = /(<!--\s*html-render-start\s*-->[\s\S]*?<!--\s*html-render-end\s*-->)/gi
  const rendered = answer
    .split(htmlBlockPattern)
    .map((part) => {
      if (/^<!--\s*html-render-start\s*-->/i.test(part)) {
        const html = part
          .replace(/^<!--\s*html-render-start\s*-->/i, '')
          .replace(/<!--\s*html-render-end\s*-->$/i, '')
        return sanitizeAnswerHtml(html)
      }

      return renderMarkdownFragment(part)
    })
    .join('')

  return sanitizeAnswerHtml(rendered)
}

function renderMarkdownFragment(value: string) {
  const html: string[] = []
  const htmlBlockPattern = /<(article|section|div|table|ul|ol|dl)(?:\s[^>]*)?>[\s\S]*?<\/\1>/gi
  let cursor = 0

  for (const match of value.matchAll(htmlBlockPattern)) {
    const index = match.index ?? 0
    if (index > cursor) {
      html.push(renderMarkdownTextFragment(value.slice(cursor, index)))
    }
    html.push(sanitizeAnswerHtml(match[0]))
    cursor = index + match[0].length
  }

  if (cursor < value.length) {
    html.push(renderMarkdownTextFragment(value.slice(cursor)))
  }

  return html.join('')
}

function renderMarkdownTextFragment(value: string) {
  const lines = value.replace(/\r\n/g, '\n').split('\n')
  const html: string[] = []
  let listType: 'ul' | 'ol' | '' = ''

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`)
      listType = ''
    }
  }

  for (const line of lines) {
    const heading2 = line.match(/^##\s+(.+)$/)
    const heading3 = line.match(/^###\s+(.+)$/)
    const unordered = line.match(/^\s*[-*]\s+(.+)$/)
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/)

    if (heading2) {
      closeList()
      html.push(`<h2>${renderInlineMarkdown(heading2[1])}</h2>`)
    } else if (heading3) {
      closeList()
      html.push(`<h3>${renderInlineMarkdown(heading3[1])}</h3>`)
    } else if (unordered) {
      if (listType !== 'ul') {
        closeList()
        html.push('<ul>')
        listType = 'ul'
      }
      html.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`)
    } else if (ordered) {
      if (listType !== 'ol') {
        closeList()
        html.push('<ol>')
        listType = 'ol'
      }
      html.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`)
    } else if (line.trim()) {
      closeList()
      html.push(`<p>${renderInlineMarkdown(line)}</p>`)
    } else {
      closeList()
    }
  }

  closeList()
  return html.join('')
}

function sanitizeAnswerHtml(value: string) {
  return DOMPurify.sanitize(value, {
    ALLOWED_TAGS: ['article', 'aside', 'div', 'section', 'p', 'span', 'strong', 'em', 'b', 'i', 'code', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'h2', 'h3', 'h4', 'br', 'a'],
    ALLOWED_ATTR: ['class', 'data-*', 'aria-label', 'href', 'target', 'rel'],
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
  })
}

function renderInlineMarkdown(value: string) {
  return restoreAllowedInlineHtmlTags(escapeHtml(value))
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
}

function restoreAllowedInlineHtmlTags(value: string) {
  return value.replace(/&lt;(\/?(?:span|strong|em|b|i|code|a)(?:\s+.*?)?)&gt;/gi, (_match, tag: string) => {
    const restoredTag = tag
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&amp;/g, '&')
    return `<${restoredTag}>`
  })
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function normalizeRow(row: unknown) {
  if (Array.isArray(row)) {
    return row
  }
  if (typeof row === 'object' && row !== null) {
    return tableColumns.value.map((column) => (row as Record<string, unknown>)[column])
  }
  return [row]
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) {
    return '-'
  }
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
</script>

<style scoped>
.query-workbench {
  display: grid;
  gap: 14px;
}

.query-card {
  display: grid;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(241, 247, 252, 0.86));
  padding: 14px;
}

.query-card label {
  color: var(--muted);
  font-size: 13px;
}

.query-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.query-footer span {
  color: var(--muted);
  font-size: 12px;
}

.answer-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(14, 165, 233, 0.09), rgba(236, 253, 245, 0.62)),
    #ffffff;
  padding: 12px;
}

.answer-content,
.answer-card p {
  margin: 8px 0 0;
  white-space: normal;
  word-break: break-word;
  line-height: 1.7;
}

.answer-waiting {
  color: var(--muted);
  font-size: 13px;
}

.answer-content :deep(p) {
  margin: 8px 0 0;
}

.answer-content :deep(ul),
.answer-content :deep(ol) {
  margin: 8px 0 0;
  padding-left: 20px;
}

.answer-content :deep(code) {
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: 4px;
  background: rgba(14, 165, 233, 0.08);
  padding: 1px 5px;
  color: #075985;
}

.answer-content :deep(a) {
  color: #0e7490;
  font-weight: 700;
  text-decoration: none;
}

.answer-content :deep(a:hover) {
  text-decoration: underline;
}

.audit-card {
  display: grid;
  gap: 10px;
}

.audit-card small {
  color: var(--muted);
}

.audit-graph-shell {
  display: grid;
  gap: 8px;
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.82);
  padding: 10px;
}

.audit-graph-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.audit-graph-header span {
  color: var(--ink);
  font-weight: 800;
}

.table-wrap {
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  border: 1px solid var(--line);
  padding: 8px;
  text-align: left;
  vertical-align: top;
}

.audit-graph {
  min-height: 360px;
}

code {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
