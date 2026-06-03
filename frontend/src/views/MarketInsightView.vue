<template>
  <section class="page market-page">
    <div class="page-header">
      <div>
        <h1>行情研判</h1>
        <p>拉取真实行情、拼接图谱事件，并生成上市公司辅助研判。</p>
      </div>
      <form class="toolbar market-form" @submit.prevent="loadAll">
        <input
          id="market-stock-code"
          v-model="stockCode"
          name="stock_code"
          aria-label="股票代码"
          placeholder="600000"
          @input="markStockCodeEdited"
        />
        <input
          id="market-company-name"
          v-model="companyName"
          name="company_name"
          aria-label="公司名称"
          placeholder="浦发银行"
          @input="syncKnownStockCode"
        />
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
        <strong>{{ displayedKlineCount }}</strong>
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
            <span class="eyebrow">K 线蜡烛图</span>
            <h2>{{ klineDisplayTitle }}</h2>
          </div>
          <span v-if="kline?.cache_status" class="status">{{ kline.cache_status }}</span>
        </div>
        <div class="candlestick-chart" aria-label="OHLC 蜡烛图" data-testid="candlestick-chart">
          <div v-if="loading" class="empty-state">正在加载行情数据...</div>
          <svg v-else-if="candleChart" viewBox="0 0 640 260" preserveAspectRatio="none">
            <g class="chart-grid">
              <line
                v-for="line in candleChart.gridLines"
                :key="line.key"
                :x1="chartBounds.left"
                :x2="chartBounds.right"
                :y1="line.y"
                :y2="line.y"
              />
              <text
                v-for="label in candleChart.priceLabels"
                :key="label.key"
                :x="chartBounds.left - 8"
                :y="label.y + 4"
                text-anchor="end"
              >
                {{ label.text }}
              </text>
            </g>
            <g class="candles">
              <g v-for="candle in candleChart.candles" :key="candle.key" class="candle" :data-direction="candle.direction">
                <title>{{ candle.label }}</title>
                <line
                  class="candle-wick"
                  :x1="candle.x"
                  :x2="candle.x"
                  :y1="candle.highY"
                  :y2="candle.lowY"
                  :stroke="candle.color"
                />
                <rect
                  class="candle-body"
                  :x="candle.bodyX"
                  :y="candle.bodyY"
                  :width="candle.bodyWidth"
                  :height="candle.bodyHeight"
                  :fill="candle.fill"
                  :stroke="candle.color"
                  rx="1.5"
                />
              </g>
            </g>
            <g class="date-axis">
              <text
                v-for="label in candleChart.dateLabels"
                :key="label.key"
                :x="label.x"
                :y="chartBounds.bottom + 22"
                text-anchor="middle"
              >
                {{ label.text }}
              </text>
            </g>
          </svg>
          <div v-else class="empty-state">暂无行情数据。</div>
        </div>
        <p v-if="invalidKlinePointCount > 0" class="chart-data-note" data-testid="kline-filter-note">
          <AlertCircle :size="14" />
          已过滤 {{ invalidKlinePointCount }} 条异常行情点，蜡烛图仅展示合法 OHLC 数据。
        </p>
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
          <div class="analysis-actions">
            <span class="status" :class="newsSupplementStatus.tone" data-testid="news-status">
              {{ newsSupplementStatus.label }}
            </span>
            <button type="button" class="secondary" @click="loadSubmittedAnalysis(true)" :disabled="analysisLoading || !submittedCompanyName">
              <Sparkles v-if="!analysisLoading" :size="14" />
              <Loader2 v-else :size="14" class="spin" />
              {{ analysisLoading ? '生成中' : '模型增强 + 实时新闻' }}
            </button>
          </div>
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
          <article class="news-status-card" :data-status="newsSupplementStatus.tone" data-testid="news-status-detail">
            <Info :size="14" />
            <span>{{ newsSupplementStatus.detail }}</span>
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
import { useRoute, type RouteLocationNormalizedLoaded } from 'vue-router'
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
import { getKline, type KlinePoint, type KlineResponse } from '../api/market'
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
const analysisRefreshNewsRequested = ref(false)
const submittedCompanyName = ref('')
const submittedStockCode = ref('')
const DEFAULT_KLINE_STOCK_CODE = '600000'
const chartBounds = {
  width: 640,
  height: 260,
  left: 54,
  right: 622,
  top: 18,
  bottom: 226
} as const
let klineRequestSequence = 0
let analysisRequestSequence = 0
let route: RouteLocationNormalizedLoaded | null = null
try {
  route = useRoute()
} catch {
  route = null
}

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
    liveNewsCount: events.filter(isLiveNewsEvent).length,
    edgeCount: edges.length
  }
})

const newsSupplementStatus = computed(() => {
  if (analysisLoading.value && analysisRefreshNewsRequested.value) {
    return {
      label: '实时新闻补充中',
      detail: '正在请求实时新闻并交给模型合并研判，请稍候。',
      tone: 'warning'
    }
  }

  if (analysisError.value && analysisRefreshNewsRequested.value) {
    return {
      label: '实时新闻失败',
      detail: '模型增强或实时新闻请求失败，请稍后重试；当前页面保留已有图谱与行情结果。',
      tone: 'danger'
    }
  }

  if (!analysis.value || !analysisView.value) {
    return {
      label: '实时新闻待请求',
      detail: '完成查询后，可点击“模型增强 + 实时新闻”补充消息面。',
      tone: ''
    }
  }

  if (!analysisRefreshNewsRequested.value) {
    return {
      label: '本地图谱事件',
      detail: `当前使用本地图谱、基本面和 ${analysisView.value.eventCount} 条图谱事件；尚未请求实时新闻。`,
      tone: 'warning'
    }
  }

  const newsFallback = analysisView.value.missingData.find((item) => item.includes('新闻补充暂不可用'))
  if (newsFallback) {
    return {
      label: '实时新闻回退',
      detail: newsFallback,
      tone: 'warning'
    }
  }

  if (analysisView.value.liveNewsCount > 0) {
    return {
      label: `实时新闻 ${analysisView.value.liveNewsCount} 条`,
      detail: `已请求实时新闻补充，并合并 ${analysisView.value.liveNewsCount} 条实时新闻与 ${analysisView.value.eventCount} 条消息/图谱事件。`,
      tone: 'success'
    }
  }

  return {
    label: '实时新闻无新增',
    detail: '已请求实时新闻补充，后端未返回新增新闻；研判仍基于图谱事件、基本面和免责声明展示。',
    tone: 'warning'
  }
})

const validKlinePoints = computed(() => (kline.value?.kline_data ?? []).filter(isValidKlinePoint))
const invalidKlinePointCount = computed(() => Math.max(0, (kline.value?.kline_data.length ?? 0) - validKlinePoints.value.length))
const displayedKlineCount = computed(() => validKlinePoints.value.length)
const candleChart = computed(() => buildCandlestickChart(validKlinePoints.value))

async function loadAll() {
  const klineRequestId = ++klineRequestSequence
  loading.value = true
  error.value = ''
  analysisError.value = ''
  kline.value = null
  analysis.value = null
  analysisUsesLlm.value = false
  analysisRefreshNewsRequested.value = false
  submittedStockCode.value = ''
  submittedCompanyName.value = companyName.value.trim()
  try {
    const matchedCode = resolveKnownStockCode(companyName.value)
    if (matchedCode && !stockCodeEdited.value) {
      stockCode.value = matchedCode
    }
    const submittedCode = normalizeStockCode(stockCode.value)
    const queryStockCode = submittedCode || DEFAULT_KLINE_STOCK_CODE
    const queryCompanyName = companyName.value.trim() || queryStockCode
    submittedStockCode.value = submittedCode
    submittedCompanyName.value = queryCompanyName

    void loadAnalysis(false, queryStockCode, queryCompanyName, ++analysisRequestSequence)

    const klineResult = await getKline(queryStockCode, 'A', 'daily', queryCompanyName)
    if (klineRequestId === klineRequestSequence) {
      kline.value = klineResult
    }
  } catch (err) {
    if (klineRequestId === klineRequestSequence) {
      error.value = err instanceof Error ? err.message : '行情加载失败'
    }
  } finally {
    if (klineRequestId === klineRequestSequence) {
      loading.value = false
    }
  }
}

function loadSubmittedAnalysis(useLlm: boolean) {
  return loadAnalysis(
    useLlm,
    submittedStockCode.value || normalizeStockCode(stockCode.value),
    submittedCompanyName.value || companyName.value.trim() || normalizeStockCode(stockCode.value),
    ++analysisRequestSequence
  )
}

async function loadAnalysis(useLlm: boolean, queryStockCode: string, queryCompanyName: string, requestId: number) {
  analysisLoading.value = true
  analysisError.value = ''
  analysisRefreshNewsRequested.value = useLlm
  try {
    const result = await analyzeStock({
      stockCode: queryStockCode,
      companyName: queryCompanyName,
      refreshNews: useLlm,
      useLlm
    })
    if (requestId !== analysisRequestSequence) {
      return
    }
    analysis.value = result
    analysisUsesLlm.value = useLlm
  } catch (err) {
    if (requestId === analysisRequestSequence) {
      analysis.value = null
      analysisError.value = err instanceof Error ? err.message : '研判生成失败'
    }
  } finally {
    if (requestId === analysisRequestSequence) {
      analysisLoading.value = false
    }
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

function isLiveNewsEvent(value: unknown) {
  const record = asRecord(value)
  return Boolean(
    stringField(record.source_url, '') ||
    stringField(record.url, '') ||
    stringField(record.news_url, '')
  )
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

function isValidKlinePoint(point: KlinePoint) {
  const ohlc = [point.open, point.high, point.low, point.close]
  if (!point.date || !ohlc.every((value) => Number.isFinite(value) && value > 0)) {
    return false
  }

  return point.high >= Math.max(point.open, point.close, point.low) &&
    point.low <= Math.min(point.open, point.close, point.high)
}

function buildCandlestickChart(points: KlinePoint[]) {
  if (points.length === 0) {
    return null
  }

  const innerHeight = chartBounds.bottom - chartBounds.top
  const innerWidth = chartBounds.right - chartBounds.left
  const lows = points.map((point) => point.low)
  const highs = points.map((point) => point.high)
  const rawMin = Math.min(...lows)
  const rawMax = Math.max(...highs)
  const padding = (rawMax - rawMin || Math.max(rawMax, 1)) * 0.04
  const min = rawMin - padding
  const max = rawMax + padding
  const span = max - min || 1
  const slotWidth = innerWidth / points.length
  const bodyWidth = Math.min(14, Math.max(4, slotWidth * 0.48))
  const scaleY = (value: number) => chartBounds.top + ((max - value) / span) * innerHeight

  const candles = points.map((point, index) => {
    const x = chartBounds.left + slotWidth * (index + 0.5)
    const openY = scaleY(point.open)
    const closeY = scaleY(point.close)
    const highY = scaleY(point.high)
    const lowY = scaleY(point.low)
    const isRising = point.close >= point.open
    const color = isRising ? '#dc2626' : '#059669'
    const bodyY = Math.min(openY, closeY)
    const bodyHeight = Math.max(2, Math.abs(closeY - openY))

    return {
      key: `${point.date}-${index}`,
      x,
      highY,
      lowY,
      bodyX: x - bodyWidth / 2,
      bodyY,
      bodyWidth,
      bodyHeight,
      color,
      fill: isRising ? 'rgba(220, 38, 38, 0.22)' : 'rgba(5, 150, 105, 0.82)',
      direction: isRising ? 'up' : 'down',
      label: `${point.date} 开 ${point.open} 高 ${point.high} 低 ${point.low} 收 ${point.close}`
    }
  })
  const priceLabels = Array.from({ length: 5 }, (_, index) => {
    const value = max - (span / 4) * index
    const y = scaleY(value)
    return {
      key: `price-${index}`,
      y,
      text: value.toFixed(2)
    }
  })
  const gridLines = priceLabels.map((label) => ({
    key: `grid-${label.key}`,
    y: label.y
  }))
  const dateIndexes = Array.from(new Set([
    0,
    Math.floor((points.length - 1) / 2),
    points.length - 1
  ]))
  const dateLabels = dateIndexes.map((index) => ({
    key: `date-${index}`,
    x: chartBounds.left + slotWidth * (index + 0.5),
    text: points[index].date.slice(5)
  }))

  return {
    candles,
    priceLabels,
    gridLines,
    dateLabels
  }
}

onMounted(() => {
  const routeCompany = typeof route?.query.company === 'string' ? route.query.company : ''
  const routeStockCode = typeof route?.query.stock_code === 'string' ? route.query.stock_code : ''
  if (routeCompany) {
    companyName.value = routeCompany
  }
  if (routeStockCode) {
    stockCode.value = routeStockCode
    stockCodeEdited.value = true
  }
  void loadAll()
})
</script>

<style scoped>
.market-form input {
  width: 156px;
  height: 42px;
}

.market-form button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
}

.market-hint {
  margin: calc(var(--space-sm) * -1) 0 0;
  border: 1px solid rgba(14, 143, 179, 0.14);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.78);
  color: var(--muted);
  padding: var(--space-sm) var(--space-md);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 13px;
  box-shadow: var(--shadow-xs);
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
  gap: var(--space-xl);
  align-items: stretch;
}

.metric-card {
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-base) var(--ease-out);
}

.metric-card:hover {
  box-shadow: var(--shadow-md);
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
  transition: width var(--transition-slow) var(--ease-out),
              height var(--transition-slow) var(--ease-out);
}

.metric-card:hover::after {
  width: 80px;
  height: 80px;
}

.chart-panel,
.analysis-panel {
  display: grid;
  gap: var(--space-lg);
}

.candlestick-chart {
  min-height: 320px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(248, 251, 255, 0.96), rgba(241, 245, 249, 0.92)),
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.14), transparent 34%);
  overflow: hidden;
  position: relative;
  box-shadow: var(--shadow-md);
  transition: box-shadow var(--transition-base) var(--ease-out);
}

.candlestick-chart:hover {
  box-shadow: var(--shadow-lg);
}

.candlestick-chart svg {
  display: block;
  width: 100%;
  height: 320px;
}

.chart-grid line {
  stroke: rgba(148, 163, 184, 0.26);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.chart-grid text,
.date-axis text {
  fill: #64748b;
  font-size: 10px;
  font-weight: 600;
}

.candle-wick,
.candle-body {
  vector-effect: non-scaling-stroke;
}

.candle-wick {
  stroke-width: 1.4;
}

.candle-body {
  stroke-width: 1.6;
  transition: opacity var(--transition-fast) var(--ease-out),
              transform var(--transition-fast) var(--ease-out);
  transform-box: fill-box;
  transform-origin: center;
}

.candle:hover .candle-body {
  opacity: 0.82;
  transform: scaleY(1.06);
}

.chart-data-note {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  width: fit-content;
  margin: calc(var(--space-xs) * -1) 0 0;
  border: 1px solid rgba(245, 158, 11, 0.22);
  border-radius: 999px;
  background: rgba(255, 251, 235, 0.76);
  color: #92400e;
  padding: var(--space-xs) var(--space-sm);
  font-size: 12px;
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}

.chart-data-note svg {
  flex-shrink: 0;
}

.event-strip {
  display: grid;
  gap: 0;
  max-height: 240px;
  overflow: auto;
}

.event-strip article {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-sm) 0;
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
  box-shadow: 0 0 10px rgba(245, 158, 11, 0.4);
  flex-shrink: 0;
  transition: box-shadow var(--transition-base) var(--ease-out),
              transform var(--transition-fast) var(--ease-out);
}

.event-strip article:hover .event-dot {
  box-shadow: 0 0 14px rgba(245, 158, 11, 0.6);
  transform: scale(1.2);
}

.event-line {
  width: 2px;
  flex: 1;
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.3), transparent);
  margin-top: var(--space-xs);
}

.event-strip article:last-child .event-line {
  display: none;
}

.event-body {
  display: grid;
  gap: var(--space-xs);
  padding-bottom: var(--space-sm);
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
  gap: var(--space-md);
}

.analysis-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.analysis-summary,
.analysis-columns article,
.analysis-list-card,
.fundamental-card,
.news-status-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: var(--space-lg);
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base) var(--ease-out),
              transform var(--transition-fast) var(--ease-out);
}

.analysis-summary:hover,
.analysis-columns article:hover,
.analysis-list-card:hover,
.fundamental-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.analysis-summary p {
  margin: 0;
  line-height: 1.7;
  color: #475569;
}

.confidence-meter {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-top: var(--space-md);
  padding-top: var(--space-md);
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
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

.meter-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #0ea5e9, #6366f1);
  transition: width var(--transition-slow) var(--ease-out);
  box-shadow: 0 0 8px rgba(14, 165, 233, 0.3);
}

.confidence-meter strong {
  font-size: 18px;
  color: #0f172a;
  white-space: nowrap;
}

.analysis-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-md);
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
  gap: var(--space-sm);
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.analysis-result ul li {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
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
  gap: var(--space-sm);
  margin: 0;
}

.fundamental-card div {
  border-radius: var(--radius-sm);
  background: rgba(241, 245, 249, 0.92);
  padding: var(--space-md);
  border: 1px solid var(--line);
  transition: all var(--transition-fast) var(--ease-out);
}

.fundamental-card div:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.fundamental-card dt {
  color: var(--muted);
  font-size: 12px;
}

.fundamental-card dd {
  margin: var(--space-xs) 0 0;
  font-weight: 700;
  font-size: 15px;
  color: #0f172a;
}

.warning-card {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(145deg, rgba(254, 249, 195, 0.6), rgba(255, 251, 235, 0.8));
}

.news-status-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.news-status-card svg {
  color: var(--accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.news-status-card[data-status="success"] {
  border-color: rgba(16, 185, 129, 0.28);
  background: linear-gradient(145deg, rgba(236, 253, 245, 0.78), rgba(209, 250, 229, 0.42));
}

.news-status-card[data-status="warning"] {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(145deg, rgba(254, 249, 195, 0.6), rgba(255, 251, 235, 0.8));
}

.news-status-card[data-status="danger"] {
  border-color: rgba(239, 68, 68, 0.28);
  background: linear-gradient(145deg, rgba(254, 242, 242, 0.76), rgba(254, 226, 226, 0.45));
}

.disclaimer {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
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
