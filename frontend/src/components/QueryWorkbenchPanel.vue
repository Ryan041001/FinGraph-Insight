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
        <span>结合当前企业上下文，生成 AI 回答并保留可审计查询语句和图谱。</span>
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
      <div v-if="result.cypher" class="cypher-shell" aria-label="生成的查询语句">
        <div class="cypher-toolbar">
          <span>查询语句</span>
          <small>Cypher</small>
        </div>
        <pre class="cypher-code"><code v-html="highlightedCypher"></code></pre>
      </div>
      <small v-for="message in result.messages" :key="message">{{ message }}</small>
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
const highlightedCypher = computed(() => highlightCypher(result.value?.cypher ?? ''))
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
  return sanitizeAnswerHtml(renderMarkedHtmlFragments(answer))
}

function renderMarkedHtmlFragments(value: string) {
  const html: string[] = []
  let cursor = 0

  while (cursor < value.length) {
    const start = findHtmlRenderMarker(value, 'start', cursor)
    if (!start) {
      html.push(renderMarkdownFragment(trimIncompleteHtmlTail(value.slice(cursor))))
      break
    }

    if (start.index > cursor) {
      html.push(renderMarkdownFragment(trimIncompleteHtmlTail(value.slice(cursor, start.index))))
    }

    const end = findHtmlRenderMarker(value, 'end', start.end)
    const rawHtml = value.slice(start.end, end?.index ?? value.length)
    html.push(renderRawHtmlFragment(rawHtml))

    if (!end) {
      break
    }
    cursor = end.end
  }

  return html.join('')
}

function findHtmlRenderMarker(value: string, type: 'start' | 'end', fromIndex: number) {
  const markerPattern = type === 'start'
    ? /<!--\s*html-render-start\s*-->/gi
    : /<!--\s*html-render-end\s*-->/gi
  markerPattern.lastIndex = fromIndex
  const match = markerPattern.exec(value)
  if (!match) {
    return null
  }
  return {
    index: match.index,
    end: markerPattern.lastIndex
  }
}

function renderRawHtmlFragment(value: string) {
  const decoded = decodeHtmlEntities(value.trim())
  return sanitizeAnswerHtml(trimIncompleteHtmlTag(decoded))
}

function trimIncompleteHtmlTag(value: string) {
  const lastOpenBracket = value.lastIndexOf('<')
  const lastCloseBracket = value.lastIndexOf('>')
  if (lastOpenBracket > lastCloseBracket) {
    return value.slice(0, lastOpenBracket)
  }
  return value
}

function decodeHtmlEntities(value: string) {
  const textarea = document.createElement('textarea')
  textarea.innerHTML = value
  return textarea.value
}

function trimIncompleteHtmlTail(value: string) {
  let cutIndex = value.length
  const markerStartIndex = value.lastIndexOf('<!-- html-render-start')
  const markerEndIndex = value.lastIndexOf('<!-- html-render-end -->')
  if (markerStartIndex > markerEndIndex) {
    cutIndex = Math.min(cutIndex, markerStartIndex)
  }

  const lastOpenBracket = value.lastIndexOf('<')
  const lastCloseBracket = value.lastIndexOf('>')
  if (lastOpenBracket > lastCloseBracket) {
    cutIndex = Math.min(cutIndex, lastOpenBracket)
  }

  const blockTagPattern = /<\/?(article|section|div|details|table|ul|ol|dl)\b[^>]*>/gi
  const stack: Array<{ tag: string; index: number }> = []
  for (const match of value.matchAll(blockTagPattern)) {
    const index = match.index ?? 0
    if (index >= cutIndex) {
      break
    }

    const rawTag = match[0]
    const tag = match[1].toLowerCase()
    if (rawTag.startsWith('</')) {
      const openIndex = stack.map((item) => item.tag).lastIndexOf(tag)
      if (openIndex >= 0) {
        stack.splice(openIndex, 1)
      }
    } else if (!rawTag.endsWith('/>')) {
      stack.push({ tag, index })
    }
  }

  if (stack.length > 0) {
    cutIndex = Math.min(cutIndex, stack[0].index)
  }
  return value.slice(0, cutIndex)
}

function renderMarkdownFragment(value: string) {
  const html: string[] = []
  const htmlBlockPattern = /<(article|section|div|details|table|ul|ol|dl)(?:\s[^>]*)?>[\s\S]*?<\/\1>/gi
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
    ALLOWED_TAGS: ['article', 'aside', 'div', 'section', 'details', 'summary', 'p', 'span', 'strong', 'em', 'b', 'i', 'code', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'h2', 'h3', 'h4', 'br', 'a'],
    ALLOWED_ATTR: ['style', 'href', 'target', 'rel'],
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

function highlightCypher(value: string) {
  const tokenPattern = /("[^"]*"|'[^']*')|(:[A-Za-z_][A-Za-z0-9_]*)|\b(MATCH|RETURN|WHERE|LIMIT|OPTIONAL|WITH|ORDER|BY|ASC|DESC|AND|OR|AS|DISTINCT|CALL|UNWIND)\b|([A-Za-z_][A-Za-z0-9_]*)(?=\s*:)(?=[^{}]*})/gi
  let cursor = 0
  const html: string[] = []

  for (const match of value.matchAll(tokenPattern)) {
    const index = match.index ?? 0
    if (index > cursor) {
      html.push(escapeHtml(value.slice(cursor, index)))
    }

    const token = match[0]
    if (match[1]) {
      html.push(`<span class="cypher-token-string">${escapeHtml(token)}</span>`)
    } else if (match[2]) {
      html.push(`<span class="cypher-token-label">${escapeHtml(token)}</span>`)
    } else if (match[3]) {
      html.push(`<span class="cypher-token-keyword">${escapeHtml(token.toUpperCase())}</span>`)
    } else {
      html.push(`<span class="cypher-token-property">${escapeHtml(token)}</span>`)
    }
    cursor = index + token.length
  }

  if (cursor < value.length) {
    html.push(escapeHtml(value.slice(cursor)))
  }
  return html.join('')
}
</script>

<style scoped>
.query-workbench {
  display: grid;
  gap: var(--space-md);
}

.query-card {
  display: grid;
  gap: var(--space-sm);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(241, 247, 252, 0.86));
  padding: var(--space-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-base) var(--ease-out);
}

.query-card:hover {
  box-shadow: var(--shadow-md);
}

.query-card label {
  color: var(--muted);
  font-size: 13px;
}

.query-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.query-footer span {
  color: var(--muted);
  font-size: 12px;
}

.answer-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(145deg, rgba(14, 165, 233, 0.09), rgba(236, 253, 245, 0.62)),
    #ffffff;
  padding: var(--space-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-base) var(--ease-out);
}

.answer-card:hover {
  box-shadow: var(--shadow-md);
}

.answer-content,
.answer-card p {
  margin: var(--space-sm) 0 0;
  white-space: normal;
  word-break: break-word;
  line-height: 1.7;
}

.answer-waiting {
  color: var(--muted);
  font-size: 13px;
}

.answer-content :deep(p) {
  margin: var(--space-sm) 0 0;
}

.answer-content :deep(ul),
.answer-content :deep(ol) {
  margin: var(--space-sm) 0 0;
  padding-left: var(--space-xl);
}

.answer-content :deep(code) {
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: var(--radius-xs);
  background: rgba(14, 165, 233, 0.08);
  padding: 1px 5px;
  color: #075985;
}

.answer-content :deep(a) {
  color: #0e7490;
  font-weight: 700;
  text-decoration: none;
  transition: color var(--transition-fast) var(--ease-out);
}

.answer-content :deep(a:hover) {
  text-decoration: underline;
  color: var(--accent);
}

.audit-card {
  display: grid;
  gap: var(--space-sm);
}

.audit-card small {
  color: var(--muted);
}

.cypher-shell {
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: var(--radius-lg);
  background: #0f172a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), var(--shadow-md);
}

.cypher-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-sm);
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  padding: var(--space-sm) var(--space-sm);
  color: #e2e8f0;
  font-size: 12px;
  font-weight: 800;
}

.cypher-toolbar small {
  color: #94a3b8;
  font-size: 11px;
  letter-spacing: 0;
  text-transform: uppercase;
}

.cypher-code {
  max-height: 170px;
  margin: 0;
  overflow: auto;
  padding: var(--space-md);
  color: #dbeafe;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.cypher-code code {
  font-family: "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
}

.cypher-code :deep(.cypher-token-keyword) {
  color: #67e8f9;
  font-weight: 800;
}

.cypher-code :deep(.cypher-token-label) {
  color: #fde68a;
}

.cypher-code :deep(.cypher-token-property) {
  color: #86efac;
}

.cypher-code :deep(.cypher-token-string) {
  color: #fca5a5;
}

.audit-graph-shell {
  display: grid;
  gap: var(--space-sm);
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.82);
  padding: var(--space-sm);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-base) var(--ease-out);
}

.audit-graph-shell:hover {
  box-shadow: var(--shadow-md);
}

.audit-graph-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.audit-graph-header span {
  color: var(--ink);
  font-weight: 800;
}

.audit-graph {
  min-height: 360px;
}
</style>
