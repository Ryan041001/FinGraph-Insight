<template>
  <section class="page reports-page">
    <div class="page-header">
      <div>
        <h1>研判报告</h1>
        <p>查看已生成的企业风险尽调报告。</p>
      </div>
      <div v-if="reports.length > 0" class="header-badge">
        <FileText :size="18" />
        {{ reports.length }} 份报告
      </div>
    </div>

    <div v-if="reports.length === 0" class="panel empty-state">
      <FileX :size="48" class="empty-icon" />
      <p>暂无研判报告</p>
      <span>请先在风险工作台中保存报告</span>
    </div>

    <div v-else class="reports-layout">
      <aside class="panel report-list-panel">
        <div class="panel-title-row">
          <span class="eyebrow">报告列表</span>
        </div>
        <div class="report-list">
          <button
            v-for="report in reports"
            :key="report.id"
            type="button"
            class="report-list-item"
            :class="{ active: selected?.id === report.id }"
            @click="selected = report"
          >
            <div class="report-list-icon">
              <FileCheck v-if="selected?.id === report.id" :size="16" />
              <FileText v-else :size="16" />
            </div>
            <div class="report-list-info">
              <strong>{{ report.companyName }}</strong>
              <span>{{ formatTime(report.createdAt) }}</span>
            </div>
          </button>
        </div>
      </aside>
      <article v-if="selected" class="panel report-detail">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">企业风险尽调报告</span>
            <h2>{{ selected.companyName }}</h2>
          </div>
          <button type="button" class="danger" @click="deleteSelectedReport">
            <Trash2 :size="14" />
            删除报告
          </button>
        </div>
        <p class="report-summary">{{ selected.summary }}</p>

        <div class="report-section">
          <h3><AlertTriangle :size="16" /> 关键风险因素</h3>
          <div class="factor-list">
            <section
              v-for="(factor, index) in selected.factors"
              :key="`${factor.title}-${index}`"
              class="factor-card"
              :data-level="factor.level"
            >
              <div class="factor-header">
                <span class="factor-dot" :class="factor.level"></span>
                <strong>{{ factor.title }}</strong>
              </div>
              <p>{{ factor.description }}</p>
            </section>
          </div>
        </div>

        <div class="report-section">
          <h3><Link2 :size="16" /> 证据链</h3>
          <div class="evidence-list">
            <section
              v-for="(item, index) in selected.evidence"
              :key="`${item.title}-${index}`"
              class="evidence-card"
            >
              <strong>{{ item.title }}</strong>
              <p>{{ item.text }}</p>
              <div class="evidence-meta">
                <span><Globe :size="12" /> {{ item.source }}</span>
                <span><Calendar :size="12" /> {{ item.date }}</span>
                <span class="confidence-badge">置信度 {{ Math.round(item.confidence * 100) }}%</span>
              </div>
            </section>
          </div>
        </div>

        <p class="disclaimer">
          <Info :size="14" />
          本结果仅用于风险研判辅助，不构成投资建议。
        </p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  AlertTriangle,
  Calendar,
  FileCheck,
  FileText,
  FileX,
  Globe,
  Info,
  Link2,
  Trash2
} from 'lucide-vue-next'
import { loadReports, removeReport } from '../product/storage'
import type { DueDiligenceReport } from '../product/types'

const reports = ref<DueDiligenceReport[]>(loadReports())
const selected = ref<DueDiligenceReport | null>(reports.value[0] ?? null)

function formatTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function deleteSelectedReport() {
  if (!selected.value) {
    return
  }
  removeReport(selected.value.id)
  reports.value = loadReports()
  selected.value = reports.value[0] ?? null
}
</script>

<style scoped>
.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.08));
  color: #0369a1;
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 600;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 24px;
  text-align: center;
  color: var(--muted);
}

.empty-state p {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #334155;
}

.empty-state span {
  font-size: 14px;
}

.empty-icon {
  color: #cbd5e1;
}

.reports-layout {
  display: grid;
  grid-template-columns: minmax(260px, 340px) 1fr;
  gap: 20px;
  align-items: start;
}

.report-list-panel {
  display: grid;
  gap: 14px;
  align-content: start;
}

.report-list {
  display: grid;
  gap: 8px;
}

.report-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  color: var(--ink);
  text-align: left;
  padding: 12px;
  transition: all 180ms ease;
  cursor: pointer;
}

.report-list-item:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
}

.report-list-item.active {
  border-color: var(--accent);
  background: linear-gradient(145deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.05));
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
}

.report-list-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: rgba(14, 165, 233, 0.1);
  color: var(--accent);
  flex-shrink: 0;
}

.report-list-item.active .report-list-icon {
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #ffffff;
}

.report-list-info {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.report-list-info strong {
  font-size: 14px;
  color: #0f172a;
}

.report-list-info span {
  color: var(--muted);
  font-size: 12px;
}

.report-detail {
  display: grid;
  gap: 20px;
}

.report-detail h2 {
  margin: 0;
  font-size: 22px;
}

.report-summary {
  margin: 0;
  color: #475569;
  line-height: 1.7;
  font-size: 15px;
  padding: 16px;
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(241, 245, 249, 0.88));
  border: 1px solid var(--line);
}

.report-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 15px;
  color: #334155;
}

.report-section h3 svg {
  color: var(--accent-2);
}

.factor-list {
  display: grid;
  gap: 10px;
}

.factor-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: 14px;
  transition: all 180ms ease;
}

.factor-card:hover {
  box-shadow: var(--shadow-sm);
}

.factor-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.factor-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.factor-dot.high {
  background: #ef4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.3);
}

.factor-dot.medium {
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.3);
}

.factor-dot.low {
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.3);
}

.factor-card strong {
  font-size: 14px;
  color: #0f172a;
}

.factor-card p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}

.evidence-list {
  display: grid;
  gap: 10px;
}

.evidence-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: 14px;
  transition: all 180ms ease;
}

.evidence-card:hover {
  box-shadow: var(--shadow-sm);
}

.evidence-card strong {
  font-size: 14px;
  color: #0f172a;
}

.evidence-card p {
  margin: 6px 0 10px;
  color: #475569;
  font-size: 13px;
  line-height: 1.55;
}

.evidence-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.evidence-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.confidence-badge {
  background: rgba(14, 165, 233, 0.1);
  color: #0369a1;
  padding: 3px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.disclaimer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
}

@media (max-width: 900px) {
  .reports-layout {
    grid-template-columns: 1fr;
  }
}
</style>
