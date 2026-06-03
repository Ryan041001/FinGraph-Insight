<template>
  <section class="panel risk-summary-panel" :data-risk="risk.level">
    <div class="panel-title-row">
      <div class="risk-title">
        <span class="eyebrow">风险等级</span>
        <h2>{{ riskLabel }}</h2>
      </div>
      <div class="risk-score-badge" :class="`score-${risk.level}`">
        <span class="score-label">评分</span>
        <strong>{{ risk.score }}</strong>
      </div>
    </div>
    <p class="risk-summary">{{ risk.summary }}</p>
    <div class="risk-factor-list">
      <button
        v-for="factor in risk.factors"
        :key="factor.id"
        type="button"
        class="risk-factor"
        :class="{ 'risk-factor-selected': isSelected(factor), [`level-${factor.level}`]: true }"
        :disabled="factor.relationIds.length === 0"
        :aria-pressed="isSelected(factor)"
        @click="selectFactor(factor.relationIds)"
      >
        <div class="factor-icon-wrapper">
          <AlertTriangle v-if="factor.level === 'high'" :size="16" />
          <AlertCircle v-else-if="factor.level === 'medium'" :size="16" />
          <CheckCircle2 v-else :size="16" />
        </div>
        <div class="factor-content">
          <strong>{{ factor.title }}</strong>
          <span>{{ factor.description }}</span>
          <span v-if="isSelected(factor)" class="selected-note">已筛选关联证据</span>
        </div>
        <ChevronRight v-if="isSelected(factor)" :size="16" class="selected-arrow" />
      </button>
      <p v-if="risk.factors.length === 0" class="muted empty-factors">{{ emptyFactorText }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight
} from 'lucide-vue-next'
import type { RiskFactor, RiskSummary } from '../product/types'

const props = withDefaults(defineProps<{
  risk: RiskSummary
  selectedRelationIds?: string[]
}>(), {
  selectedRelationIds: () => []
})

const emit = defineEmits<{
  'select-factor': [relationIds: string[]]
}>()

const selectedRelationIdSet = computed(() => new Set(props.selectedRelationIds))

const riskLabel = computed(() => {
  const labels = {
    high: '高风险',
    medium: '中风险',
    low: '低风险',
    unknown: '待补充数据'
  }
  return labels[props.risk.level]
})

const emptyFactorText = computed(() => {
  if (props.risk.level === 'unknown') {
    return '暂无足够数据生成风险因子。'
  }
  if (props.risk.level === 'low') {
    return '暂未发现高风险路径'
  }
  return '暂无可展示风险因子。'
})

function isSelected(factor: RiskFactor) {
  return factor.relationIds.some((relationId) => selectedRelationIdSet.value.has(relationId))
}

function selectFactor(relationIds: string[]) {
  if (relationIds.length === 0) {
    return
  }
  emit('select-factor', relationIds)
}
</script>

<style scoped>
.risk-summary-panel {
  display: grid;
  gap: var(--space-md);
  align-content: start;
  position: relative;
  overflow: hidden;
}

.risk-summary-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: #cbd5e1;
  transition: all var(--transition-base) var(--ease-out);
}

.risk-summary-panel[data-risk="high"]::before {
  background: linear-gradient(90deg, #ef4444, #dc2626);
  box-shadow: 0 1px 4px rgba(239, 68, 68, 0.3);
}

.risk-summary-panel[data-risk="medium"]::before {
  background: linear-gradient(90deg, #f59e0b, #d97706);
  box-shadow: 0 1px 4px rgba(245, 158, 11, 0.3);
}

.risk-summary-panel[data-risk="low"]::before {
  background: linear-gradient(90deg, #10b981, #059669);
  box-shadow: 0 1px 4px rgba(16, 185, 129, 0.3);
}

.risk-summary-panel[data-risk="unknown"]::before {
  background: linear-gradient(90deg, #94a3b8, #64748b);
}

.risk-title {
  display: grid;
  gap: var(--space-xs);
}

.risk-title h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.risk-score-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  height: 52px;
  border-radius: var(--radius-sm);
  padding: var(--space-xs) var(--space-sm);
  text-align: center;
  transition: all var(--transition-base) var(--ease-out);
}

.risk-score-badge:hover {
  transform: scale(1.05);
}

.score-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.8;
}

.risk-score-badge strong {
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
}

.score-high {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(220, 38, 38, 0.08));
  color: #b91c1c;
  box-shadow: var(--shadow-xs);
}

.score-medium {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(217, 119, 6, 0.08));
  color: #b45309;
  box-shadow: var(--shadow-xs);
}

.score-low {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(5, 150, 105, 0.08));
  color: #047857;
  box-shadow: var(--shadow-xs);
}

.score-unknown {
  background: linear-gradient(135deg, rgba(148, 163, 184, 0.15), rgba(100, 116, 139, 0.1));
  color: #475569;
  box-shadow: var(--shadow-xs);
}

.risk-summary {
  margin: 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.6;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.9), rgba(241, 245, 249, 0.7));
  border: 1px solid rgba(203, 213, 225, 0.4);
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.risk-summary:hover {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.85));
  box-shadow: var(--shadow-sm);
}

.risk-factor-list {
  display: grid;
  gap: var(--space-sm);
}

.risk-factor {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  border: 1.5px solid var(--line);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  color: var(--ink);
  text-align: left;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
  cursor: pointer;
}

.risk-factor:hover:not(:disabled) {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateX(3px);
  background: linear-gradient(145deg, rgba(255, 255, 255, 1), rgba(239, 246, 255, 0.95));
}

.risk-factor:active:not(:disabled) {
  transform: translateX(2px);
  box-shadow: var(--shadow-sm);
}

.risk-factor-selected {
  border-color: var(--accent);
  background: linear-gradient(145deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.06));
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15), var(--shadow-sm);
}

.risk-factor-selected:hover:not(:disabled) {
  transform: translateX(4px);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.2), var(--shadow-lg);
}

.risk-factor:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  filter: grayscale(0.3);
}

.factor-icon-wrapper {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
  margin-top: 1px;
  transition: all var(--transition-fast) var(--ease-out);
}

.risk-factor:hover:not(:disabled) .factor-icon-wrapper {
  transform: scale(1.1);
}

.level-high .factor-icon-wrapper {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.2);
}

.level-medium .factor-icon-wrapper {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.2);
}

.level-low .factor-icon-wrapper {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.2);
}

.factor-content {
  display: grid;
  gap: var(--space-xs);
  flex: 1;
  min-width: 0;
}

.factor-content strong {
  font-size: 14px;
  color: #0f172a;
  transition: color var(--transition-fast) var(--ease-out);
}

.risk-factor:hover:not(:disabled) .factor-content strong {
  color: var(--accent);
}

.factor-content span {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.selected-note {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  animation: fadeIn var(--transition-base) var(--ease-out);
}

.selected-arrow {
  color: var(--accent);
  flex-shrink: 0;
  animation: slideIn var(--transition-base) var(--ease-out);
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-4px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.empty-factors {
  text-align: center;
  padding: var(--space-xl);
  font-size: 14px;
}
</style>
