<template>
  <div class="relation-filter-bar">
    <label>
      关系深度
      <select :value="depth" @change="changeDepth">
        <option :value="1">1 跳</option>
        <option :value="2">2 跳</option>
        <option :value="3">3 跳</option>
      </select>
    </label>
    <div class="segmented" aria-label="关系类型筛选">
      <button
        v-for="type in relationTypes"
        :key="type"
        type="button"
        :class="{ active: selectedTypes.includes(type) }"
        :aria-pressed="selectedTypes.includes(type)"
        @click="$emit('toggle-type', type)"
      >
        {{ type }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  depth: number
  relationTypes: string[]
  selectedTypes: string[]
}>()

const emit = defineEmits<{
  'update:depth': [depth: number]
  'toggle-type': [type: string]
}>()

function changeDepth(event: Event) {
  emit('update:depth', Number((event.target as HTMLSelectElement).value))
}
</script>

<style scoped>
.relation-filter-bar {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px;
  align-items: end;
}

label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 13px;
}

select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
  color: var(--ink);
  padding: 9px 10px;
}

.segmented {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.segmented button {
  border: 1px solid var(--line);
  background: #ffffff;
  color: var(--ink);
}

.segmented button.active {
  border-color: var(--accent);
  background: #f0fdfa;
  color: var(--accent);
}

@media (max-width: 720px) {
  .relation-filter-bar {
    grid-template-columns: 1fr;
  }
}
</style>
