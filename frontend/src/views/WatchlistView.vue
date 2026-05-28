<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>关注清单</h1>
        <p>持续跟踪重点企业的风险变化。</p>
      </div>
    </div>

    <div v-if="items.length === 0" class="panel empty-state">
      暂无关注企业。请先在风险工作台中加入关注。
    </div>

    <div v-else class="panel list">
      <article v-for="item in items" :key="item.companyName" class="list-item watchlist-row">
        <div>
          <strong>{{ item.companyName }}</strong>
          <p>{{ item.industry }} · {{ riskLabel(item.riskLevel) }}</p>
          <span>{{ item.summary }}</span>
        </div>
        <div class="toolbar">
          <RouterLink class="text-link" :to="`/workbench?company=${encodeURIComponent(item.companyName)}`">打开工作台</RouterLink>
          <button type="button" class="secondary" @click="remove(item.companyName)">移除</button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { loadWatchlist, removeWatchlistItem } from '../product/storage'
import type { RiskLevel, WatchlistItem } from '../product/types'

const items = ref<WatchlistItem[]>(loadWatchlist())

function remove(companyName: string) {
  removeWatchlistItem(companyName)
  items.value = loadWatchlist()
}

function riskLabel(level: RiskLevel): string {
  const labels: Record<RiskLevel, string> = {
    high: '高风险',
    medium: '中风险',
    low: '低风险',
    unknown: '待补充数据'
  }

  return labels[level]
}
</script>

<style scoped>
.watchlist-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.watchlist-row p {
  margin: 6px 0;
}

.watchlist-row span {
  color: var(--muted);
}

.text-link {
  color: var(--accent);
  text-decoration: none;
}

@media (max-width: 720px) {
  .watchlist-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
