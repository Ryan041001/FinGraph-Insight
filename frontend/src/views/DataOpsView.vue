<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>数据与任务</h1>
        <p>查看基础数据导入、AKShare 增量任务和金标准评测状态。</p>
      </div>
      <div class="toolbar">
        <button type="button" @click="refresh" :disabled="loading">
          <RefreshCw v-if="!loading" :size="16" />
          <Loader2 v-else :size="16" class="spin" />
          刷新
        </button>
        <button type="button" class="secondary" @click="importDataset" :disabled="importing">
          <Database v-if="!importing" :size="16" />
          <Loader2 v-else :size="16" class="spin" />
          {{ importing ? '导入中' : '导入 FinancialDatasets' }}
        </button>
      </div>
    </div>

    <div class="metric-grid">
      <article class="metric metric-card">
        <div class="metric-icon import-icon">
          <FileDown :size="20" />
        </div>
        <span class="eyebrow">导入状态</span>
        <strong>{{ preload.dataset_status }}</strong>
      </article>
      <article class="metric metric-card">
        <div class="metric-icon node-icon">
          <CircleDot :size="20" />
        </div>
        <span class="eyebrow">节点</span>
        <strong>{{ formatNumber(preload.dataset_nodes) }}</strong>
      </article>
      <article class="metric metric-card">
        <div class="metric-icon rel-icon">
          <ArrowLeftRight :size="20" />
        </div>
        <span class="eyebrow">关系</span>
        <strong>{{ formatNumber(preload.dataset_relationships) }}</strong>
      </article>
      <article class="metric metric-card">
        <div class="metric-icon task-icon">
          <Clock :size="20" />
        </div>
        <span class="eyebrow">增量任务</span>
        <strong>{{ preload.akshare_status }}</strong>
      </article>
    </div>

    <div class="ops-layout">
      <section class="panel ops-panel">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">AKShare</span>
            <h2>新闻增量更新</h2>
          </div>
          <button type="button" @click="runJob" :disabled="jobRunning">
            <Play v-if="!jobRunning" :size="14" />
            <Loader2 v-else :size="14" class="spin" />
            {{ jobRunning ? '运行中' : '立即更新' }}
          </button>
        </div>
        <div v-if="jobs.length === 0" class="empty-state">
          <Inbox :size="32" />
          暂无任务记录
        </div>
        <div v-else class="job-list">
          <article v-for="job in jobs" :key="job.job_run_id" class="job-card">
            <div class="job-header">
              <div class="job-status">
                <span class="status-dot" :class="job.status"></span>
                <strong>{{ job.status }}</strong>
              </div>
              <span class="job-id">{{ job.job_run_id }}</span>
            </div>
            <dl class="job-metrics">
              <div class="job-metric">
                <dt>文档</dt>
                <dd>{{ job.new_documents }}</dd>
              </div>
              <div class="job-metric">
                <dt>实体</dt>
                <dd>{{ job.new_entities }}</dd>
              </div>
              <div class="job-metric">
                <dt>关系</dt>
                <dd>{{ job.new_relationships }}</dd>
              </div>
              <div class="job-metric">
                <dt>失败</dt>
                <dd>{{ job.failed_items }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section class="panel ops-panel">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">质量评测</span>
            <h2>金标准指标</h2>
          </div>
          <button type="button" class="secondary" @click="loadMetrics" :disabled="metricsLoading">
            <BarChart3 v-if="!metricsLoading" :size="14" />
            <Loader2 v-else :size="14" class="spin" />
            {{ metricsLoading ? '评测中' : '读取指标' }}
          </button>
        </div>
        <div v-if="metricsError" class="state-panel error">{{ metricsError }}</div>
        <div v-else-if="metrics" class="quality-grid">
          <div class="quality-card">
            <span>样本数</span>
            <strong>{{ metrics.sample_count }}</strong>
          </div>
          <div class="quality-card">
            <span>实体 F1</span>
            <strong>{{ percent(metrics.entity_f1) }}</strong>
          </div>
          <div class="quality-card">
            <span>关系 F1</span>
            <strong>{{ percent(metrics.relation_f1) }}</strong>
          </div>
          <div class="quality-card">
            <span>幻觉率</span>
            <strong>{{ percent(metrics.hallucination_rate) }}</strong>
          </div>
        </div>
        <p v-else class="muted hint">未配置真实 predictor 时，后端会返回 metrics_unavailable，这是预期的安全行为。</p>
      </section>
    </div>

    <div v-if="error" class="panel state-panel error">
      <AlertCircle :size="18" />
      {{ error }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  AlertCircle,
  ArrowLeftRight,
  BarChart3,
  CircleDot,
  Clock,
  Database,
  FileDown,
  Inbox,
  Loader2,
  Play,
  RefreshCw
} from 'lucide-vue-next'
import { getExtractionMetrics } from '../api/metrics'
import { getJob, listJobs, runAkshareJob } from '../api/jobs'
import { getPreloadState, importFinancialDataset } from '../api/runtime'
import type { ExtractionMetrics, JobRun, PreloadState } from '../api/types'

const loading = ref(false)
const importing = ref(false)
const metricsLoading = ref(false)
const error = ref('')
const metricsError = ref('')
const metrics = ref<ExtractionMetrics | null>(null)
const jobs = ref<JobRun[]>([])
const pollingJobId = ref('')
let pollTimer: number | undefined
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

const jobRunning = computed(() => jobs.value.some((job) => job.status === 'running') || Boolean(pollingJobId.value))

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [preloadResult, jobResult] = await Promise.all([getPreloadState(), listJobs()])
    preload.value = preloadResult
    jobs.value = jobResult.jobs
  } catch (err) {
    error.value = err instanceof Error ? err.message : '状态刷新失败'
  } finally {
    loading.value = false
  }
}

async function importDataset() {
  importing.value = true
  error.value = ''
  try {
    const result = await importFinancialDataset()
    preload.value = {
      ...preload.value,
      dataset_status: 'ready',
      dataset_nodes: result.nodes_created + result.nodes_skipped,
      dataset_relationships: result.relationships_created + result.relationships_skipped
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '导入失败'
  } finally {
    importing.value = false
  }
}

async function runJob() {
  error.value = ''
  try {
    const job = await runAkshareJob()
    jobs.value = [job, ...jobs.value.filter((item) => item.job_run_id !== job.job_run_id)]
    pollingJobId.value = job.job_run_id
    startPolling()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务启动失败'
  }
}

async function loadMetrics() {
  metricsLoading.value = true
  metricsError.value = ''
  try {
    metrics.value = await getExtractionMetrics()
  } catch (err) {
    metrics.value = null
    metricsError.value = err instanceof Error ? err.message : '评测暂不可用'
  } finally {
    metricsLoading.value = false
  }
}

function startPolling() {
  window.clearInterval(pollTimer)
  pollTimer = window.setInterval(async () => {
    if (!pollingJobId.value) {
      window.clearInterval(pollTimer)
      return
    }
    const job = await getJob(pollingJobId.value)
    jobs.value = [job, ...jobs.value.filter((item) => item.job_run_id !== job.job_run_id)]
    if (job.status !== 'running') {
      pollingJobId.value = ''
      window.clearInterval(pollTimer)
    }
  }, 2000)
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function percent(value: number) {
  return `${Math.round(value * 1000) / 10}%`
}

onMounted(refresh)
onBeforeUnmount(() => window.clearInterval(pollTimer))
</script>

<style scoped>
.metric-card {
  position: relative;
  overflow: hidden;
  padding-top: 48px;
  transition: all var(--transition-base) var(--ease-out);
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.metric-icon {
  position: absolute;
  top: var(--space-md);
  right: var(--space-md);
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  color: #ffffff;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base) var(--ease-out);
}

.metric-card:hover .metric-icon {
  transform: scale(1.1) rotate(5deg);
  box-shadow: var(--shadow-md);
}

.import-icon {
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
}

.node-icon {
  background: linear-gradient(135deg, #10b981, #059669);
}

.rel-icon {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}

.task-icon {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.ops-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-xl);
  align-items: stretch;
}

.ops-panel {
  display: grid;
  gap: var(--space-lg);
  align-content: start;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-2xl) var(--space-xl);
  color: var(--muted);
  font-size: 14px;
}

.empty-state svg {
  color: #cbd5e1;
  opacity: 0.6;
}

.job-list {
  display: grid;
  gap: var(--space-md);
}

.job-card {
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: var(--space-md);
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.job-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--line-strong);
  transform: translateY(-1px);
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.job-status {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.job-status strong {
  font-size: 14px;
  color: #0f172a;
}

.job-id {
  color: var(--muted);
  font-size: 12px;
  font-family: monospace;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  transition: all var(--transition-base) var(--ease-out);
}

.status-dot.running {
  background: #0ea5e9;
  box-shadow: 0 0 10px rgba(14, 165, 233, 0.5);
  animation: pulse 2s infinite;
}

.status-dot.completed,
.status-dot.success {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
}

.status-dot.failed {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.2); }
}

.job-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-sm);
  margin: 0;
}

.job-metric {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.95);
  padding: var(--space-sm);
  text-align: center;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.job-metric:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
  border-color: var(--accent);
}

.job-metric dt {
  color: var(--muted);
  font-size: 11px;
  margin-bottom: var(--space-xs);
}

.job-metric dd {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-md);
}

.quality-card {
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: var(--space-lg);
  text-align: center;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-base) var(--ease-out);
}

.quality-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--line-strong);
  transform: translateY(-2px);
}

.quality-card span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: var(--space-xs);
}

.quality-card strong {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.hint {
  padding: var(--space-xl);
  text-align: center;
  background: linear-gradient(145deg, rgba(255, 251, 235, 0.7), rgba(254, 249, 195, 0.4));
  border-radius: var(--radius-sm);
  border: 1px dashed var(--line);
  transition: all var(--transition-base) var(--ease-out);
}

.hint:hover {
  background: linear-gradient(145deg, rgba(255, 251, 235, 0.85), rgba(254, 249, 195, 0.55));
}

button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  transition: all var(--transition-base) var(--ease-out);
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

button:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 760px) {
  .ops-layout,
  .job-metrics,
  .quality-grid {
    grid-template-columns: 1fr;
  }
}
</style>
