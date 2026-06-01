<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <Network :size="20" />
        </div>
        <div>
          <strong>企业风险尽调</strong>
          <span>Risk Intelligence</span>
        </div>
      </div>
      <nav aria-label="产品导航">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path">
          <component :is="item.icon" :size="18" stroke-width="2" />
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="sidebar-footer">
        FinGraph Insight v0.1
      </div>
    </aside>
    <main class="workspace">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import {
  Activity,
  Database,
  FileText,
  FlaskConical,
  Gauge,
  Network,
  Radar,
  Star
} from 'lucide-vue-next'
import { productNavItems } from './router'

const navIcons = {
  '/overview': Activity,
  '/workbench': Radar,
  '/extraction': FlaskConical,
  '/market': Gauge,
  '/data-ops': Database,
  '/watchlist': Star,
  '/reports': FileText
} satisfies Record<(typeof productNavItems)[number]['path'], Component>

const navItems = productNavItems.map((item) => ({
  ...item,
  icon: navIcons[item.path]
}))
</script>
