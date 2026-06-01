<template>
  <section class="page market-page">
    <div class="page-header">
      <div>
        <h1>行情研判</h1>
        <p>拉取真实行情、拼接图谱事件，并生成上市公司辅助研判。</p>
      </div>
      <form class="toolbar market-form" @submit.prevent="loadAll">
        <input v-model="stockCode" aria-label="股票代码" placeholder="600000" @input="markStockCodeEdited" />
        <input v-model="companyName" aria-label="公司名称" placeholder="浦发银行" @input="syncKnownStockCode" />
        <button type="submit" :disabled="loading">
          <Search v-if="!loading" :size="16" />
          <Loader2 v-else :size="16" class="spin" />
          {{ loading ? '加载中' : '查询' }}
        </button>
      </form>
    </div>
    <p class="market-hint">
      <Info :size="14" />
      当前 K 线按股票代码 {{ resolvedStockCode }} 拉取；公司名称用于匹配图谱事件。
      <span v-if="companyStockHint">{{ companyStockHint }}</span>
    </p>

    <div class="metric-grid">
      <article class="metric metric-card">
        <span class="eyebrow">行情源</span>
        <strong>{{ kline?.data_source ?? '-' }}</strong>
      </article>
      <article class="metric metric-card">
        <span class="eyebrow">缓存</span>
        <strong>{{ kline?.cached ? '命中' : '实时' }}</strong>
      </article>
      <article class="metric metric-card">
        <span class="eyebrow">K 线数量</span>
        <strong>{{ kline?.kline_data.length ?? 0 }}</strong>
      </article>
      <article class="metric metric-card">
        <span class="eyebrow">图谱事件</span>
        <strong>{{ kline?.events.length ?? 0 }}</strong>
      </article>
    </div>

    <div class="market-layout">
      <section class="panel chart-panel">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">K 线收盘走势</span>
            <h2>{{ klineDisplayTitle }}</h2>
          </div>
          <span v-if="kline?.cache_status" class="status">{{ kline.cache_status }}</span>
        </div>
        <div class="sparkline" aria-label="收盘价走势">
          <div v-if="loading" class="empty-state">正在加载行情数据...</div>
          <svg v-else-if="sparklinePoints" viewBox="0 0 640 220" preserveAspectRatio="none">
            <defs>
              <linearGradient id="sparklineGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="rgba(14, 165, 233, 0.3)" />
                <stop offset="100%" stop-color="rgba(14, 165, 233, 0)" />
              </linearGradient>
            </defs>
            <polygon :points="sparklineFillPoints" fill="url(#sparklineGrad)" />
            <polyline :points="sparklinePoints" />
          </svg>
          <div v-else class="empty-state">暂无行情数据。</div>
        </div>
        <div class="event-strip">
          <article v-for="event in kline?.events ?? []" :key="`${event.date}-${event.label}`">
            <div class="event-timeline">
              <div class="event-dot"></div>
              <div class="event-line"></div>
            </div>
            <div class="event-body">
              <span>{{ event.date }}</span>
              <strong>{{ event.label }}</strong>
              <small>{{ event.amount || event.round || event.source || '图谱事件' }}</small>
            </div>
          </article>
        </div>
      </section>

      <section class="panel analysis-panel">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">图谱增强研判</span>
            <h2>{{ resultTitle }}</h2>
          </div>
          <button type="button" class="secondary" @click="loadSubmittedAnalysis(true)" :disabled="analysisLoading || !submittedCompanyName">
            <Sparkles v-if="!analysisLoading" :size="14" />
            <Loader2 v-else :size="14" class="spin" />
            {{ analysisLoading ? '生成中' : '调用模型增强' }}
          </button>
        </div>
        <div v-if="analysisLoading" class="state-panel">正在生成研判...</div>
        <div v-else-if="analysisError" class="state-panel error">{{ analysisError }}</div>
        <div v-else-if="analysisView" class="analysis-result">
          <article class="analysis-summary">
            <span class="eyebrow">研判摘要</span>
            <p>{{ analysisView.summary }}</p>
            <div class="confidence-meter">
              <span class="meter-source">{{ analysisSourceLabel }}</span>
              <div class="meter-bar">
                <div class="meter-fill" :style="{ width: `${analysisView.confidence * 100}%` }"></div>
              </div>
              <strong>{{ percent(analysisView.confidence) }}</strong>
            </div>
          </article>
          <div class="analysis-columns">
            <article class="factor-panel opportunity">
              <span class="eyebrow">机会因素</span>
              <ul v-if="analysisView.opportunityFactors.length > 0">
                <li v-for="item in analysisView.opportunityFactors" :key="item">
                  <TrendingUp :size="14" class="factor-icon-up" />
                  {{ item }}
                </li>
              </ul>
              <p v-else class="muted">暂无明确机会因素。</p>
            </article>
            <article class="factor-panel risk">
              <span class="eyebrow">风险因素</span>
              <ul v-if="analysisView.riskFactors.length > 0">
                <li v-for="item in analysisView.riskFactors" :key="item">
                  <TrendingDown :size="14" class="factor-icon-down" />
                  {{ item }}
                </li>
              </ul>
              <p v-else class="muted">暂无明确风险因素。</p>
            </article>
          </div>
          <article class="analysis-list-card">
            <span class="eyebrow">图谱洞察</span>
            <ul v-if="analysisView.graphInsights.length > 0">
              <li v-for="item in analysisView.graphInsights" :key="item">
                <Network :size="14" class="insight-icon" />
                {{ item }}
              </li>
            </ul>
            <p v-else class="muted">暂无可展示图谱洞察。</p>
          </article>
          <article class="fundamental-card">
            <span class="eyebrow">基本面字段</span>
            <dl>
              <div><dt>行业</dt><dd>{{ analysisView.industry }}</dd></div>
              <div><dt>数据时间</dt><dd>{{ analysisView.dataTime }}</dd></div>
              <div><dt>图谱事件</dt><dd>{{ analysisView.eventCount }} 条</dd></div>
              <div><dt>图谱关系</dt><dd>{{ analysisView.edgeCount }} 条</dd></div>
            </dl>
          </article>
          <article v-if="analysisView.missingData.length > 0" class="analysis-list-card warning-card">
            <span class="eyebrow">待补充数据</span>
            <ul>
              <li v-for="item in analysisView.missingData" :key="item">
                <AlertCircle :size="14" class="warning-icon" />
                {{ item }}
              </li>
            </ul>
          </article>
          <small class="disclaimer">
            <Info :size="14" />
            {{ analysisView.disclaimer }}
          </small>
        </div>
        <p v-else class="muted">查询后会展示基本面、图谱事件、风险因素和免责声明。</p>
      </section>
    </div>

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
  Info,
  Loader2,
  Network,
  Search,
  Sparkles,
  TrendingDown,
  TrendingUp
} from 'lucide-vue-next'
import { analyzeStock } from '../api/analysis'
import { getKline, type KlineResponse } from '../api/market'
import { plainTextFromMarkdown } from '../product/text'

const stockCode = ref('')
const companyName = ref('浦发银行')
const loading = ref(false)
const analysisLoading = ref(false)
const error = ref('')
const analysisError = ref('')
const kline = ref<KlineResponse | null>(null)
const analysis = ref<Record<string, unknown> | null>(null)
const stockCodeEdited = ref(false)
const analysisUsesLlm = ref(false)
const submittedCompanyName = ref('')
const submittedStockCode = ref('')
const DEFAULT_KLINE_STOCK_CODE = '600000'

const KNOWN_STOCKS: Record<string, string> = {
  浦发银行: '600000',
  平安银行: '000001',
  招商银行: '600036',
  贵州茅台: '600519',
  比亚迪: '002594',
  万科A: '000002',
  万科: '000002',
  宁德时代: '300750',
  中国平安: '601318',
  工商银行: '601398',
  农业银行: '601288',
  中国银行: '601988',
  建设银行: '601939'
}

const resolvedStockCode = computed(() => normalizeStockCode(stockCode.value) || '空')
const klineDisplayTitle = computed(() => submittedStockCode.value ? (kline.value?.display_code ?? submittedStockCode.value) : '')
const resultTitle = computed(() => submittedCompanyName.value || submittedStockCode.value || companyName.value || stockCode.value)
const analysisSourceLabel = computed(() => analysisUsesLlm.value ? '模型增强研判' : '本地图谱研判')
const companyStockHint = computed(() => {
  const matchedCode = resolveKnownStockCode(companyName.value)
  if (!companyName.value.trim()) {
    return ''
  }
  if (!matchedCode) {
    return '未检测到股票代码，K 线仍会展示，但不显示股票代码。'
  }
  return matchedCode === resolvedStockCode.value
    ? `已匹配 ${companyName.value.trim()}：${matchedCode}。`
    : `检测到 ${companyName.value.trim()} 常用代码为 ${matchedCode}，当前仍按 ${resolvedStockCode.value} 查询。`
})

const analysisView = computed(() => {
  if (!analysis.value) {
    return null
  }
  const analysisBlock = asRecord(analysis.value.analysis)
  const fundamentals = asRecord(analysis.value.fundamentals)
  const subgraph = asRecord(analysis.value.subgraph)
  const nodes = Array.isArray(subgraph.nodes) ? subgraph.nodes : []
  const edges = Array.isArray(subgraph.edges) ? subgraph.edges : []
  const events = Array.isArray(analysis.value.news_events) ? analysis.value.news_events : []
  const nodeLabels = buildNodeLabelMap(nodes)

  return {
    summary: stringField(analysisBlock.summary, '暂无摘要。'),
    opportunityFactors: stringList(analysisBlock.opportunity_factors),
    riskFactors: stringList(analysisBlock.risk_factors),
    graphInsights: graphInsightList(analysisBlock.graph_insights, nodeLabels),
    missingData: stringList(analysisBlock.missing_data),
    confidence: numberField(analysisBlock.confidence, 0),
    disclaimer: stringField(analysisBlock.disclaimer, '本结果仅用于研究辅助，不构成投资建议。'),
    industry: stringField(fundamentals.industry || fundamentals.sector, '未知'),
    dataTime: stringField(fundamentals.data_time, '未知'),
    eventCount: events.length,
    edgeCount: edges.length
  }
})

const sparklinePoints = computed(() => {
  const points = kline.value?.kline_data ?? []
  if (points.length === 0) {
    return ''
  }
  const closes = points.map((point) => point.close)
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const span = max - min || 1
  return closes.map((close, index) => {
    const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 640
    const y = 200 - ((close - min) / span) * 180
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

const sparklineFillPoints = computed(() => {
  if (!sparklinePoints.value) return ''
  const first = sparklinePoints.value.split(' ')[0]
  const last = sparklinePoints.value.split(' ').pop()
  return `${first} ${sparklinePoints.value} ${last} 640,220 0,220`
})

async function loadAll() {
  loading.value = true
  error.value = ''
  analysisError.value = ''
  kline.value = null
  analysis.value = null
  analysisUsesLlm.value = false
  submittedStockCode.value = ''
  submittedCompanyName.value = companyName.value.trim()
  try {
    const matchedCode = resolveKnownStockCode(companyName.value)
    stockCode.value = matchedCode || ''
    const submittedCode = normalizeStockCode(stockCode.value)
    const queryStockCode = submittedCode || DEFAULT_KLINE_STOCK_CODE
    const queryCompanyName = companyName.value.trim() || queryStockCode
    submittedStockCode.value = submittedCode
    submittedCompanyName.value = queryCompanyName

    const [klineResult, analysisResult] = await Promise.allSettled([
      getKline(queryStockCode, 'A', 'daily', queryCompanyName),
      loadAnalysis(false, queryStockCode, queryCompanyName)
    ])

    if (klineResult.status === 'fulfilled') {
      kline.value = klineResult.value
    } else {
      error.value = klineResult.reason instanceof Error ? klineResult.reason.message : '行情加载失败'
    }

    if (analysisResult.status === 'rejected') {
      analysisError.value = analysisResult.reason instanceof Error ? analysisResult.reason.message : '研判生成失败'
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '行情加载失败'
  } finally {
    loading.value = false
  }
}

function loadSubmittedAnalysis(useLlm: boolean) {
  return loadAnalysis(
    useLlm,
    submittedStockCode.value || normalizeStockCode(stockCode.value),
    submittedCompanyName.value || companyName.value.trim() || normalizeStockCode(stockCode.value)
  )
}

async function loadAnalysis(useLlm: boolean, queryStockCode: string, queryCompanyName: string) {
  analysisLoading.value = true
  analysisError.value = ''
  try {
    analysis.value = await analyzeStock({
      stockCode: queryStockCode,
      companyName: queryCompanyName,
      refreshNews: false,
      useLlm
    })
    analysisUsesLlm.value = useLlm
  } catch (err) {
    analysis.value = null
    analysisError.value = err instanceof Error ? err.message : '研判生成失败'
  } finally {
    analysisLoading.value = false
  }
}

function markStockCodeEdited() {
  stockCodeEdited.value = true
}

function syncKnownStockCode() {
  const matchedCode = resolveKnownStockCode(companyName.value)
  stockCode.value = matchedCode || ''
  stockCodeEdited.value = false
}

function resolveKnownStockCode(value: string) {
  const normalizedName = value.trim()
  return KNOWN_STOCKS[normalizedName] ?? ''
}

function normalizeStockCode(value: string) {
  return value.trim()
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}

function stringField(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? plainTextFromMarkdown(value) : fallback
}

function numberField(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function percent(value: number) {
  return `${Math.round(value * 1000) / 10}%`
}

function stringList(value: unknown) {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => {
      if (typeof item === 'string') {
        return plainTextFromMarkdown(item)
      }
      if (typeof item === 'object' && item !== null) {
        const record = item as Record<string, unknown>
        const title = typeof record.title === 'string' ? record.title : ''
        const detail = typeof record.detail === 'string'
          ? record.detail
          : typeof record.evidence === 'string'
            ? record.evidence
            : typeof record.path === 'string'
              ? record.path
              : ''
        return plainTextFromMarkdown([title, detail].filter(Boolean).join('：'))
      }
      return ''
    })
    .filter(Boolean)
}

function graphInsightList(value: unknown, nodeLabels: Map<string, string>) {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => {
      if (typeof item === 'string') {
        return replaceNodeIds(plainTextFromMarkdown(item), nodeLabels)
      }
      if (typeof item === 'object' && item !== null) {
        const record = item as Record<string, unknown>
        const title = typeof record.title === 'string' ? record.title : ''
        const detail = typeof record.detail === 'string'
          ? record.detail
          : typeof record.evidence === 'string'
            ? record.evidence
            : typeof record.path === 'string'
              ? readablePath(record.path, nodeLabels)
              : ''
        return plainTextFromMarkdown([title, detail].filter(Boolean).join('：'))
      }
      return ''
    })
    .filter(Boolean)
}

function buildNodeLabelMap(nodes: unknown[]) {
  const labels = new Map<string, string>()
  for (const node of nodes) {
    if (typeof node !== 'object' || node === null) {
      continue
    }
    const record = node as Record<string, unknown>
    if (typeof record.id === 'string' && typeof record.label === 'string' && record.label.trim()) {
      labels.set(record.id, record.label)
    }
  }
  return labels
}

function readablePath(value: string, nodeLabels: Map<string, string>) {
  return value
    .split('->')
    .map((part) => replaceNodeIds(part.trim(), nodeLabels))
    .join(' → ')
}

function replaceNodeIds(value: string, nodeLabels: Map<string, string>) {
  let result = value
  for (const [id, label] of nodeLabels) {
    result = result.split(id).join(label)
  }
  return result
}

onMounted(loadAll)
</script>

<style scoped>
.market-form input {
  width: 156px;
  height: 42px;
}

.market-form button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.market-hint {
  margin: -8px 0 0;
  border: 1px solid rgba(14, 143, 179, 0.14);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.78);
  color: var(--muted);
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.market-hint svg {
  color: var(--accent);
  flex-shrink: 0;
}

.market-hint span {
  color: var(--accent);
  font-weight: 700;
}

.market-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: stretch;
}

.metric-card {
  position: relative;
  overflow: hidden;
}

.metric-card::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 60px;
  height: 60px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.06), transparent);
  border-radius: 0 0 0 60px;
}

.chart-panel,
.analysis-panel {
  display: grid;
  gap: 16px;
}

.sparkline {
  min-height: 320px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: linear-gradient(180deg, #f8fbff, #f1f5f9);
  overflow: hidden;
}

.sparkline svg {
  display: block;
  width: 100%;
  height: 320px;
}

.sparkline polyline {
  fill: none;
  stroke: var(--accent);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.event-strip {
  display: grid;
  gap: 0;
  max-height: 240px;
  overflow: auto;
}

.event-strip article {
  display: flex;
  gap: 12px;
  padding: 10px 0;
}

.event-timeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
  flex-shrink: 0;
}

.event-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-2), #d97706);
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.3);
  flex-shrink: 0;
}

.event-line {
  width: 2px;
  flex: 1;
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.3), transparent);
  margin-top: 4px;
}

.event-strip article:last-child .event-line {
  display: none;
}

.event-body {
  display: grid;
  gap: 3px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--line);
  flex: 1;
}

.event-strip article:last-child .event-body {
  border-bottom: none;
}

.event-body span,
.event-body small {
  color: var(--muted);
  font-size: 12px;
}

.event-body strong {
  font-size: 14px;
  color: #0f172a;
}

.analysis-result {
  display: grid;
  gap: 14px;
}

.analysis-summary,
.analysis-columns article,
.analysis-list-card,
.fundamental-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: 16px;
}

.analysis-summary p {
  margin: 0;
  line-height: 1.7;
  color: #475569;
}

.confidence-meter {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.meter-source {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}

.meter-bar {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.8);
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #0ea5e9, #6366f1);
  transition: width 600ms cubic-bezier(0.4, 0, 0.2, 1);
}

.confidence-meter strong {
  font-size: 18px;
  color: #0f172a;
  white-space: nowrap;
}

.analysis-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.factor-panel {
  position: relative;
  overflow: hidden;
}

.factor-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
}

.factor-panel.opportunity::before {
  background: linear-gradient(90deg, #10b981, #059669);
}

.factor-panel.risk::before {
  background: linear-gradient(90deg, #ef4444, #dc2626);
}

.analysis-result ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.analysis-result ul li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 14px;
  line-height: 1.55;
  color: #334155;
}

.factor-icon-up {
  color: #10b981;
  flex-shrink: 0;
  margin-top: 2px;
}

.factor-icon-down {
  color: #ef4444;
  flex-shrink: 0;
  margin-top: 2px;
}

.insight-icon {
  color: var(--accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.warning-icon {
  color: var(--warning);
  flex-shrink: 0;
  margin-top: 2px;
}

.fundamental-card dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.fundamental-card div {
  border-radius: var(--radius-sm);
  background: rgba(241, 245, 249, 0.92);
  padding: 12px;
  border: 1px solid var(--line);
  transition: all 150ms ease;
}

.fundamental-card div:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
}

.fundamental-card dt {
  color: var(--muted);
  font-size: 12px;
}

.fundamental-card dd {
  margin: 6px 0 0;
  font-weight: 700;
  font-size: 15px;
  color: #0f172a;
}

.warning-card {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(145deg, rgba(254, 249, 195, 0.6), rgba(255, 251, 235, 0.8));
}

.disclaimer {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  line-height: 1.6;
  font-size: 12px;
}

.disclaimer svg {
  flex-shrink: 0;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 1080px) {
  .market-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .analysis-columns,
  .fundamental-card dl {
    grid-template-columns: 1fr;
  }
}
</style>
