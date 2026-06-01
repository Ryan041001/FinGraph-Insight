<template>
  <section class="company-profile-panel">
    <div class="profile-header">
      <div class="profile-avatar">
        <Building2 :size="22" />
      </div>
      <div>
        <span class="eyebrow">搜索对象</span>
        <h2>{{ company.name }}</h2>
      </div>
    </div>
    <dl class="profile-facts">
      <div>
        <dt><Briefcase :size="13" /> 行业</dt>
        <dd>{{ company.industry || '待补充' }}</dd>
      </div>
      <div>
        <dt><User :size="13" /> 法人</dt>
        <dd>{{ company.legalRepresentative || '待补充' }}</dd>
      </div>
    </dl>
    <div v-if="company.tags.length > 0" class="tag-list">
      <span v-for="tag in company.tags" :key="tag">
        <Tag :size="11" />
        {{ tag }}
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Briefcase, Building2, Tag, User } from 'lucide-vue-next'
import type { ProductCompany } from '../product/types'

defineProps<{
  company: ProductCompany
}>()
</script>

<style scoped>
.company-profile-panel {
  display: grid;
  gap: 16px;
  overflow: hidden;
  border: 1px solid rgba(14, 143, 179, 0.15);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(140deg, rgba(236, 253, 245, 0.92), rgba(239, 246, 255, 0.96) 52%, rgba(255, 251, 235, 0.92)),
    var(--panel-strong);
  box-shadow: var(--shadow);
  padding: 18px;
  transition: all 200ms ease;
}

.company-profile-panel:hover {
  box-shadow: var(--shadow-md);
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.profile-avatar {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #ffffff;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.25);
}

.company-profile-panel .eyebrow {
  margin-bottom: 0;
  color: var(--accent);
  font-weight: 800;
  font-size: 10px;
}

.company-profile-panel h2 {
  margin: 2px 0 0;
  color: var(--ink);
  font-size: 20px;
  line-height: 1.35;
  word-break: break-word;
  font-weight: 700;
}

.profile-facts {
  display: grid;
  gap: 8px;
  margin: 0;
}

.profile-facts div {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  border: 1px solid rgba(14, 143, 179, 0.12);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.72);
  padding: 10px 12px;
  transition: all 150ms ease;
}

.profile-facts div:hover {
  border-color: rgba(14, 143, 179, 0.25);
  background: rgba(255, 255, 255, 0.9);
}

.profile-facts dt,
.profile-facts dd {
  margin: 0;
}

.profile-facts dt {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.7;
  display: flex;
  align-items: center;
  gap: 5px;
}

.profile-facts dd {
  color: var(--ink);
  font-weight: 700;
  line-height: 1.5;
  text-align: right;
  word-break: break-word;
  font-size: 14px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-list span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  border: 1px solid rgba(14, 143, 179, 0.15);
  border-radius: 999px;
  background: rgba(236, 253, 245, 0.82);
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
}
</style>
