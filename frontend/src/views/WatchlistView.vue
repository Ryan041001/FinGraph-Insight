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
  gap: var(--space-sm);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.08));
  color: #0369a1;
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-xl);
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.header-badge:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  padding: var(--space-2xl) var(--space-xl);
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
  opacity: 0.6;
}

.watchlist-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--space-lg);
}

.watchlist-card {
  background: var(--panel-strong);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  box-shadow: var(--shadow-md);
  transition: all var(--transition-base) var(--ease-out);
  display: grid;
  gap: var(--space-sm);
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
  transition: all var(--transition-base) var(--ease-out);
}

.watchlist-card[data-risk="high"]::before {
  background: linear-gradient(180deg, #ef4444, #dc2626);
  box-shadow: 2px 0 8px rgba(239, 68, 68, 0.3);
}

.watchlist-card[data-risk="medium"]::before {
  background: linear-gradient(180deg, #f59e0b, #d97706);
  box-shadow: 2px 0 8px rgba(245, 158, 11, 0.3);
}

.watchlist-card[data-risk="low"]::before {
  background: linear-gradient(180deg, #10b981, #059669);
  box-shadow: 2px 0 8px rgba(16, 185, 129, 0.3);
}

.watchlist-card[data-risk="unknown"]::before {
  background: linear-gradient(180deg, #94a3b8, #64748b);
}

.watchlist-card:hover {
  box-shadow: var(--shadow-xl);
  transform: translateY(-3px);
  border-color: var(--line-strong);
}

.watchlist-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-sm);
}

.company-info {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}

.company-info svg {
  color: var(--accent);
  flex-shrink: 0;
  transition: transform var(--transition-base) var(--ease-out);
}

.watchlist-card:hover .company-info svg {
  transform: scale(1.15);
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
  gap: var(--space-xs);
  border-radius: var(--radius-xl);
  padding: var(--space-xs) var(--space-sm);
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-fast) var(--ease-out);
}

.risk-badge:hover {
  transform: scale(1.05);
}

.risk-high {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.risk-medium {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.risk-low {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.risk-unknown {
  background: rgba(148, 163, 184, 0.15);
  color: #475569;
  border: 1px solid rgba(148, 163, 184, 0.2);
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
  gap: var(--space-sm);
  margin-top: var(--space-xs);
}

.action-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.06));
  color: #0369a1;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.action-link:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.1));
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.remove-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  min-height: auto;
  font-size: 13px;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.remove-btn:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
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
