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

    <div v-else-if="model" class="workbench-grid">
      <aside class="workbench-left">
        <CompanyProfilePanel :company="model.company" />
        <button type="button" class="secondary" @click="addToWatchlist">加入关注</button>
        <RiskSummaryPanel
          :risk="model.risk"
          :selected-relation-ids="highlightedRelationIds"
          @select-factor="highlightRelations"
        />
      </aside>
      <section class="panel workbench-main">
        <div class="panel-title-row">
          <div>
            <span class="eyebrow">关联网络</span>
            <h2>关系图谱</h2>
          </div>
        </div>
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
        <h3>关联路径</h3>
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
      <aside class="workbench-right">
        <EvidenceDrawer :evidence="visibleEvidence" :selected-relation-id="selectedRelationId" />
        <AskPanel :company-name="model.company.name" />
        <ReportPreview :model="model" @save-report="saveCurrentReport" />
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import type { GraphEdge } from '../api/types'
import AskPanel from '../components/AskPanel.vue'
import CompanyProfilePanel from '../components/CompanyProfilePanel.vue'
import CompanySearch from '../components/CompanySearch.vue'
import EvidenceDrawer from '../components/EvidenceDrawer.vue'
import RelationFilterBar from '../components/RelationFilterBar.vue'
import ReportPreview from '../components/ReportPreview.vue'
import RiskSummaryPanel from '../components/RiskSummaryPanel.vue'
import { getCompanyProfile } from '../api/graph'
import { buildRiskWorkbenchModel } from '../product/riskAdapter'
import { saveReport, saveWatchlistItem } from '../product/storage'
import type { RiskWorkbenchModel } from '../product/types'

const DEFAULT_COMPANY_NAME = '浙江数科控股有限公司'
const RiskGraphCanvas = defineAsyncComponent(() => import('../components/RiskGraphCanvas.vue'))

const keyword = ref(DEFAULT_COMPANY_NAME)
const loading = ref(false)
const error = ref('')
const model = ref<RiskWorkbenchModel | null>(null)
const highlightedRelationIds = ref<string[]>([])
const activeRequestQuery = ref('')
const depth = ref(2)
const selectedRelationId = ref('')
const selectedRelationTypes = ref<string[]>([])
let requestSequence = 0

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
  void loadCompany(keyword.value)
})
</script>

<style scoped>
.workbench-grid {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(280px, 360px);
  gap: 18px;
  align-items: start;
}

.workbench-left {
  display: grid;
  gap: 18px;
}

.workbench-main,
.workbench-right {
  display: grid;
  gap: 12px;
}

.workbench-main h3 {
  margin: 8px 0 0;
}

.selection-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border: 1px solid #99f6e4;
  border-radius: 8px;
  background: #f0fdfa;
  color: #115e59;
  padding: 10px 12px;
}

.path-row,
.evidence-row {
  border-left: 4px solid transparent;
}

.selected-row {
  border-left-color: var(--accent);
  background: #f0fdfa;
}

.path-row[data-risk="high"] strong {
  color: var(--danger);
}

.path-row[data-risk="medium"] strong {
  color: var(--accent-2);
}

@media (max-width: 1100px) {
  .workbench-grid {
    grid-template-columns: 1fr;
  }
}
</style>
