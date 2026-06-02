<template>
  <section class="panel query-workbench">
    <div class="panel-title-row">
      <div>
        <span class="eyebrow">图谱问答</span>
        <h2>统一问答入口</h2>
      </div>
    </div>

    <div class="query-mode-tabs" role="tablist" aria-label="问答模式">
      <button
        type="button"
        role="tab"
        :aria-selected="mode === 'graph-rag'"
        :class="{ active: mode === 'graph-rag' }"
        @click="selectMode('graph-rag')"
      >
        GraphRAG
        <span>开放追问</span>
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="mode === 'text2cypher'"
        :class="{ active: mode === 'text2cypher' }"
        @click="selectMode('text2cypher')"
      >
        Text2Cypher
        <span>精确查询</span>
      </button>
    </div>

    <form class="query-card" @submit.prevent="submitActiveQuery">
      <label for="query-workbench-question">{{ modeMeta.label }}</label>
      <textarea id="query-workbench-question" v-model="activeQuestion" name="query-workbench-question" rows="4" />
      <div class="query-footer">
        <span>{{ modeMeta.hint }}</span>
        <button type="submit" :disabled="activeLoading">{{ activeLoading ? '生成中' : modeMeta.action }}</button>
      </div>
    </form>

    <article v-if="mode === 'graph-rag' && graphAnswer" class="answer-card">
      <strong>回答</strong>
      <p>{{ graphAnswer }}</p>
    </article>

    <article v-if="mode === 'text2cypher' && cypherResult" class="answer-card">
      <strong>Cypher</strong>
      <p><code>{{ cypherResult.cypher }}</code></p>
      <small v-if="cypherResult.note">{{ cypherResult.note }}</small>
    </article>

    <p v-if="error" class="state-panel">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { askGraphRag, askText2Cypher } from '../api/qa'
import type { GraphRagResponse, Text2CypherResponse } from '../api/types'
import { plainTextFromMarkdown } from '../product/text'

const props = defineProps<{
  companyName: string
}>()

const graphQuestion = ref('这家公司有哪些投资方和风险点？')
const cypherQuestion = ref('查询这家公司的投资方和融资事件')
const graphLoading = ref(false)
const cypherLoading = ref(false)
const graphAnswer = ref('')
const cypherResult = ref<Text2CypherResponse | null>(null)
const error = ref('')
const mode = ref<'graph-rag' | 'text2cypher'>('graph-rag')
let requestSequence = 0

const activeQuestion = computed({
  get: () => mode.value === 'graph-rag' ? graphQuestion.value : cypherQuestion.value,
  set: (value: string) => {
    if (mode.value === 'graph-rag') {
      graphQuestion.value = value
    } else {
      cypherQuestion.value = value
    }
  }
})
const activeLoading = computed(() => mode.value === 'graph-rag' ? graphLoading.value : cypherLoading.value)
const modeMeta = computed(() => {
  if (mode.value === 'graph-rag') {
    return {
      label: 'GraphRAG 追问',
      hint: '适合问风险、投资方、证据解释。',
      action: '发送追问'
    }
  }

  return {
    label: 'Text2Cypher',
    hint: '适合生成可审计的只读图查询。',
    action: '生成查询'
  }
})

watch(() => props.companyName, () => {
  graphAnswer.value = ''
  cypherResult.value = null
})

function selectMode(value: 'graph-rag' | 'text2cypher') {
  mode.value = value
  error.value = ''
}

function submitActiveQuery() {
  return mode.value === 'graph-rag' ? submitGraphRag() : submitText2Cypher()
}

async function submitGraphRag() {
  const question = graphQuestion.value.trim()
  if (!question || graphLoading.value) {
    return
  }

  const requestId = ++requestSequence
  graphLoading.value = true
  error.value = ''
  try {
    const result = await askGraphRag(`${props.companyName}：${question}`)
    if (requestId !== requestSequence) {
      return
    }
    graphAnswer.value = normalizeGraphAnswer(result)
  } catch (err) {
    if (requestId === requestSequence) {
      error.value = err instanceof Error ? err.message : 'GraphRAG 查询失败'
    }
  } finally {
    if (requestId === requestSequence) {
      graphLoading.value = false
    }
  }
}

async function submitText2Cypher() {
  const question = cypherQuestion.value.trim()
  if (!question || cypherLoading.value) {
    return
  }

  const requestId = ++requestSequence
  cypherLoading.value = true
  error.value = ''
  try {
    const result = await askText2Cypher(`${props.companyName}：${question}`)
    if (requestId !== requestSequence) {
      return
    }
    cypherResult.value = result
  } catch (err) {
    if (requestId === requestSequence) {
      error.value = err instanceof Error ? err.message : 'Text2Cypher 生成失败'
    }
  } finally {
    if (requestId === requestSequence) {
      cypherLoading.value = false
    }
  }
}

function normalizeGraphAnswer(result: GraphRagResponse) {
  if (typeof result.answer === 'string' && result.answer.trim()) {
    return plainTextFromMarkdown(result.answer)
  }

  return '未获得有效回答，请稍后重试。'
}
</script>

<style scoped>
.query-workbench {
  display: grid;
  gap: 14px;
}

.query-mode-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.query-mode-tabs button {
  display: grid;
  justify-items: start;
  gap: 3px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.74);
  color: #475569;
  min-height: 58px;
  text-align: left;
}

.query-mode-tabs button span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
}

.query-mode-tabs button.active {
  border-color: rgba(14, 143, 179, 0.38);
  background:
    linear-gradient(135deg, rgba(14, 165, 233, 0.13), rgba(99, 102, 241, 0.08)),
    #ffffff;
  color: #075985;
  box-shadow: var(--shadow-sm);
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

.answer-card p {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}

code {
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 980px) {
  .query-grid {
    grid-template-columns: 1fr;
  }
}
</style>
