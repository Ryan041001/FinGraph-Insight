<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>关注清单</h1>
        <p>持续跟踪重点企业的风险变化。</p>
      </div>
      <div class="header-badge">
        <Bookmark :size="18" />
        {{ items.length }} 家企业
      </div>
    </div>

    <div v-if="items.length === 0" class="panel empty-state">
      <Inbox :size="48" class="empty-icon" />
      <p>暂无关注企业</p>
      <span>请先在风险工作台中加入关注</span>
    </div>

    <div v-else class="watchlist-grid">
      <article
        v-for="item in items"
        :key="item.companyName"
        class="watchlist-card"
        :data-risk="item.riskLevel"
      >
        <div class="watchlist-card-header">
          <div class="company-info">
            <Building2 :size="20" />
            <strong>{{ item.companyName }}</strong>
          </div>
          <span class="risk-badge" :class="`risk-${item.riskLevel}`">
            <ShieldAlert v-if="item.riskLevel === 'high'" :size="12" />
            <ShieldCheck v-else-if="item.riskLevel === 'low'" :size="12" />
            <Shield v-else :size="12" />
            {{ riskLabel(item.riskLevel) }}
          </span>
        </div>
        <p class="industry">{{ item.industry }}</p>
        <p class="summary">{{ item.summary }}</p>
        <div class="watchlist-actions">
          <RouterLink class="action-link" :to="`/workbench?company=${encodeURIComponent(item.companyName)}`">
            <ExternalLink :size="14" />
            打开工作台
          </RouterLink>
          <button type="button" class="secondary remove-btn" @click="remove(item.companyName)">
            <Trash2 :size="14" />
            移除
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  Bookmark,
  Building2,
  ExternalLink,
  Inbox,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2
} from 'lucide-vue-next'
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
.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.08));
  color: #0369a1;
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 600;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 24px;
  text-align: center;
  color: var(--muted);
}

.empty-state p {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #334155;
}

.empty-state span {
  font-size: 14px;
}

.empty-icon {
  color: #cbd5e1;
}

.watchlist-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 18px;
}

.watchlist-card {
  background: var(--panel-strong);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 22px;
  box-shadow: var(--shadow);
  transition: all 200ms ease;
  display: grid;
  gap: 10px;
  position: relative;
  overflow: hidden;
}

.watchlist-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: #cbd5e1;
}

.watchlist-card[data-risk="high"]::before {
  background: linear-gradient(180deg, #ef4444, #dc2626);
}

.watchlist-card[data-risk="medium"]::before {
  background: linear-gradient(180deg, #f59e0b, #d97706);
}

.watchlist-card[data-risk="low"]::before {
  background: linear-gradient(180deg, #10b981, #059669);
}

.watchlist-card[data-risk="unknown"]::before {
  background: linear-gradient(180deg, #94a3b8, #64748b);
}

.watchlist-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.watchlist-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.company-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.company-info svg {
  color: var(--accent);
  flex-shrink: 0;
}

.company-info strong {
  font-size: 17px;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.risk-high {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}

.risk-medium {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
}

.risk-low {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.risk-unknown {
  background: rgba(148, 163, 184, 0.15);
  color: #475569;
}

.industry {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.summary {
  margin: 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.watchlist-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}

.action-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.06));
  color: #0369a1;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  transition: all 150ms ease;
}

.action-link:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.1));
}

.remove-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  min-height: auto;
  font-size: 13px;
}

@media (max-width: 720px) {
  .watchlist-grid {
    grid-template-columns: 1fr;
  }

  .watchlist-card-header {
    flex-wrap: wrap;
  }
}
</style>
