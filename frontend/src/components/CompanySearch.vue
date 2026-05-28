<template>
  <form class="company-search" @submit.prevent="submit">
    <label for="company-search-input">企业名称或股票代码</label>
    <div class="search-row">
      <input id="company-search-input" v-model="searchValue" type="search" />
      <button type="submit" :disabled="isDuplicateLoadingQuery">
        {{ isDuplicateLoadingQuery ? '分析中' : '开始尽调' }}
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: string
  loading?: boolean
  activeQuery?: string
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
</script>
