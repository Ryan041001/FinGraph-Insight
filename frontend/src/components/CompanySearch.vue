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
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  transition: color var(--transition-fast) var(--ease-out);
}

.company-search label svg {
  color: var(--accent);
  transition: transform var(--transition-fast) var(--ease-out);
}

.company-search:focus-within label svg {
  transform: scale(1.1);
}

.search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-sm);
  align-items: center;
}

.search-row input,
.search-row button {
  height: 44px;
}

.search-row input {
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.search-row input:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--line-strong);
}

.search-row input:focus {
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15), var(--shadow-sm);
  border-color: var(--accent);
}

.search-row button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 0 var(--space-lg);
  white-space: nowrap;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base) var(--ease-out);
}

.search-row button:hover:not(:disabled) {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.search-row button:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  margin-top: var(--space-md);
  align-items: center;
  animation: fadeIn var(--transition-base) var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.suggestions-label {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
  margin-right: var(--space-xs);
}

.suggestion-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.05));
  color: #0369a1;
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: var(--radius-lg);
  min-height: 32px;
  padding: 0 var(--space-sm);
  font-size: 13px;
  font-weight: 500;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
  cursor: pointer;
}

.suggestion-pill:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.1));
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: rgba(14, 143, 179, 0.35);
}

.suggestion-pill:active {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.suggestion-pill svg {
  transition: transform var(--transition-fast) var(--ease-out);
}

.suggestion-pill:hover svg {
  transform: scale(1.15);
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
