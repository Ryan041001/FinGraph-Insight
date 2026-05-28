<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">RI</div>
        <div>
          <strong>企业风险尽调</strong>
          <span>Risk Intelligence</span>
        </div>
      </div>
      <nav aria-label="产品导航">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path">
          <component :is="item.icon" :size="18" />
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="workspace">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { FileText, Radar, Star } from 'lucide-vue-next'
import { productNavItems } from './router'

const navIcons = {
  '/workbench': Radar,
  '/watchlist': Star,
  '/reports': FileText
} satisfies Record<(typeof productNavItems)[number]['path'], Component>

const navItems = productNavItems.map((item) => ({
  ...item,
  icon: navIcons[item.path]
}))
</script>
