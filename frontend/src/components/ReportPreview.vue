<template>
  <section class="panel report-preview">
    <span class="eyebrow">研判报告</span>
    <h2>{{ model.company.name }} 风险尽调摘要</h2>
    <p>{{ model.risk.summary }}</p>
    <div class="list">
      <article v-for="factor in model.risk.factors" :key="factor.id" class="list-item">
        <strong>{{ factor.title }}</strong>
        <p>{{ factor.description }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { RiskWorkbenchModel } from '../product/types'

defineProps<{
  model: RiskWorkbenchModel
}>()
</script>

<style scoped>
.report-preview {
  display: grid;
  gap: 12px;
}

.report-preview p {
  margin: 0;
}
</style>
