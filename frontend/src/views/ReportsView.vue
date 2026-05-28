<template>
  <section class="page reports-page">
    <div class="page-header">
      <div>
        <h1>研判报告</h1>
        <p>查看已生成的企业风险尽调报告。</p>
      </div>
    </div>

    <div v-if="reports.length === 0" class="panel empty-state">
      暂无研判报告。请先在风险工作台中保存报告。
    </div>

    <div v-else class="reports-layout">
      <aside class="panel list">
        <button
          v-for="report in reports"
          :key="report.id"
          type="button"
          class="report-list-item"
          :class="{ active: selected?.id === report.id }"
          @click="selected = report"
        >
          <strong>{{ report.companyName }}</strong>
          <span>{{ formatTime(report.createdAt) }}</span>
        </button>
      </aside>
      <article v-if="selected" class="panel report-detail">
        <span class="eyebrow">企业风险尽调报告</span>
        <h2>{{ selected.companyName }}</h2>
        <p>{{ selected.summary }}</p>
        <h3>关键风险因素</h3>
        <div class="list">
          <section v-for="(factor, index) in selected.factors" :key="`${factor.title}-${index}`" class="list-item">
            <strong>{{ factor.title }}</strong>
            <p>{{ factor.description }}</p>
          </section>
        </div>
        <h3>证据链</h3>
        <div class="list">
          <section v-for="(item, index) in selected.evidence" :key="`${item.title}-${index}`" class="list-item">
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
            <small>{{ item.source }} ｜ {{ item.date }} ｜ {{ Math.round(item.confidence * 100) }}%</small>
          </section>
        </div>
        <p class="muted">本结果仅用于风险研判辅助，不构成投资建议。</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { loadReports } from '../product/storage'
import type { DueDiligenceReport } from '../product/types'

const reports = ref<DueDiligenceReport[]>(loadReports())
const selected = ref<DueDiligenceReport | null>(reports.value[0] ?? null)

function formatTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.reports-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) 1fr;
  gap: 18px;
  align-items: start;
}

.report-list-item {
  display: grid;
  gap: 4px;
  border: 1px solid var(--line);
  background: #ffffff;
  color: var(--ink);
  text-align: left;
}

.report-list-item span,
.report-detail small {
  color: var(--muted);
}

.report-list-item.active {
  border-color: var(--accent);
  background: #f0fdfa;
}

.report-detail {
  display: grid;
  gap: 12px;
}

.report-detail h3 {
  margin: 10px 0 0;
}

.report-detail p {
  margin: 0;
}

@media (max-width: 900px) {
  .reports-layout {
    grid-template-columns: 1fr;
  }
}
</style>
