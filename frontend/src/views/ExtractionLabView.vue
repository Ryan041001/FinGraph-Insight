<template>
  <section class="page extraction-page">
    <div class="page-header">
      <div>
        <h1>抽取实验室</h1>
        <p>用大模型从金融文本中抽取实体、关系和证据，确认后写入图谱。</p>
      </div>
      <div class="toolbar">
        <button type="button" class="secondary" @click="loadExample">
          <FileInput :size="14" />
          填入示例
        </button>
        <button type="button" @click="runExtraction" :disabled="extracting || inputText.trim().length === 0">
          <Sparkles v-if="!extracting" :size="14" />
          <Loader2 v-else :size="14" class="spin" />
          {{ extracting ? '抽取中' : '开始抽取' }}
        </button>
      </div>
    </div>

    <div class="lab-layout">
      <section class="panel input-panel">
        <div class="panel-header">
          <span class="eyebrow">金融文本</span>
          <h2>输入内容</h2>
        </div>
        <textarea v-model="inputText" rows="12" />
        <div class="switch-row">
          <label class="switch-label">
            <input v-model="selfRefine" type="checkbox" />
            <span class="switch-box"></span>
            自修正
          </label>
          <label class="switch-label">
            <input v-model="judge" type="checkbox" />
            <span class="switch-box"></span>
            裁判评分
          </label>
        </div>
        <p class="muted hint">
          <Info :size="14" />
          快速演示建议先关闭自修正和裁判；高质量模式会触发更多模型调用。
        </p>
      </section>

      <section class="panel result-panel">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">结构化结果</span>
            <h2>实体与关系</h2>
          </div>
          <button type="button" class="secondary" @click="writeGraph" :disabled="!payload || importing">
            <Save v-if="!importing" :size="14" />
            <Loader2 v-else :size="14" class="spin" />
            {{ importing ? '写入中' : '写入图谱' }}
          </button>
        </div>

        <div v-if="error" class="state-panel error">
          <AlertCircle :size="16" />
          {{ error }}
        </div>
        <div v-else-if="!payload" class="empty-state">
          <FileSearch :size="40" />
          <p>等待抽取结果</p>
          <span>在左侧输入金融文本并点击开始抽取</span>
        </div>
        <template v-else>
          <div class="result-section">
            <h3 class="section-title">
              <Users :size="16" />
              实体 <span class="count-badge">{{ payload.entities.length }}</span>
            </h3>
            <div class="entity-grid">
              <article v-for="entity in payload.entities" :key="entity.temp_id ?? entity.name" class="entity-card">
                <div class="entity-header">
                  <strong>{{ entity.name }}</strong>
                  <span class="type-badge">{{ entity.type }}</span>
                </div>
                <p>{{ entity.evidence || entity.resolved_name || '暂无证据片段' }}</p>
              </article>
            </div>
          </div>

          <div class="result-section">
            <h3 class="section-title">
              <Link2 :size="16" />
              关系 <span class="count-badge">{{ payload.relationships.length }}</span>
            </h3>
            <div class="relation-list">
              <article
                v-for="relationship in payload.relationships"
                :key="relationship.temp_id ?? `${relationship.head_temp_id}-${relationship.relation}-${relationship.tail_temp_id}`"
                class="relation-card"
                :data-status="relationship.status || 'pending'"
              >
                <div class="relation-header">
                  <strong>{{ relationship.relation }}</strong>
                  <span class="relation-meta">
                    <span class="confidence-tag">{{ confidenceText(relationship.confidence) }}</span>
                    <span class="status-tag">{{ relationship.status || 'pending' }}</span>
                  </span>
                </div>
                <p>{{ relationship.evidence || '暂无证据片段' }}</p>
              </article>
            </div>
          </div>
        </template>
      </section>
    </div>

    <div v-if="importResult" class="panel import-success">
      <CheckCircle2 :size="20" class="success-icon" />
      <div>
        <strong>写入完成</strong>
        <span>新增节点 {{ importResult.nodes_created }}，命中节点 {{ importResult.nodes_matched }}，新增关系 {{ importResult.relationships_created }}。</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  AlertCircle,
  CheckCircle2,
  FileInput,
  FileSearch,
  Info,
  Link2,
  Loader2,
  Save,
  Sparkles,
  Users
} from 'lucide-vue-next'
import { extractText, importGraph } from '../api/extraction'
import type { ExtractionPayload, GraphImportResponse } from '../api/types'

const exampleText = '2024年3月，云链智能科技有限公司完成B轮融资，融资金额2亿元，由国投创业领投，启明创投跟投。本轮资金将主要用于金融风控大模型研发和企业知识图谱平台建设。'

const inputText = ref(exampleText)
const selfRefine = ref(false)
const judge = ref(false)
const extracting = ref(false)
const importing = ref(false)
const error = ref('')
const payload = ref<ExtractionPayload | null>(null)
const importResult = ref<GraphImportResponse | null>(null)

function loadExample() {
  inputText.value = exampleText
}

async function runExtraction() {
  extracting.value = true
  error.value = ''
  importResult.value = null
  try {
    payload.value = await extractText(inputText.value, {
      self_refine: selfRefine.value,
      judge: judge.value,
      mock: false
    })
  } catch (err) {
    payload.value = null
    error.value = err instanceof Error ? err.message : '抽取失败'
  } finally {
    extracting.value = false
  }
}

async function writeGraph() {
  if (!payload.value) {
    return
  }
  importing.value = true
  error.value = ''
  try {
    importResult.value = await importGraph(payload.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '写入失败'
  } finally {
    importing.value = false
  }
}

function confidenceText(value: number | undefined) {
  if (typeof value !== 'number') {
    return '未评分'
  }
  return `${Math.round(value * 100)}%`
}
</script>

<style scoped>
.lab-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: stretch;
}

.input-panel,
.result-panel {
  display: grid;
  gap: 14px;
  align-content: start;
}

.panel-header h2 {
  margin: 4px 0 0;
  font-size: 18px;
}

.input-panel textarea {
  min-height: 360px;
}

.switch-row {
  display: flex;
  gap: 20px;
  align-items: center;
}

.switch-label {
  display: inline-flex;
  gap: 10px;
  align-items: center;
  color: #475569;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.switch-label input {
  width: auto;
  display: none;
}

.switch-box {
  width: 36px;
  height: 20px;
  border-radius: 999px;
  background: #cbd5e1;
  position: relative;
  transition: background 200ms ease;
  flex-shrink: 0;
}

.switch-box::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  transition: transform 200ms ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

.switch-label input:checked + .switch-box {
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
}

.switch-label input:checked + .switch-box::after {
  transform: translateX(16px);
}

.hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 251, 235, 0.6), rgba(254, 249, 195, 0.3));
  border: 1px dashed var(--line);
  font-size: 13px;
}

.hint svg {
  color: var(--accent-2);
  flex-shrink: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 50px 24px;
  text-align: center;
  color: var(--muted);
}

.empty-state svg {
  color: #cbd5e1;
}

.empty-state p {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #475569;
}

.empty-state span {
  font-size: 13px;
}

.result-section {
  display: grid;
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  color: #334155;
}

.section-title svg {
  color: var(--accent);
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 20px;
  border-radius: 999px;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  padding: 0 7px;
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.entity-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: 14px;
  transition: all 180ms ease;
}

.entity-card:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--line-strong);
}

.entity-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.entity-header strong {
  font-size: 15px;
  color: #0f172a;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.08));
  color: #0369a1;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.entity-card p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.relation-list {
  display: grid;
  gap: 10px;
}

.relation-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: 14px;
  transition: all 180ms ease;
  position: relative;
  overflow: hidden;
}

.relation-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  background: #cbd5e1;
}

.relation-card[data-status="approved"]::before {
  background: linear-gradient(180deg, #10b981, #059669);
}

.relation-card[data-status="rejected"]::before {
  background: linear-gradient(180deg, #ef4444, #dc2626);
}

.relation-card[data-status="pending"]::before {
  background: linear-gradient(180deg, #f59e0b, #d97706);
}

.relation-card:hover {
  box-shadow: var(--shadow-sm);
}

.relation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}

.relation-header strong {
  font-size: 15px;
  color: #0f172a;
}

.relation-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.confidence-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(14, 165, 233, 0.1);
  color: #0369a1;
  font-size: 11px;
  font-weight: 700;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  color: #475569;
  font-size: 11px;
  font-weight: 700;
}

.relation-card p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.import-success {
  display: flex;
  gap: 14px;
  align-items: center;
  border-color: rgba(16, 185, 129, 0.3);
  background: linear-gradient(145deg, rgba(236, 253, 245, 0.8), rgba(209, 250, 229, 0.5));
}

.import-success strong {
  display: block;
  color: #047857;
  margin-bottom: 2px;
}

.import-success span {
  color: #059669;
  font-size: 14px;
}

.success-icon {
  color: #10b981;
  flex-shrink: 0;
}

button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 980px) {
  .lab-layout,
  .entity-grid {
    grid-template-columns: 1fr;
  }
}
</style>
