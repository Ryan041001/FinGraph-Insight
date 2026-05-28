<template>
  <section class="panel company-profile-panel">
    <span class="eyebrow">尽调对象</span>
    <h2>{{ company.name }}</h2>
    <dl>
      <div>
        <dt>行业</dt>
        <dd>{{ company.industry }}</dd>
      </div>
      <div>
        <dt>法人</dt>
        <dd>{{ company.legalRepresentative }}</dd>
      </div>
    </dl>
    <div class="tag-list">
      <span v-for="tag in company.tags" :key="tag">{{ tag }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ProductCompany } from '../product/types'

defineProps<{
  company: ProductCompany
}>()
</script>
