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
        {{ loading ? "分析中" : "提交追问" }}
      </button>
    </form>
    <article v-if="answer" class="answer-card">
      <div class="answer-header">
        <Sparkles :size="16" />
        <strong>回答</strong>
      </div>
      <div class="answer-content" v-html="renderedAnswer"></div>
    </article>
  </section>
</template>

<script setup lang="ts">
import DOMPurify from "dompurify";
import { computed, ref, watch } from "vue";
import {
  Loader2,
  MessageCircleQuestion,
  Send,
  Sparkles,
} from "lucide-vue-next";
import { askGraphRag } from "../api/qa";
import { plainTextFromMarkdown } from "../product/text";

const props = defineProps<{
  companyName: string;
}>();

const question = ref("这家公司有哪些需要关注的关联关系？");
const answer = ref("");
const loading = ref(false);
let requestSequence = 0;
const renderedAnswer = computed(() => renderAnswer(answer.value));

watch(
  () => props.companyName,
  () => {
    requestSequence += 1;
    answer.value = "";
    loading.value = false;
  },
);

async function submit() {
  const trimmedQuestion = question.value.trim();
  if (!trimmedQuestion || loading.value) {
    return;
  }
  const requestId = ++requestSequence;
  loading.value = true;
  answer.value = "";
  try {
    const result = await askGraphRag(
      `${props.companyName}：${trimmedQuestion}`,
    );
    if (requestId !== requestSequence) {
      return;
    }
    if (typeof result.answer === "string" && isSafeAnswer(result.answer)) {
      answer.value = result.answer;
    } else {
      answer.value = "未能完成本次追问，请稍后重试。";
    }
  } catch {
    if (requestId === requestSequence) {
      answer.value = "未能完成本次追问，请稍后重试。";
    }
  } finally {
    if (requestId === requestSequence) {
      loading.value = false;
    }
  }
}

function isSafeAnswer(value: string): boolean {
  const answerText = value.trim();
  if (!answerText) {
    return false;
  }
  const normalizedAnswer = answerText.toLowerCase();
  const blockedProductTerms = [
    ["示", "例"].join(""),
    ["样", "例"].join(""),
    ["演", "示"].join(""),
    ["课", "程", "项", "目"].join(""),
    ["d", "e", "m", "o"].join(""),
    ["s", "a", "m", "p", "l", "e"].join(""),
    ["m", "o", "c", "k"].join(""),
  ];
  if (blockedProductTerms.some((term) => normalizedAnswer.includes(term))) {
    return false;
  }
  return ![
    /^\s*[\[{]/,
    /\bMATCH\s*\(/i,
    /\bRETURN\b/i,
    new RegExp("\\bCy" + "pher\\b", "i"),
    /\bTraceback\b/i,
    /\bException\b/i,
    /\b[A-Za-z]*Error:/i,
    /stack trace/i,
    /raw_payload/i,
  ].some((pattern) => pattern.test(answerText));
}

function renderAnswer(value: string): string {
  if (hasHtmlRenderMarker(value)) {
    return sanitizeAnswerHtml(renderMarkedHtmlFragments(value));
  }
  if (/<[a-z][\s\S]*>/i.test(value)) {
    return sanitizeAnswerHtml(value);
  }
  return renderTextAnswerFragment(value);
}

function hasHtmlRenderMarker(value: string): boolean {
  return /<!--\s*html-render-start\s*-->/i.test(value);
}

function renderMarkedHtmlFragments(value: string): string {
  const html: string[] = [];
  let cursor = 0;

  while (cursor < value.length) {
    const start = findHtmlRenderMarker(value, "start", cursor);
    if (!start) {
      html.push(renderUnmarkedAnswerFragment(value.slice(cursor)));
      break;
    }

    if (start.index > cursor) {
      html.push(renderUnmarkedAnswerFragment(value.slice(cursor, start.index)));
    }

    const end = findHtmlRenderMarker(value, "end", start.end);
    html.push(renderRawHtmlFragment(value.slice(start.end, end?.index ?? value.length)));

    if (!end) {
      break;
    }
    cursor = end.end;
  }

  return html.join("");
}

function findHtmlRenderMarker(value: string, type: "start" | "end", fromIndex: number) {
  const markerPattern = type === "start"
    ? /<!--\s*html-render-start\s*-->/gi
    : /<!--\s*html-render-end\s*-->/gi;
  markerPattern.lastIndex = fromIndex;
  const match = markerPattern.exec(value);
  if (!match) {
    return null;
  }
  return {
    index: match.index,
    end: markerPattern.lastIndex,
  };
}

function renderUnmarkedAnswerFragment(value: string): string {
  if (/<[a-z][\s\S]*>/i.test(value)) {
    return sanitizeAnswerHtml(value);
  }
  return renderTextAnswerFragment(value);
}

function renderRawHtmlFragment(value: string): string {
  return sanitizeAnswerHtml(trimIncompleteHtmlTag(decodeHtmlEntities(value.trim())));
}

function trimIncompleteHtmlTag(value: string): string {
  const lastOpenBracket = value.lastIndexOf("<");
  const lastCloseBracket = value.lastIndexOf(">");
  if (lastOpenBracket > lastCloseBracket) {
    return value.slice(0, lastOpenBracket);
  }
  return value;
}

function decodeHtmlEntities(value: string): string {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = value;
  return textarea.value;
}

function renderTextAnswerFragment(value: string): string {
  return escapeHtml(plainTextFromMarkdown(value)).replace(/\n/g, "<br>");
}

function sanitizeAnswerHtml(value: string): string {
  return DOMPurify.sanitize(value, {
    ALLOWED_TAGS: [
      "article",
      "aside",
      "div",
      "section",
      "details",
      "summary",
      "p",
      "span",
      "small",
      "strong",
      "em",
      "b",
      "i",
      "code",
      "ul",
      "ol",
      "li",
      "dl",
      "dt",
      "dd",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "h2",
      "h3",
      "h4",
      "br",
      "a",
    ],
    ALLOWED_ATTR: ["style", "href", "target", "rel"],
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    FORBID_TAGS: [
      "script",
      "style",
      "iframe",
      "object",
      "embed",
      "img",
      "svg",
      "math",
    ],
    FORBID_ATTR: ["onerror", "onclick", "onload", "onmouseover", "onfocus"],
  });
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
</script>

<style scoped>
.ask-panel {
  display: grid;
  gap: var(--space-md);
}

.ask-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.ask-header svg {
  color: var(--accent);
  flex-shrink: 0;
  transition: transform var(--transition-base) var(--ease-out);
}

.ask-panel:hover .ask-header svg {
  transform: rotate(5deg) scale(1.1);
}

.ask-header h2 {
  margin: 2px 0 0;
  font-size: 18px;
}

form {
  display: grid;
  gap: var(--space-sm);
}

textarea {
  min-height: 88px;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

textarea:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--line-strong);
}

textarea:focus {
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15), var(--shadow-sm);
  border-color: var(--accent);
}

form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base) var(--ease-out);
}

form button:hover:not(:disabled) {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

form button:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

.answer-card {
  border: 1.5px solid rgba(14, 165, 233, 0.25);
  border-radius: var(--radius-lg);
  background: linear-gradient(
    145deg,
    rgba(236, 253, 245, 0.7),
    rgba(239, 246, 255, 0.9)
  );
  padding: var(--space-lg);
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base) var(--ease-out);
  animation: slideDown var(--transition-slow) var(--ease-out);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.answer-card:hover {
  box-shadow: var(--shadow-md);
  border-color: rgba(14, 165, 233, 0.4);
}

.answer-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, #0ea5e9, #6366f1);
  box-shadow: 0 2px 8px rgba(14, 165, 233, 0.3);
}

.answer-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.answer-header svg {
  color: var(--accent);
  animation: sparkle 2s ease-in-out infinite;
}

@keyframes sparkle {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.1); }
}

.answer-header strong {
  color: #0f172a;
  font-size: 14px;
}

.answer-content {
  margin: 0;
  color: #475569;
  line-height: 1.7;
  font-size: 14px;
}

.answer-content :deep(p) {
  margin: var(--space-sm) 0 0;
}

.answer-content :deep(p:first-child) {
  margin-top: 0;
}

.answer-content :deep(.qa-insight-card) {
  margin-top: var(--space-md);
}

.answer-content :deep(table) {
  width: 100%;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
