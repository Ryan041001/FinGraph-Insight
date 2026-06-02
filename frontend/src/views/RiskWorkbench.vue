<template>
  <section class="page workbench-page">
    <div class="page-header">
      <div>
        <h1>风险工作台</h1>
        <p>输入企业名称，自动汇总图谱、数据集事件、实时新闻和 AI 研判。</p>
      </div>
      <CompanySearch
        v-model="keyword"
        :loading="loading"
        :active-query="activeRequestQuery"
        :options="companyOptions"
        @search="loadCompany"
      />
    </div>

    <div v-if="error" class="panel state-panel">
      <strong>未能完成本次分析</strong>
      <p>{{ error }}</p>
      <button type="button" @click="loadCompany(keyword)">重试</button>
    </div>

    <div v-else-if="loading" class="panel state-panel">
      正在分析关联风险...
    </div>

    <div v-else-if="model" class="workbench-layout">
      <section class="panel graph-workspace">
        <div class="graph-workspace-header">
          <div class="panel-title-row">
            <div>
              <span class="eyebrow">关联网络</span>
              <h2>关系图谱</h2>
            </div>
          </div>
        </div>
        <div class="graph-workspace-main">
          <RelationFilterBar
            v-model:depth="depth"
            :relation-types="relationTypes"
            :selected-types="selectedRelationTypes"
            @toggle-type="toggleRelationType"
          />
          <RiskGraphCanvas
            :nodes="filteredNodes"
            :edges="filteredEdges"
            :highlighted-relation-ids="highlightedRelationIds"
            @select-edge="selectEdge"
          />
          <div v-if="hasHighlightedRelations" class="selection-banner">
            <span>已筛选 {{ highlightedRelationIds.length }} 条相关关系</span>
            <button
              type="button"
              class="secondary"
              data-testid="clear-relation-filter"
              @click="clearHighlightedRelations"
            >
              清除筛选
            </button>
          </div>
        </div>
        <aside class="graph-workspace-side" aria-label="搜索对象与快捷操作">
          <CompanyProfilePanel :company="model.company" />
          <section class="market-mini-module">
            <span class="eyebrow">上市公司行情</span>
            <h3>{{ listedStockCode ? 'K 线与事件' : '待识别股票代码' }}</h3>
            <p>
              {{ listedStockCode
                ? '作为企业节点的补充视图，查看蜡烛图、图谱事件和实时新闻增强研判。'
                : '当前图谱节点没有股票代码，行情模块可继续查询浦发银行、招商银行等上市公司。'
              }}
            </p>
            <a class="market-module-link" :href="marketInsightLink">
              {{ listedStockCode ? '打开行情模块' : '查询上市公司行情' }}
            </a>
          </section>
          <section class="quick-actions">
            <span class="eyebrow">快捷操作</span>
            <button type="button" class="secondary" @click="addToWatchlist">加入关注</button>
            <button type="button" @click="saveCurrentReport">保存报告</button>
          </section>
        </aside>
        <div class="graph-workspace-lower">
          <section class="panel evidence-hub-panel graph-workspace-evidence-hub" data-testid="evidence-hub-panel">
            <div class="panel-title-row">
              <div>
                <span class="eyebrow">自动证据</span>
                <h2>数据集与新闻证据</h2>
              </div>
              <div class="evidence-actions">
                <span class="status" :class="evidenceStatus.tone" data-testid="evidence-status">
                  {{ evidenceStatus.label }}
                </span>
                <button
                  type="button"
                  class="secondary"
                  :disabled="evidenceLoading"
                  @click="loadCompanyEvidence(true)"
                >
                  <Sparkles v-if="!evidenceLoading" :size="14" />
                  <Loader2 v-else :size="14" class="spin" />
                  {{ evidenceLoading ? '抓取中' : '刷新实时新闻 + AI研判' }}
                </button>
              </div>
            </div>
            <p class="evidence-hub-copy">
              以当前企业为唯一入口，自动汇总本地图谱、数据集事件和可用实时新闻，再交给模型生成研判；无需手动粘贴新闻文本。
            </p>
            <div class="evidence-stat-row">
              <article>
                <span>数据集/图谱事件</span>
                <strong>{{ graphEvidenceCount }}</strong>
              </article>
              <article>
                <span>实时新闻</span>
                <strong>{{ liveNewsCount }}</strong>
              </article>
              <article>
                <span>研判置信度</span>
                <strong>{{ analysisConfidenceLabel }}</strong>
              </article>
            </div>
            <div v-if="evidenceLoading && !evidenceAnalysis" class="state-panel">
              正在整理本地图谱事件和数据集证据...
            </div>
            <div v-else-if="evidenceError" class="state-panel error">
              {{ evidenceError }}
            </div>
            <template v-else>
              <article v-if="analysisSummary" class="analysis-brief-card">
                <span class="eyebrow">{{ analysisBriefTitle }}</span>
                <p>{{ analysisSummary }}</p>
                <ul v-if="analysisMissingData.length > 0">
                  <li v-for="item in analysisMissingData" :key="item">{{ item }}</li>
                </ul>
              </article>
              <div v-if="newsEvidenceItems.length > 0" class="news-evidence-list" data-testid="news-evidence-list">
                <article v-for="item in newsEvidenceItems" :key="item.id" class="news-evidence-card" :data-source="item.sourceKind">
                  <div class="news-evidence-meta">
                    <span class="source-pill">{{ item.sourceLabel }}</span>
                    <time>{{ item.date }}</time>
                    <span v-if="item.sentiment" class="sentiment-pill">{{ item.sentiment }}</span>
                  </div>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.evidence }}</p>
                  <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer">查看新闻来源</a>
                </article>
              </div>
              <p v-else class="muted">暂无可列出的新闻或图谱事件。可点击“刷新实时新闻 + AI研判”补充消息面。</p>
            </template>
          </section>
          <RiskSummaryPanel
            :risk="model.risk"
            :selected-relation-ids="highlightedRelationIds"
            @select-factor="highlightRelations"
          />
          <section class="workspace-subpanel graph-workspace-paths">
            <div class="panel-title-row">
              <div>
                <span class="eyebrow">关联路径</span>
                <h3>路径列表</h3>
              </div>
            </div>
            <div v-if="visiblePaths.length > 0" class="list path-list" data-testid="path-list">
              <article
                v-for="path in visiblePaths"
                :key="path.id"
                class="list-item path-row"
                :class="{ 'selected-row': isRelationMatch(path.relationIds) }"
                :data-risk="path.riskLevel"
                data-testid="path-row"
              >
                <strong>{{ path.label }}</strong>
                <p class="muted">风险标签：{{ riskLevelLabel(path.riskLevel) }} ｜ 相关证据 {{ evidenceCountForPath(path.relationIds) }} 条</p>
              </article>
            </div>
            <p v-else class="muted">暂无可展示关系路径。</p>
          </section>
          <EvidenceDrawer :evidence="visibleEvidence" :selected-relation-id="selectedRelationId" />
        </div>
      </section>
      <div class="workbench-detail-grid">
        <QueryWorkbenchPanel :company-name="model.company.name" />
        <ReportPreview :model="model" />
      </div>
    </div>
    <div v-else class="panel state-panel">
      未查询到图谱数据，请从候选企业中选择或在数据任务页确认基础数据已导入。
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { useRoute, type RouteLocationNormalizedLoaded } from 'vue-router'
import { Loader2, Sparkles } from 'lucide-vue-next'
import type { CompanySearchItem, GraphEdge } from '../api/types'
import CompanyProfilePanel from '../components/CompanyProfilePanel.vue'
import CompanySearch from '../components/CompanySearch.vue'
import EvidenceDrawer from '../components/EvidenceDrawer.vue'
import RelationFilterBar from '../components/RelationFilterBar.vue'
import ReportPreview from '../components/ReportPreview.vue'
import QueryWorkbenchPanel from '../components/QueryWorkbenchPanel.vue'
import RiskSummaryPanel from '../components/RiskSummaryPanel.vue'
import { analyzeStock } from '../api/analysis'
import { getCompanyProfile, searchCompanies } from '../api/graph'
import { buildRiskWorkbenchModel } from '../product/riskAdapter'
import { saveReport, saveWatchlistItem } from '../product/storage'
import type { RiskWorkbenchModel } from '../product/types'

const DEFAULT_COMPANY_NAME = '邦盛科技'
const RiskGraphCanvas = defineAsyncComponent(() => import('../components/RiskGraphCanvas.vue'))
let route: RouteLocationNormalizedLoaded | null = null
try {
  route = useRoute()
} catch {
  route = null
}

const keyword = ref(DEFAULT_COMPANY_NAME)
const loading = ref(false)
const error = ref('')
const model = ref<RiskWorkbenchModel | null>(null)
const highlightedRelationIds = ref<string[]>([])
const activeRequestQuery = ref('')
const depth = ref(2)
const selectedRelationId = ref('')
const selectedRelationTypes = ref<string[]>([])
const evidenceLoading = ref(false)
const evidenceError = ref('')
const evidenceAnalysis = ref<Record<string, unknown> | null>(null)
const evidenceRealtimeRequested = ref(false)
const companyOptions = ref<CompanySearchItem[]>([
  { id: 'company_0baf1af79a1c1f67', name: '邦盛科技', industry: '金融科技' },
  { id: 'demo-guotou', name: '国投创业', industry: '投资机构' }
])
let requestSequence = 0
let evidenceRequestSequence = 0
let searchOptionTimer: number | undefined

const highlightedRelationIdSet = computed(() => new Set(highlightedRelationIds.value))
const hasHighlightedRelations = computed(() => highlightedRelationIds.value.length > 0)
const relationTypes = computed(() => Array.from(new Set(model.value?.graph.edges.map((edge) => edge.label) ?? [])))
const centerNodeId = computed(() => {
  if (!model.value) {
    return ''
  }

  const matchingCompanyNode = model.value.graph.nodes.find((node) => {
    return node.id === model.value?.company.id || node.label === model.value?.company.name
  })
  const firstCompanyNode = model.value.graph.nodes.find((node) => node.type.trim().toLowerCase() === 'company')

  return matchingCompanyNode?.id ?? firstCompanyNode?.id ?? model.value.graph.nodes[0]?.id ?? ''
})
const visibleNodeIdSet = computed(() => {
  if (!model.value || !centerNodeId.value) {
    return new Set<string>()
  }

  const adjacency = new Map<string, string[]>()
  for (const edge of model.value.graph.edges) {
    adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target])
    adjacency.set(edge.target, [...(adjacency.get(edge.target) ?? []), edge.source])
  }

  const distances = new Map<string, number>([[centerNodeId.value, 0]])
  const queue = [centerNodeId.value]

  while (queue.length > 0) {
    const currentNodeId = queue.shift()!
    const currentDistance = distances.get(currentNodeId) ?? 0

    if (currentDistance >= depth.value) {
      continue
    }

    for (const nextNodeId of adjacency.get(currentNodeId) ?? []) {
      if (!distances.has(nextNodeId)) {
        distances.set(nextNodeId, currentDistance + 1)
        queue.push(nextNodeId)
      }
    }
  }

  return new Set(Array.from(distances.keys()))
})
const depthFilteredEdgeIds = computed(() => {
  if (!model.value) {
    return new Set<string>()
  }

  return new Set(model.value.graph.edges
    .filter((edge) => visibleNodeIdSet.value.has(edge.source) && visibleNodeIdSet.value.has(edge.target))
    .map((edge) => edge.id))
})
const filteredNodes = computed(() => {
  if (!model.value) {
    return []
  }

  return model.value.graph.nodes.filter((node) => visibleNodeIdSet.value.has(node.id))
})
const filteredEdges = computed(() => {
  const edges = model.value?.graph.edges ?? []
  const depthFilteredEdges = edges.filter((edge) => depthFilteredEdgeIds.value.has(edge.id))

  if (selectedRelationTypes.value.length === 0) {
    return depthFilteredEdges
  }

  return depthFilteredEdges.filter((edge) => selectedRelationTypes.value.includes(edge.label))
})
const filteredRelationIdSet = computed(() => new Set(filteredEdges.value.map((edge) => edge.id)))
const evidenceAnalysisBlock = computed(() => asRecord(evidenceAnalysis.value?.analysis))
const analysisSummary = computed(() => stringField(evidenceAnalysisBlock.value.summary, ''))
const analysisMissingData = computed(() => stringList(evidenceAnalysisBlock.value.missing_data))
const analysisBriefTitle = computed(() => {
  if (analysisMissingData.value.some((item) => item.includes('模型研判暂不可用'))) {
    return '本地回退摘要'
  }
  return evidenceRealtimeRequested.value ? 'AI 研判摘要' : '本地研判摘要'
})
const analysisConfidenceLabel = computed(() => {
  const confidence = numberField(evidenceAnalysisBlock.value.confidence, 0)
  return confidence > 0 ? `${Math.round(confidence * 100)}%` : '-'
})
const rawNewsEvents = computed(() => {
  const events = evidenceAnalysis.value?.news_events
  return Array.isArray(events) ? events : []
})
const newsEvidenceItems = computed(() => rawNewsEvents.value.map(toNewsEvidenceItem).filter((item) => item.title))
const liveNewsCount = computed(() => newsEvidenceItems.value.filter((item) => item.sourceKind === 'live').length)
const graphEvidenceCount = computed(() => newsEvidenceItems.value.filter((item) => item.sourceKind === 'graph').length)
const evidenceStatus = computed(() => {
  if (evidenceLoading.value && evidenceRealtimeRequested.value) {
    return { label: '实时新闻抓取中', tone: 'warning' }
  }
  if (evidenceLoading.value) {
    return { label: '整理本地证据', tone: 'warning' }
  }
  if (evidenceError.value) {
    return { label: '证据更新失败', tone: 'danger' }
  }
  if (!evidenceAnalysis.value) {
    return { label: '等待企业查询', tone: '' }
  }
  if (!evidenceRealtimeRequested.value) {
    return { label: '本地数据集证据', tone: 'warning' }
  }
  if (analysisMissingData.value.some((item) => item.includes('新闻补充暂不可用') || item.includes('模型研判暂不可用'))) {
    return { label: '部分能力回退', tone: 'warning' }
  }
  if (liveNewsCount.value > 0) {
    return { label: `实时新闻 ${liveNewsCount.value} 条`, tone: 'success' }
  }
  return { label: '实时新闻无新增', tone: 'warning' }
})
const marketInsightLink = computed(() => {
  const stockCode = listedStockCode.value
  if (!stockCode) {
    return '/market'
  }

  const params = new URLSearchParams({ company: model.value?.company.name ?? '', stock_code: stockCode })
  return `/market?${params.toString()}`
})
const listedStockCode = computed(() => {
  const companyName = model.value?.company.name ?? ''
  const companyNode = model.value?.graph.nodes.find((node) => node.label === companyName || node.id === model.value?.company.id)
  const stockCode = companyNode?.properties.stock_code
    ?? companyNode?.properties.display_code
    ?? knownMarketStockCode(companyName)

  return typeof stockCode === 'string' ? stockCode.split('.')[0].trim() : ''
})
const visiblePaths = computed(() => {
  if (!model.value) {
    return []
  }

  const paths = model.value.paths.filter((path) => path.relationIds.some((relationId) => filteredRelationIdSet.value.has(relationId)))

  if (!hasHighlightedRelations.value) {
    return paths
  }

  return paths.filter((path) => isRelationMatch(path.relationIds))
})
const visibleEvidence = computed(() => {
  if (!model.value) {
    return []
  }

  const evidence = model.value.evidence.filter((item) => filteredRelationIdSet.value.has(item.relationId))

  if (!hasHighlightedRelations.value) {
    return evidence
  }

  return evidence.filter((item) => highlightedRelationIdSet.value.has(item.relationId))
})

async function loadCompany(value: string) {
  const query = value.trim()

  if (loading.value && query === activeRequestQuery.value) {
    return
  }

  const requestId = ++requestSequence
  evidenceRequestSequence += 1
  evidenceLoading.value = false
  evidenceError.value = ''
  evidenceAnalysis.value = null
  evidenceRealtimeRequested.value = false
  highlightedRelationIds.value = []
  selectedRelationId.value = ''
  selectedRelationTypes.value = []

  if (!query) {
    activeRequestQuery.value = ''
    loading.value = false
    error.value = '请输入企业名称或股票代码。'
    return
  }

  activeRequestQuery.value = query
  loading.value = true
  error.value = ''
  try {
    const profile = await getCompanyProfile(query)
    if (requestId !== requestSequence) {
      return
    }

    if (profile.found === false || (profile.graph.nodes.length === 0 && profile.graph.edges.length === 0)) {
      model.value = null
      error.value = ''
      await loadFallbackCompany(requestId)
      return
    }

    model.value = buildRiskWorkbenchModel(profile)
    void loadCompanyEvidence(false)
  } catch {
    if (requestId !== requestSequence) {
      return
    }

    error.value = '服务暂不可用，请稍后重试。'
  } finally {
    if (requestId === requestSequence) {
      loading.value = false
      activeRequestQuery.value = ''
    }
  }
}

async function loadCompanyEvidence(useRealtimeAndLlm: boolean) {
  if (!model.value) {
    return
  }

  const requestId = ++evidenceRequestSequence
  evidenceLoading.value = true
  evidenceError.value = ''
  evidenceRealtimeRequested.value = useRealtimeAndLlm
  try {
    const result = await analyzeStock({
      stockCode: listedStockCode.value,
      companyName: model.value.company.name,
      refreshNews: useRealtimeAndLlm,
      useLlm: useRealtimeAndLlm
    })
    if (requestId !== evidenceRequestSequence) {
      return
    }
    evidenceAnalysis.value = result
  } catch {
    if (requestId === evidenceRequestSequence) {
      evidenceError.value = '证据和新闻研判暂不可用，请稍后重试；图谱、路径和证据链仍可继续查看。'
    }
  } finally {
    if (requestId === evidenceRequestSequence) {
      evidenceLoading.value = false
    }
  }
}

async function loadFallbackCompany(requestId: number) {
  try {
    const fallbackCandidates = await searchCompanies(DEFAULT_COMPANY_NAME, 1)
    const fallbackName = fallbackCandidates.companies[0]?.name ?? DEFAULT_COMPANY_NAME
    if (requestId !== requestSequence) {
      return
    }

    if (fallbackName && fallbackName !== keyword.value) {
      keyword.value = fallbackName
    }
    await loadCompany(fallbackName)
  } catch {
    // Keep the empty state if the fallback search cannot resolve a company.
  }
}

watch(keyword, (value) => {
  window.clearTimeout(searchOptionTimer)
  searchOptionTimer = window.setTimeout(async () => {
    try {
      const result = await searchCompanies(value.trim(), 8)
      if (result.companies.length > 0) {
        companyOptions.value = result.companies
      }
    } catch {
      // Keep the last useful suggestions; search is an enhancement, not a blocker.
    }
  }, 260)
})

function highlightRelations(relationIds: string[]) {
  selectedRelationId.value = ''
  highlightedRelationIds.value = [...new Set(relationIds)]
}

function clearHighlightedRelations() {
  highlightedRelationIds.value = []
  selectedRelationId.value = ''
}

function isRelationMatch(relationIds: string[]) {
  if (!hasHighlightedRelations.value) {
    return false
  }

  return relationIds.some((relationId) => highlightedRelationIdSet.value.has(relationId))
}

function evidenceCountForPath(relationIds: string[]) {
  if (!model.value) {
    return 0
  }

  const relationIdSet = new Set(relationIds)

  return model.value.evidence.filter((item) => relationIdSet.has(item.relationId)).length
}

function riskLevelLabel(level: RiskWorkbenchModel['risk']['level']) {
  const labels: Record<RiskWorkbenchModel['risk']['level'], string> = {
    high: '高风险',
    medium: '中风险',
    low: '低风险',
    unknown: '待补充数据'
  }

  return labels[level]
}

function toggleRelationType(type: string) {
  selectedRelationTypes.value = selectedRelationTypes.value.includes(type)
    ? selectedRelationTypes.value.filter((item) => item !== type)
    : [...selectedRelationTypes.value, type]
}

function selectEdge(edge: GraphEdge) {
  selectedRelationId.value = edge.id
  highlightedRelationIds.value = [edge.id]
}

function addToWatchlist() {
  if (!model.value) {
    return
  }

  saveWatchlistItem({
    companyName: model.value.company.name,
    industry: model.value.company.industry,
    riskLevel: model.value.risk.level,
    summary: model.value.risk.summary,
    updatedAt: new Date().toISOString()
  })
}

function saveCurrentReport() {
  if (!model.value) {
    return
  }

  saveReport({
    id: createReportId(model.value.company.id),
    companyName: model.value.company.name,
    riskLevel: model.value.risk.level,
    summary: model.value.risk.summary,
    factors: model.value.risk.factors.map((factor) => ({
      level: factor.level,
      title: factor.title,
      description: factor.description
    })),
    evidence: model.value.evidence.map((item) => ({
      title: item.title,
      text: item.text,
      source: item.source,
      confidence: item.confidence,
      date: item.date
    })),
    createdAt: new Date().toISOString()
  })
}

function createReportId(companyId: string) {
  const randomId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`

  return `${companyId}-${randomId}`
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}

function stringField(value: unknown, fallback = '-') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function numberField(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function stringList(value: unknown) {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map((item) => typeof item === 'string' ? item.trim() : '').filter(Boolean)
}

function toNewsEvidenceItem(value: unknown, index: number) {
  const event = asRecord(value)
  const url = stringField(event.source_url || event.url || event.news_url, '')
  const sourceKind = url ? 'live' : 'graph'
  return {
    id: `${sourceKind}-${stringField(event.title, 'event')}-${index}`,
    title: stringField(event.title || event.label, ''),
    date: stringField(event.date, '未标注日期'),
    evidence: stringField(event.evidence || event.description, '暂无摘要或证据片段。'),
    url,
    sentiment: stringField(event.sentiment, ''),
    sourceKind,
    sourceLabel: sourceKind === 'live' ? '实时新闻' : '数据集/图谱'
  }
}

function knownMarketStockCode(companyName: string) {
  const knownCodes: Record<string, string> = {
    浦发银行: '600000',
    招商银行: '600036',
    平安银行: '000001',
    中国平安: '601318',
    贵州茅台: '600519',
    比亚迪: '002594'
  }

  return knownCodes[companyName] ?? ''
}

onMounted(() => {
  const routeCompany = typeof route?.query.company === 'string' ? route.query.company : ''
  if (routeCompany) {
    keyword.value = routeCompany
  }
  void loadCompany(keyword.value).then(() => {
    if (!model.value) {
      void loadFallbackCompany(requestSequence)
    }
  })
})
</script>

<style scoped>
.workbench-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  align-items: start;
}

.graph-workspace {
  display: grid;
  grid-template-columns: minmax(0, 3.2fr) minmax(280px, 0.9fr);
  gap: 12px;
  align-items: start;
  background:
    linear-gradient(135deg, rgba(14, 165, 233, 0.06), rgba(245, 158, 11, 0.04)),
    var(--panel);
}

.graph-workspace-header {
  grid-column: 1 / -1;
  min-width: 0;
}

.graph-workspace-main,
.graph-workspace-side {
  min-width: 0;
}

.graph-workspace-main {
  display: grid;
  gap: 12px;
}

.graph-workspace-main :deep(.risk-graph-canvas) {
  min-height: clamp(560px, 50vh, 700px);
}

.graph-workspace-side {
  display: grid;
  grid-template-rows: auto auto minmax(140px, 1fr);
  gap: 12px;
  align-self: stretch;
}

.graph-workspace-lower {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: minmax(260px, 0.95fr) minmax(320px, 1.1fr) minmax(340px, 1.35fr);
  gap: 12px;
  align-items: stretch;
  padding-top: 0;
}

.graph-workspace-lower :deep(.panel),
.workspace-subpanel {
  min-width: 0;
  box-shadow: none;
}

.workspace-subpanel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(241, 247, 252, 0.84));
  padding: 18px;
}

.graph-workspace-lower :deep(.panel),
.workspace-subpanel {
  height: 100%;
}

.quick-actions {
  display: grid;
  gap: 10px;
  align-content: start;
  border: 1px solid rgba(183, 121, 31, 0.18);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(255, 251, 235, 0.88), rgba(236, 253, 245, 0.7)),
    var(--panel-soft);
  padding: 14px;
}

.market-mini-module {
  display: grid;
  gap: 9px;
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(14, 165, 233, 0.10), rgba(236, 253, 245, 0.72)),
    var(--panel-soft);
  padding: 14px;
}

.market-mini-module h3 {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
}

.market-mini-module p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}

.market-module-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  border: 1px solid rgba(14, 143, 179, 0.28);
  border-radius: 8px;
  color: #075985;
  background: rgba(255, 255, 255, 0.82);
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
  transition: all 160ms ease;
}

.market-module-link:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
  border-color: var(--accent);
}

.workbench-detail-grid {
  display: grid;
  gap: 18px;
  align-items: start;
}

.evidence-hub-panel {
  display: grid;
  gap: 14px;
}

.graph-workspace-evidence-hub {
  grid-column: 1 / -1;
}

.evidence-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.evidence-actions button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.evidence-hub-copy {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
  font-size: 14px;
}

.evidence-stat-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.evidence-stat-row article {
  border: 1px solid var(--line);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(241, 247, 252, 0.84));
  padding: 14px;
}

.evidence-stat-row span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.evidence-stat-row strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 22px;
}

.analysis-brief-card {
  border: 1px solid rgba(14, 143, 179, 0.18);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(14, 165, 233, 0.09), rgba(236, 253, 245, 0.62)),
    #ffffff;
  padding: 15px;
}

.analysis-brief-card p {
  margin: 0;
  color: #334155;
  line-height: 1.65;
}

.analysis-brief-card ul {
  margin: 12px 0 0;
  padding-left: 18px;
  color: #92400e;
  font-size: 13px;
  line-height: 1.55;
}

.news-evidence-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.news-evidence-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.9));
  padding: 14px;
  min-width: 0;
}

.news-evidence-card[data-source="live"] {
  border-color: rgba(16, 185, 129, 0.24);
  background: linear-gradient(145deg, rgba(236, 253, 245, 0.72), rgba(255, 255, 255, 0.94));
}

.news-evidence-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
}

.source-pill,
.sentiment-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
}

.source-pill {
  background: rgba(14, 165, 233, 0.1);
  color: #0369a1;
}

.sentiment-pill {
  background: rgba(148, 163, 184, 0.15);
  color: #475569;
}

.news-evidence-card strong {
  color: #0f172a;
  line-height: 1.45;
}

.news-evidence-card p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}

.news-evidence-card a {
  color: #0e7490;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.news-evidence-card a:hover {
  text-decoration: underline;
}

.workbench-detail-grid :deep(.query-workbench),
.workbench-detail-grid :deep(.report-preview) {
  grid-column: auto;
}

.graph-workspace h3 {
  margin: 0;
}

.selection-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border: 1px solid rgba(14, 143, 179, 0.26);
  border-radius: 8px;
  background: rgba(14, 165, 233, 0.10);
  color: #075985;
  padding: 10px 12px;
}

.path-row,
.evidence-row {
  border-left: 4px solid transparent;
}

.selected-row {
  border-left-color: var(--accent);
  background: rgba(14, 165, 233, 0.10);
}

.path-row[data-risk="high"] strong {
  color: var(--danger);
}

.path-row[data-risk="medium"] strong {
  color: var(--accent-2);
}

@media (max-width: 1100px) {
  .workbench-layout,
  .graph-workspace,
  .graph-workspace-lower,
  .workbench-detail-grid,
  .evidence-stat-row,
  .news-evidence-list {
    grid-template-columns: 1fr;
  }

  .workbench-detail-grid :deep(.query-workbench),
  .workbench-detail-grid :deep(.report-preview) {
    grid-column: span 1;
  }
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
