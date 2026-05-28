<template>
  <section class="panel risk-summary-panel" :data-risk="risk.level">
    <div class="panel-title-row">
      <span class="eyebrow">风险等级</span>
      <strong class="risk-score">{{ risk.score }}</strong>
    </div>
    <h2>{{ riskLabel }}</h2>
    <p>{{ risk.summary }}</p>
    <div class="risk-factor-list">
      <button
        v-for="factor in risk.factors"
        :key="factor.id"
        type="button"
        class="risk-factor"
        :class="{ 'risk-factor-selected': isSelected(factor) }"
        :disabled="factor.relationIds.length === 0"
        :aria-pressed="isSelected(factor)"
        @click="selectFactor(factor.relationIds)"
      >
        <strong>{{ factor.title }}</strong>
        <span>{{ factor.description }}</span>
        <span v-if="isSelected(factor)" class="selected-note">已筛选关联证据</span>
      </button>
      <p v-if="risk.factors.length === 0" class="muted">{{ emptyFactorText }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
.risk-factor-list {
  display: grid;
  gap: 10px;
}

.risk-factor {
  width: 100%;
  display: grid;
  gap: 4px;
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  text-align: left;
}

.risk-factor:hover:not(:disabled),
.risk-factor-selected {
  border-color: var(--accent);
  background: #f0fdfa;
  color: var(--ink);
}

.risk-factor:disabled {
  cursor: default;
  opacity: 0.72;
}

.selected-note {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
}
</style>
