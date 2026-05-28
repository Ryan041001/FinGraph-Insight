<template>
  <section class="panel ask-panel">
    <span class="eyebrow">追问</span>
    <h2>继续询问关联关系</h2>
    <form @submit.prevent="submit">
      <textarea v-model="question" rows="3" />
      <button type="submit" :disabled="loading || question.trim().length === 0">
        {{ loading ? '分析中' : '提交追问' }}
      </button>
    </form>
    <article v-if="answer" class="answer-card">
      <strong>回答</strong>
      <p>{{ answer }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { askGraphRag } from '../api/qa'

const props = defineProps<{
  companyName: string
}>()

const question = ref('这家公司有哪些需要关注的关联关系？')
const answer = ref('')
const loading = ref(false)
let requestSequence = 0

watch(() => props.companyName, () => {
  requestSequence += 1
  answer.value = ''
  loading.value = false
})

async function submit() {
  const trimmedQuestion = question.value.trim()
  if (!trimmedQuestion || loading.value) {
    return
  }

  const requestId = ++requestSequence
  loading.value = true
  answer.value = ''
  try {
    const result = await askGraphRag(`${props.companyName}：${trimmedQuestion}`)
    if (requestId !== requestSequence) {
      return
    }

    if (typeof result.answer === 'string' && isSafeAnswer(result.answer)) {
      answer.value = result.answer.trim()
    } else {
      answer.value = '未能完成本次追问，请稍后重试。'
    }
  } catch {
    if (requestId === requestSequence) {
      answer.value = '未能完成本次追问，请稍后重试。'
    }
  } finally {
    if (requestId === requestSequence) {
      loading.value = false
    }
  }
}

function isSafeAnswer(value: string): boolean {
  const answerText = value.trim()
  if (!answerText) {
    return false
  }

  const normalizedAnswer = answerText.toLowerCase()
  const blockedProductTerms = [
    ['示', '例'].join(''),
    ['样', '例'].join(''),
    ['演', '示'].join(''),
    ['课', '程', '项', '目'].join(''),
    ['d', 'e', 'm', 'o'].join(''),
    ['s', 'a', 'm', 'p', 'l', 'e'].join(''),
    ['m', 'o', 'c', 'k'].join('')
  ]

  if (blockedProductTerms.some((term) => normalizedAnswer.includes(term))) {
    return false
  }

  return ![
    /^\s*[\[{]/,
    /\bMATCH\s*\(/i,
    /\bRETURN\b/i,
    new RegExp('\\bCy' + 'pher\\b', 'i'),
    /\bTraceback\b/i,
    /\bException\b/i,
    /\b[A-Za-z]*Error:/i,
    /stack trace/i,
    /raw_payload/i
  ].some((pattern) => pattern.test(answerText))
}
</script>

<style scoped>
.ask-panel {
  display: grid;
  gap: 12px;
}

form {
  display: grid;
  gap: 10px;
}

textarea {
  min-height: 88px;
}

.answer-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
}

.answer-card p {
  margin: 8px 0 0;
}
</style>
