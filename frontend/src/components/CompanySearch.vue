<template>
  <form class="company-search" @submit.prevent="submit">
    <label for="company-search-input">
      <Search :size="14" />
      企业名称或股票代码
    </label>
    <div class="search-row">
      <input
        id="company-search-input"
        v-model="searchValue"
        name="company-search"
        type="search"
        placeholder="输入企业名称搜索..."
      />
      <button type="submit" :disabled="isDuplicateLoadingQuery">
        <Search v-if="!isDuplicateLoadingQuery" :size="16" />
        <Loader2 v-else :size="16" class="spin" />
        {{ isDuplicateLoadingQuery ? '搜索中' : '开始搜索' }}
      </button>
    </div>
    <div v-if="options.length > 0" class="suggestions" data-testid="company-suggestions">
      <span class="suggestions-label">建议</span>
      <button
        v-for="option in options"
        :key="option.id"
        type="button"
        class="suggestion-pill"
        @click="pickSuggestion(option.name)"
      >
        <Building2 :size="12" />
        {{ option.name }}
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Building2, Loader2, Search } from 'lucide-vue-next'
import type { CompanySearchItem } from '../api/types'

const props = defineProps<{
  modelValue: string
  loading?: boolean
  activeQuery?: string
  options?: CompanySearchItem[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
}>()

const searchValue = computed({
  get: () => props.modelValue,
  set: (value: string) => {
    emit('update:modelValue', value)
  }
})

const trimmedSearchValue = computed(() => searchValue.value.trim())
const trimmedActiveQuery = computed(() => (props.activeQuery ?? '').trim())
const options = computed(() => props.options ?? [])
const isDuplicateLoadingQuery = computed(() => {
  return Boolean(props.loading && trimmedActiveQuery.value && trimmedSearchValue.value === trimmedActiveQuery.value)
})

function submit() {
  const value = trimmedSearchValue.value
  emit('update:modelValue', value)
  if (isDuplicateLoadingQuery.value) {
    return
  }
  emit('search', value)
}

function pickSuggestion(value: string) {
  emit('update:modelValue', value)
  emit('search', value)
}
</script>

<style scoped>
.company-search {
  width: min(100%, 520px);
}

.company-search label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 13px;
}

.company-search label svg {
  color: var(--accent);
}

.search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.search-row input,
.search-row button {
  height: 44px;
}

.search-row button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 18px;
  white-space: nowrap;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  align-items: center;
}

.suggestions-label {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
  margin-right: 4px;
}

.suggestion-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.05));
  color: #0369a1;
  border: 1px solid rgba(14, 143, 179, 0.18);
  min-height: 32px;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 500;
  transition: all 150ms ease;
}

.suggestion-pill:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.1));
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .company-search {
    width: 100%;
  }
}
</style>
