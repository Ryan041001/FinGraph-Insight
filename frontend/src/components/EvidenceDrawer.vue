<template>
  <section class="panel evidence-drawer">
    <div class="panel-title-row">
      <div>
        <span class="eyebrow">证据链</span>
        <h2>{{ selectedTitle }}</h2>
      </div>
    </div>
    <div v-if="items.length === 0" class="empty-state">当前关系暂无可展示证据。</div>
    <div v-else class="list" data-testid="evidence-list">
      <article v-for="item in items" :key="item.id" class="list-item evidence-row">
        <div class="evidence-meta">
          <strong>{{ item.title }}</strong>
          <span>{{ Math.round(item.confidence * 100) }}%</span>
        </div>
        <p>{{ item.text }}</p>
        <small>来源：{{ item.source }} ｜ 日期：{{ item.date }} ｜ 置信度：{{ Math.round(item.confidence * 100) }}%</small>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EvidenceItem } from '../product/types'

const props = defineProps<{
  evidence: EvidenceItem[]
  selectedRelationId: string
}>()

const items = computed(() => {
  if (!props.selectedRelationId) {
    return props.evidence
  }

  return props.evidence.filter((item) => item.relationId === props.selectedRelationId)
})

const selectedTitle = computed(() => (props.selectedRelationId ? '选中关系证据' : '全部证据'))
</script>

<style scoped>
.evidence-drawer {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  align-content: start;
  min-height: 0;
  overflow: hidden;
}

.evidence-drawer .list {
  align-content: start;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

.evidence-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.evidence-meta span,
small {
  color: var(--muted);
}

.evidence-row p {
  margin: 8px 0;
}
</style>
