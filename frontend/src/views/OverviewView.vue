<template>
  <section class="page overview-page">
    <div class="hero-band">
      <div class="hero-copy">
        <div class="hero-badge">
          <Sparkles :size="14" />
          FinGraph Insight
        </div>
        <h1>金融知识图谱与大模型工作台</h1>
        <p>
          基于 FinancialDatasets、AKShare 与 OpenAI 兼容模型接口，完成数据导入、图谱浏览、自动证据抓取、统一问答和上市公司行情补充。
        </p>
        <div class="toolbar hero-actions">
          <button type="button" @click="refreshAll" :disabled="loading">
            <RefreshCw v-if="!loading" :size="16" />
            <Loader2 v-else :size="16" class="spin" />
            {{ loading ? '刷新中' : '刷新状态' }}
          </button>
          <RouterLink class="ghost-link" to="/workbench">
            进入工作台
            <ArrowRight :size="16" />
          </RouterLink>
        </div>
      </div>
      <div class="hero-stack">
        <article class="hero-card">
          <div class="hero-card-icon data-icon">
            <Database :size="20" />
          </div>
          <div class="hero-card-body">
            <span>数据导入</span>
            <strong>{{ datasetStatusLabel }}</strong>
            <small>{{ preload.dataset_nodes }} 节点 · {{ preload.dataset_relationships }} 关系</small>
          </div>
        </article>
        <article class="hero-card">
          <div class="hero-card-icon db-icon">
            <HardDrive :size="20" />
          </div>
          <div class="hero-card-body">
            <span>图数据库</span>
            <strong>{{ health.neo4j }}</strong>
            <small>scheduler: {{ health.scheduler }}</small>
          </div>
        </article>
        <article class="hero-card">
          <div class="hero-card-icon model-icon">
            <Brain :size="20" />
          </div>
          <div class="hero-card-body">
            <span>模型接口</span>
            <strong>{{ llmStatus }}</strong>
            <small>DeepSeek / OpenAI 兼容</small>
          </div>
        </article>
      </div>
    </div>

    <div class="summary-grid">
      <article class="panel stat-panel">
        <span class="eyebrow">项目运行</span>
        <h2>基础状态</h2>
        <dl>
          <div>
            <dt><Shield :size="14" /> 后端健康</dt>
            <dd>
              <span class="status-dot" :class="health.status === 'ok' ? 'ok' : ''"></span>
              {{ health.status }}
            </dd>
          </div>
          <div>
            <dt><Database :size="14" /> Neo4j</dt>
            <dd>{{ health.neo4j }}</dd>
          </div>
          <div>
            <dt><Clock :size="14" /> 调度器</dt>
            <dd>{{ health.scheduler }}</dd>
          </div>
          <div>
            <dt><FileDown :size="14" /> 导入状态</dt>
            <dd>{{ preload.dataset_status }}</dd>
          </div>
        </dl>
      </article>

      <article class="panel stat-panel">
        <span class="eyebrow">数据资源</span>
        <h2>接入内容</h2>
        <ul>
          <li><CheckCircle2 :size="14" class="icon-check" /> 工商、投资事件、投资机构、金融新闻、专栏资讯、36氪新闻</li>
          <li><CheckCircle2 :size="14" class="icon-check" /> AKShare 增量新闻与股票行情</li>
          <li><CheckCircle2 :size="14" class="icon-check" /> 金标准评测集与本地缓存</li>
        </ul>
      </article>

      <article class="panel stat-panel">
        <span class="eyebrow">模型能力</span>
        <h2>可用链路</h2>
        <ul>
          <li><Zap :size="14" class="icon-zap" /> 公司名驱动的实体关系抽取入图</li>
          <li><Zap :size="14" class="icon-zap" /> GraphRAG 与 Hybrid RAG</li>
          <li><Zap :size="14" class="icon-zap" /> Text2Cypher 只读查询</li>
          <li><Zap :size="14" class="icon-zap" /> 实时新闻补充与股票研判</li>
        </ul>
      </article>
    </div>

    <section class="panel feature-strip">
      <RouterLink v-for="feature in features" :key="feature.path" :to="feature.path" class="feature-link">
        <component :is="feature.icon" :size="22" />
        <span>{{ feature.label }}</span>
      </RouterLink>
    </section>

    <section class="panel demo-panel">
      <div class="panel-title-row">
        <div>
          <span class="eyebrow">真实图谱样例</span>
          <h2>可直接打开的企业关系网络</h2>
        </div>
        <Network :size="24" class="panel-icon" />
      </div>
      <div class="demo-links">
        <RouterLink
          v-for="company in demoCompanies"
          :key="company"
          class="demo-link"
          :to="`/workbench?company=${encodeURIComponent(company)}`"
        >
          <div class="demo-link-header">
            <Building2 :size="18" />
            <strong>{{ company }}</strong>
          </div>
          <span>查看融资事件、投资机构和证据链</span>
        </RouterLink>
      </div>
    </section>

    <div v-if="error" class="panel state-panel error">
      <AlertCircle :size="18" />
      {{ error }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  AlertCircle,
  ArrowRight,
  Brain,
  Building2,
  CheckCircle2,
  Clock,
  Database,
  FileDown,
  HardDrive,
  Loader2,
  Network,
  RefreshCw,
  Shield,
  Sparkles,
  Zap,
  FileText,
  Star
} from 'lucide-vue-next'
import { getHealth, getPreloadState } from '../api/runtime'
import type { HealthResponse, PreloadState } from '../api/types'

const loading = ref(false)
const error = ref('')
const health = ref<HealthResponse>({ status: 'unknown', neo4j: 'unknown', scheduler: 'unknown' })
const preload = ref<PreloadState>({
  dataset_status: 'skipped',
  dataset_started_at: null,
  dataset_finished_at: null,
  dataset_nodes: 0,
  dataset_relationships: 0,
  akshare_status: 'skipped',
  akshare_job_run_id: null,
  error: null
})
const demoCompanies = ['邦盛科技', '国投创业']

const features = [
  { path: '/workbench', label: '图谱与新闻', icon: Network },
  { path: '/data-ops', label: '数据任务', icon: Database },
  { path: '/watchlist', label: '关注追踪', icon: Star },
  { path: '/reports', label: '研判报告', icon: FileText }
]

const datasetStatusLabel = computed(() => {
  const labels: Record<PreloadState['dataset_status'], string> = {
    skipped: '等待导入',
    running: '导入中',
    ready: '已就绪',
    failed: '导入失败'
  }
  return labels[preload.value.dataset_status]
})

const llmStatus = computed(() => {
  return preload.value.error ? '需检查配置' : '已接入'
})

async function refreshAll() {
  loading.value = true
  error.value = ''
  try {
    const [healthResult, preloadResult] = await Promise.all([getHealth(), getPreloadState()])
    health.value = healthResult
    preload.value = preloadResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : '状态刷新失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void refreshAll()
})
</script>

<style scoped>
.overview-page {
  display: grid;
  gap: 20px;
}

.hero-band {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 420px);
  gap: 20px;
  align-items: stretch;
}

.hero-copy,
.hero-stack {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(135deg, rgba(14, 165, 233, 0.05), rgba(99, 102, 241, 0.04)),
    var(--panel-strong);
  padding: 28px;
  box-shadow: var(--shadow);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.08));
  color: #0369a1;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin-bottom: 12px;
}

.hero-copy h1 {
  margin: 8px 0 12px;
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
  background: linear-gradient(135deg, #0f172a, #334155);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-copy p {
  margin: 0;
  color: var(--muted);
  max-width: 56ch;
  line-height: 1.65;
  font-size: 15px;
}

.hero-actions {
  margin-top: 20px;
}

.hero-actions button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.hero-stack {
  display: grid;
  gap: 14px;
  align-content: start;
}

.hero-card {
  display: flex;
  gap: 14px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(241, 245, 249, 0.88));
  padding: 16px;
  transition: all 200ms ease;
}

.hero-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateX(2px);
}

.hero-card-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-sm);
  color: #ffffff;
  flex-shrink: 0;
}

.data-icon {
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
}

.db-icon {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}

.model-icon {
  background: linear-gradient(135deg, #10b981, #059669);
}

.hero-card-body {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.hero-card-body span {
  color: var(--muted);
  font-size: 12px;
}

.hero-card-body strong {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.hero-card-body small {
  color: var(--muted);
  font-size: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.demo-panel {
  display: grid;
  gap: 16px;
}

.panel-icon {
  color: var(--accent);
  opacity: 0.5;
}

.feature-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  padding: 18px;
}

.feature-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 90px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.06), rgba(99, 102, 241, 0.04));
  color: #334155;
  text-decoration: none;
  font-weight: 600;
  font-size: 13px;
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  padding: 14px;
}

.feature-link:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(99, 102, 241, 0.08));
  color: #0f172a;
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  border-color: var(--line-strong);
}

.feature-link svg {
  color: var(--accent);
  transition: transform 200ms ease;
}

.feature-link:hover svg {
  transform: scale(1.1);
}

.demo-links {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.demo-link {
  display: grid;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  color: var(--ink);
  text-decoration: none;
  padding: 18px;
  transition: all 200ms ease;
}

.demo-link:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.demo-link-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.demo-link-header svg {
  color: var(--accent);
}

.demo-link strong {
  font-size: 16px;
  color: #0f172a;
}

.demo-link span {
  color: var(--muted);
  font-size: 13px;
}

.stat-panel {
  display: grid;
  gap: 14px;
}

.stat-panel h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.stat-panel dl,
.stat-panel ul {
  margin: 0;
  padding: 0;
}

.stat-panel dl {
  display: grid;
  gap: 10px;
}

.stat-panel dl div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--line);
  align-items: center;
}

.stat-panel dl div:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.stat-panel dt {
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.stat-panel dd {
  margin: 0;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}

.status-dot.ok {
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
}

.stat-panel ul {
  display: grid;
  gap: 10px;
  list-style: none;
}

.stat-panel ul li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.icon-check {
  color: var(--success);
  flex-shrink: 0;
}

.icon-zap {
  color: var(--accent);
  flex-shrink: 0;
}

.ghost-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 42px;
  padding: 0 18px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  color: #334155;
  text-decoration: none;
  background: rgba(255, 255, 255, 0.9);
  font-weight: 600;
  font-size: 14px;
  transition: all 200ms ease;
}

.ghost-link:hover {
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
}

@media (max-width: 1100px) {
  .hero-band,
  .summary-grid,
  .demo-links,
  .feature-strip {
    grid-template-columns: 1fr;
  }

  .hero-copy h1 {
    font-size: 26px;
  }
}
</style>
