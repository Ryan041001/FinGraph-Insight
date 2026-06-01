<template>
  <section class="panel query-workbench">
    <div class="panel-title-row">
      <div>
        <span class="eyebrow">模型查询</span>
        <h2>GraphRAG 与 Text2Cypher</h2>
      </div>
    </div>

    <div class="query-grid">
      <form class="query-card" @submit.prevent="submitGraphRag">
        <label>GraphRAG 追问</label>
        <textarea v-model="graphQuestion" rows="4" />
        <button type="submit" :disabled="graphLoading">{{ graphLoading ? '生成中' : '发送追问' }}</button>
        <article v-if="graphAnswer" class="answer-card">
          <strong>回答</strong>
          <p>{{ graphAnswer }}</p>
        </article>
      </form>

      <form class="query-card" @submit.prevent="submitText2Cypher">
        <label>Text2Cypher</label>
        <textarea v-model="cypherQuestion" rows="4" />
        <button type="submit" :disabled="cypherLoading">{{ cypherLoading ? '生成中' : '生成查询' }}</button>
        <article v-if="cypherResult" class="answer-card">
          <strong>Cypher</strong>
          <p><code>{{ cypherResult.cypher }}</code></p>
          <small v-if="cypherResult.note">{{ cypherResult.note }}</small>
        </article>
      </form>
    </div>

    <p v-if="error" class="state-panel">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
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
let requestSequence = 0

watch(() => props.companyName, () => {
  graphAnswer.value = ''
  cypherResult.value = null
})

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

.query-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.answer-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(14, 165, 233, 0.08);
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
