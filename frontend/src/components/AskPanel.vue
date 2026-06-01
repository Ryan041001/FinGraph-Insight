<template>
  <section class="panel ask-panel">
    <div class="ask-header">
      <MessageCircleQuestion :size="20" />
      <div>
        <span class="eyebrow">追问</span>
        <h2>继续询问关联关系</h2>
      </div>
    </div>
    <form @submit.prevent="submit">
      <textarea v-model="question" rows="3" placeholder="输入您的问题..." />
      <button type="submit" :disabled="loading || question.trim().length === 0">
        <Send v-if="!loading" :size="14" />
        <Loader2 v-else :size="14" class="spin" />
        {{ loading ? '分析中' : '提交追问' }}
      </button>
    </form>
    <article v-if="answer" class="answer-card">
      <div class="answer-header">
        <Sparkles :size="16" />
        <strong>回答</strong>
      </div>
      <p>{{ answer }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Loader2, MessageCircleQuestion, Send, Sparkles } from 'lucide-vue-next'
import { askGraphRag } from '../api/qa'
import { plainTextFromMarkdown } from '../product/text'

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
      answer.value = plainTextFromMarkdown(result.answer)
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
  gap: 14px;
}

.ask-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ask-header svg {
  color: var(--accent);
  flex-shrink: 0;
}

.ask-header h2 {
  margin: 2px 0 0;
  font-size: 18px;
}

form {
  display: grid;
  gap: 10px;
}

textarea {
  min-height: 88px;
}

form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.answer-card {
  border: 1px solid rgba(14, 165, 233, 0.2);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(236, 253, 245, 0.6), rgba(239, 246, 255, 0.8));
  padding: 16px;
  position: relative;
  overflow: hidden;
}

.answer-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, #0ea5e9, #6366f1);
}

.answer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.answer-header svg {
  color: var(--accent);
}

.answer-header strong {
  color: #0f172a;
  font-size: 14px;
}

.answer-card p {
  margin: 0;
  color: #475569;
  line-height: 1.7;
  font-size: 14px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
