<template>
  <section class="page workbench-page">
    <div class="page-header">
      <div>
        <h1>风险工作台</h1>
        <p>输入企业名称，查看风险摘要、关联路径和证据链。</p>
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
          <section class="quick-actions">
            <span class="eyebrow">快捷操作</span>
            <button type="button" class="secondary" @click="addToWatchlist">加入关注</button>
            <button type="button" @click="saveCurrentReport">保存报告</button>
          </section>
        </aside>
        <div class="graph-workspace-lower">
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
      <aside class="workbench-followup">
        <AskPanel :company-name="model.company.name" />
      </aside>
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
import type { CompanySearchItem, GraphEdge } from '../api/types'
import AskPanel from '../components/AskPanel.vue'
import CompanyProfilePanel from '../components/CompanyProfilePanel.vue'
import CompanySearch from '../components/CompanySearch.vue'
import EvidenceDrawer from '../components/EvidenceDrawer.vue'
import RelationFilterBar from '../components/RelationFilterBar.vue'
import ReportPreview from '../components/ReportPreview.vue'
import QueryWorkbenchPanel from '../components/QueryWorkbenchPanel.vue'
import RiskSummaryPanel from '../components/RiskSummaryPanel.vue'
import { getCompanyProfile, searchCompanies } from '../api/graph'
import { buildRiskWorkbenchModel } from '../product/riskAdapter'
import { saveReport, saveWatchlistItem } from '../product/storage'
import type { RiskWorkbenchModel } from '../product/types'

const DEFAULT_COMPANY_NAME = '浙江数科控股有限公司'
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
const companyOptions = ref<CompanySearchItem[]>([
  { id: 'company_0baf1af79a1c1f67', name: '邦盛科技', industry: '金融科技' },
  { id: 'demo-guotou', name: '国投创业', industry: '投资机构' }
])
let requestSequence = 0
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

async function loadFallbackCompany(requestId: number) {
  try {
    const fallbackCandidates = await searchCompanies('', 1)
    const fallbackName = fallbackCandidates.companies[0]?.name ?? '邦盛科技'
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
  grid-template-rows: auto minmax(140px, 1fr);
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

.workbench-followup {
  display: grid;
  align-items: start;
  margin-top: -4px;
}

.workbench-detail-grid {
  display: grid;
  gap: 18px;
  align-items: start;
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
  .workbench-followup,
  .workbench-detail-grid {
    grid-template-columns: 1fr;
  }

  .workbench-detail-grid :deep(.query-workbench),
  .workbench-detail-grid :deep(.report-preview) {
    grid-column: span 1;
  }
}
</style>
