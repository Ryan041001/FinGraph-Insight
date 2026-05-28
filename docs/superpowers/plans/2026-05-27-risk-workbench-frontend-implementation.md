# Risk Workbench Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Vue frontend into a productized enterprise risk due diligence workbench with no engineering-facing pages or raw API output in the user interface.

**Architecture:** Keep the existing Vue 3 + Vite app and FastAPI contracts. Add a product view-model layer that converts raw graph, QA, and analysis responses into business-facing risk summaries, evidence items, relationship paths, watchlist entries, and reports. Replace the current module navigation with three product routes: risk workbench, watchlist, and reports.

**Tech Stack:** Vue 3, Vue Router, TypeScript, ECharts, lucide-vue-next, Vitest, Vue Test Utils, jsdom.

---

## Scope And Repository Note

The current directory is not a git repository. The commit steps below are checkpoints for workers running inside a git repo; in this workspace, record the completed task in the plan and skip the git command.

This plan implements the approved spec at `docs/superpowers/specs/2026-05-27-risk-workbench-frontend-design.md`.

## Target File Structure

- Modify `frontend/package.json`: add frontend test scripts and test dependencies.
- Modify `frontend/tsconfig.json`: add Vitest global test types.
- Create `frontend/vitest.config.ts`: Vitest config for Vue component tests.
- Create `frontend/src/product/types.ts`: product-facing TypeScript interfaces.
- Create `frontend/src/product/riskAdapter.ts`: converts backend responses into workbench view models.
- Create `frontend/src/product/storage.ts`: local watchlist and report persistence.
- Create `frontend/src/router.ts`: product route definitions.
- Modify `frontend/src/main.ts`: use extracted router.
- Modify `frontend/src/App.vue`: product shell and product navigation only.
- Create `frontend/src/views/RiskWorkbench.vue`: default product workspace.
- Create `frontend/src/views/WatchlistView.vue`: saved company list.
- Create `frontend/src/views/ReportsView.vue`: report list and report detail.
- Create `frontend/src/components/CompanySearch.vue`: search input and submit.
- Create `frontend/src/components/RiskSummaryPanel.vue`: risk score, summary, and factors.
- Create `frontend/src/components/CompanyProfilePanel.vue`: company facts and tags.
- Create `frontend/src/components/RiskGraphCanvas.vue`: ECharts graph with risk highlighting.
- Create `frontend/src/components/RelationFilterBar.vue`: depth and relation type filters.
- Create `frontend/src/components/EvidenceDrawer.vue`: selected relation evidence and citations.
- Create `frontend/src/components/AskPanel.vue`: productized follow-up questions.
- Create `frontend/src/components/ReportPreview.vue`: report generation preview.
- Modify `frontend/src/styles.css`: product workbench layout and states.
- Keep legacy API files under `frontend/src/api/`; do not expose their raw responses in templates.

---

### Task 1: Add Frontend Test Harness

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/tsconfig.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Modify package scripts and dev dependencies**

Update `frontend/package.json` so the relevant sections contain these entries:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview --host 0.0.0.0",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^25.0.1",
    "typescript": "^5.7.2",
    "vite": "^6.0.5",
    "vitest": "^4.1.7",
    "vue-tsc": "^2.1.10"
  }
}
```

- [ ] **Step 2: Install dependency lockfile updates**

Run:

```powershell
npm install
```

Expected: `package-lock.json` updates with `vitest`, `@vue/test-utils`, and `jsdom`.

- [ ] **Step 3: Add Vitest global types**

Update `frontend/tsconfig.json` so `compilerOptions` contains Vitest globals:

```json
{
  "compilerOptions": {
    "types": ["vitest/globals"]
  }
}
```

- [ ] **Step 4: Create Vitest config**

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts']
  }
})
```

- [ ] **Step 5: Create test setup**

Create `frontend/src/test/setup.ts`:

```ts
import { afterEach } from 'vitest'

afterEach(() => {
  localStorage.clear()
})
```

- [ ] **Step 6: Verify the empty test suite runs**

Run:

```powershell
npm run test -- --passWithNoTests
```

Expected: Vitest starts successfully and exits with code 0 even though no test files exist yet.

- [ ] **Step 7: Verify Vite and Vitest use the same Vite major**

Run:

```powershell
npm ls vite vitest
```

Expected: `vitest` is compatible with the installed Vite major and does not install a nested Vite 5 copy.

- [ ] **Step 8: Checkpoint**

If inside a git repo:

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vitest.config.ts frontend/src/test/setup.ts
git commit -m "test: add frontend vitest harness"
```

---

### Task 2: Add Product View Models And Risk Adapter

**Files:**
- Create: `frontend/src/product/types.ts`
- Create: `frontend/src/product/riskAdapter.ts`
- Create: `frontend/src/product/riskAdapter.test.ts`

- [ ] **Step 1: Write failing adapter tests**

Create `frontend/src/product/riskAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { CompanyProfile } from '../api/types'
import { buildRiskWorkbenchModel } from './riskAdapter'

const profile: CompanyProfile = {
  company: {
    name: '示例科技',
    industry: '金融科技',
    legal_representative: '张三'
  },
  profile: {},
  graph: {
    nodes: [
      { id: 'company_demo', label: '示例科技', type: 'Company', risk_level: 'normal', properties: { industry: '金融科技' } },
      { id: 'institution_demo', label: '红杉资本', type: 'Institution', risk_level: 'normal', properties: { type: 'VC' } },
      { id: 'event_demo', label: 'B轮融资事件', type: 'Event', risk_level: 'normal', properties: { amount: '3000万元', date: '2024-03-15' } }
    ],
    edges: [
      {
        id: 'rel_invested_demo',
        source: 'institution_demo',
        target: 'event_demo',
        type: 'INVESTED_IN',
        label: '投资',
        confidence: 0.92,
        status: 'confirmed',
        properties: { role: '领投', round: 'B轮' },
        provenance: { source_text: '红杉资本领投了示例科技B轮融资。', source_doc_id: 'doc_demo' }
      }
    ]
  }
}

describe('buildRiskWorkbenchModel', () => {
  it('maps a company profile into business-facing risk content', () => {
    const model = buildRiskWorkbenchModel(profile)

    expect(model.company.name).toBe('示例科技')
    expect(model.company.industry).toBe('金融科技')
    expect(model.risk.level).toBe('low')
    expect(model.risk.summary).toContain('暂未发现高风险路径')
    expect(model.evidence).toHaveLength(1)
    expect(model.evidence[0].text).toBe('红杉资本领投了示例科技B轮融资。')
    expect(model.paths[0].label).toBe('红杉资本 -> B轮融资事件')
    expect(model.graph.nodes).toHaveLength(3)
  })

  it('raises risk level when the graph contains risk nodes or low confidence relations', () => {
    const riskyProfile: CompanyProfile = {
      ...profile,
      graph: {
        ...profile.graph,
        nodes: [
          ...profile.graph.nodes,
          { id: 'risk_event', label: '异常担保事件', type: 'Event', risk_level: 'high', properties: { date: '2024-05-01' } }
        ],
        edges: [
          ...profile.graph.edges,
          {
            id: 'rel_risk',
            source: 'company_demo',
            target: 'risk_event',
            type: 'RISK_EVENT',
            label: '涉及风险事件',
            confidence: 0.58,
            status: 'pending',
            properties: {},
            provenance: { source_text: '示例科技被报道涉及异常担保。' }
          }
        ]
      }
    }

    const model = buildRiskWorkbenchModel(riskyProfile)

    expect(model.risk.level).toBe('high')
    expect(model.risk.factors[0].title).toContain('异常担保事件')
    expect(model.evidence.some((item) => item.confidence === 0.58)).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
npm run test -- src/product/riskAdapter.test.ts
```

Expected: FAIL because `./riskAdapter` and product types do not exist.

- [ ] **Step 3: Create product types**

Create `frontend/src/product/types.ts`:

```ts
import type { GraphPayload } from '../api/types'

export type RiskLevel = 'low' | 'medium' | 'high' | 'unknown'

export interface ProductCompany {
  id: string
  name: string
  industry: string
  legalRepresentative: string
  tags: string[]
}

export interface RiskFactor {
  id: string
  level: RiskLevel
  title: string
  description: string
  relationIds: string[]
}

export interface RiskSummary {
  level: RiskLevel
  score: number
  summary: string
  factors: RiskFactor[]
}

export interface EvidenceItem {
  id: string
  relationId: string
  title: string
  text: string
  source: string
  confidence: number
  date: string
}

export interface RelationPath {
  id: string
  label: string
  relationIds: string[]
  riskLevel: RiskLevel
}

export interface RiskWorkbenchModel {
  company: ProductCompany
  risk: RiskSummary
  graph: GraphPayload
  evidence: EvidenceItem[]
  paths: RelationPath[]
}

export interface WatchlistItem {
  companyName: string
  industry: string
  riskLevel: RiskLevel
  summary: string
  updatedAt: string
}

export interface DueDiligenceReport {
  id: string
  companyName: string
  riskLevel: RiskLevel
  summary: string
  factors: RiskFactor[]
  evidence: EvidenceItem[]
  createdAt: string
}
```

- [ ] **Step 4: Create adapter implementation**

Create `frontend/src/product/riskAdapter.ts`:

```ts
import type { CompanyProfile, GraphEdge, GraphNode } from '../api/types'
import type { EvidenceItem, ProductCompany, RelationPath, RiskFactor, RiskLevel, RiskWorkbenchModel } from './types'

function stringValue(value: unknown, fallback = '-'): string {
  return typeof value === 'string' && value.trim().length > 0 ? value : fallback
}

function hasHighRiskNode(nodes: GraphNode[]): boolean {
  return nodes.some((node) => node.risk_level === 'high')
}

function hasWeakRelation(edges: GraphEdge[]): boolean {
  return edges.some((edge) => edge.confidence < 0.65 || edge.status === 'pending')
}

function resolveRiskLevel(nodes: GraphNode[], edges: GraphEdge[]): RiskLevel {
  if (hasHighRiskNode(nodes) || edges.some((edge) => edge.type.includes('RISK'))) {
    return 'high'
  }
  if (hasWeakRelation(edges)) {
    return 'medium'
  }
  return edges.length > 0 ? 'low' : 'unknown'
}

function riskScore(level: RiskLevel): number {
  const scoreMap: Record<RiskLevel, number> = {
    high: 86,
    medium: 61,
    low: 28,
    unknown: 0
  }
  return scoreMap[level]
}

function buildCompany(profile: CompanyProfile): ProductCompany {
  const companyNode = profile.graph.nodes.find((node) => node.type === 'Company')
  const company = profile.company ?? {}
  const industry = stringValue(company.industry ?? companyNode?.properties.industry)
  const legalRepresentative = stringValue(company.legal_representative ?? companyNode?.properties.legal_representative)

  return {
    id: companyNode?.id ?? stringValue(company.name, 'company_unknown'),
    name: stringValue(company.name ?? companyNode?.label, '未知企业'),
    industry,
    legalRepresentative,
    tags: [industry, legalRepresentative === '-' ? '法人信息不足' : `法人 ${legalRepresentative}`]
  }
}

function nodeLabel(nodes: GraphNode[], id: string): string {
  return nodes.find((node) => node.id === id)?.label ?? id
}

function buildRiskFactors(nodes: GraphNode[], edges: GraphEdge[], level: RiskLevel): RiskFactor[] {
  if (level === 'low') {
    return [{
      id: 'stable-relations',
      level: 'low',
      title: '暂未发现高风险路径',
      description: '当前样例图谱中主要为已确认关系，可继续查看证据链验证来源。',
      relationIds: edges.map((edge) => edge.id)
    }]
  }

  return edges
    .filter((edge) => edge.confidence < 0.65 || edge.status === 'pending' || edge.type.includes('RISK'))
    .map((edge) => ({
      id: `factor-${edge.id}`,
      level,
      title: `${nodeLabel(nodes, edge.source)} 与 ${nodeLabel(nodes, edge.target)} 存在${edge.label}`,
      description: `该关系置信度为 ${(edge.confidence * 100).toFixed(0)}%，建议结合证据来源复核。`,
      relationIds: [edge.id]
    }))
}

function buildEvidence(edges: GraphEdge[]): EvidenceItem[] {
  return edges.map((edge) => ({
    id: `evidence-${edge.id}`,
    relationId: edge.id,
    title: edge.label,
    text: stringValue(edge.provenance.source_text, '暂无可展示证据文本'),
    source: stringValue(edge.provenance.source_doc_id ?? edge.provenance.source, '图谱来源'),
    confidence: edge.confidence,
    date: stringValue(edge.properties.date ?? edge.provenance.date, '未标注日期')
  }))
}

function buildRelationPaths(nodes: GraphNode[], edges: GraphEdge[]): RelationPath[] {
  return edges.map((edge) => ({
    id: `path-${edge.id}`,
    label: `${nodeLabel(nodes, edge.source)} -> ${nodeLabel(nodes, edge.target)}`,
    relationIds: [edge.id],
    riskLevel: edge.type.includes('RISK') || edge.confidence < 0.65 ? 'high' : 'low'
  }))
}

export function buildRiskWorkbenchModel(profile: CompanyProfile): RiskWorkbenchModel {
  const company = buildCompany(profile)
  const level = resolveRiskLevel(profile.graph.nodes, profile.graph.edges)
  const factors = buildRiskFactors(profile.graph.nodes, profile.graph.edges, level)

  return {
    company,
    risk: {
      level,
      score: riskScore(level),
      summary: level === 'low'
        ? `${company.name} 当前样例数据暂未发现高风险路径，建议继续关注融资、股权和关键人员变化。`
        : `${company.name} 存在需要复核的风险关系，请优先查看高亮路径和证据链。`,
      factors
    },
    graph: profile.graph,
    evidence: buildEvidence(profile.graph.edges),
    paths: buildRelationPaths(profile.graph.nodes, profile.graph.edges)
  }
}
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```powershell
npm run test -- src/product/riskAdapter.test.ts
```

Expected: PASS.

- [ ] **Step 6: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/product/types.ts frontend/src/product/riskAdapter.ts frontend/src/product/riskAdapter.test.ts
git commit -m "feat: add product risk adapter"
```

---

### Task 3: Add Watchlist And Report Persistence

**Files:**
- Create: `frontend/src/product/storage.ts`
- Create: `frontend/src/product/storage.test.ts`

- [ ] **Step 1: Write failing storage tests**

Create `frontend/src/product/storage.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { DueDiligenceReport, WatchlistItem } from './types'
import { loadReports, loadWatchlist, removeWatchlistItem, saveReport, saveWatchlistItem } from './storage'

const watchlistItem: WatchlistItem = {
  companyName: '示例科技',
  industry: '金融科技',
  riskLevel: 'low',
  summary: '当前样例数据暂未发现高风险路径',
  updatedAt: '2026-05-27T00:00:00.000Z'
}

const report: DueDiligenceReport = {
  id: 'report-demo',
  companyName: '示例科技',
  riskLevel: 'low',
  summary: '当前样例数据暂未发现高风险路径',
  factors: [],
  evidence: [],
  createdAt: '2026-05-27T00:00:00.000Z'
}

describe('product storage', () => {
  it('saves one watchlist item per company name', () => {
    saveWatchlistItem(watchlistItem)
    saveWatchlistItem({ ...watchlistItem, industry: '软件服务' })

    expect(loadWatchlist()).toEqual([{ ...watchlistItem, industry: '软件服务' }])
  })

  it('removes a watchlist item by company name', () => {
    saveWatchlistItem(watchlistItem)
    removeWatchlistItem('示例科技')

    expect(loadWatchlist()).toEqual([])
  })

  it('stores reports newest first', () => {
    saveReport({ ...report, id: 'old', createdAt: '2026-05-26T00:00:00.000Z' })
    saveReport({ ...report, id: 'new', createdAt: '2026-05-27T00:00:00.000Z' })

    expect(loadReports().map((item) => item.id)).toEqual(['new', 'old'])
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
npm run test -- src/product/storage.test.ts
```

Expected: FAIL because `./storage` does not exist.

- [ ] **Step 3: Create storage implementation**

Create `frontend/src/product/storage.ts`:

```ts
import type { DueDiligenceReport, WatchlistItem } from './types'

const WATCHLIST_KEY = 'financial-risk-workbench-watchlist'
const REPORTS_KEY = 'financial-risk-workbench-reports'

function readJson<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key)
  if (!raw) {
    return fallback
  }

  try {
    return JSON.parse(raw) as T
  } catch {
    localStorage.removeItem(key)
    return fallback
  }
}

function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value))
}

export function loadWatchlist(): WatchlistItem[] {
  return readJson<WatchlistItem[]>(WATCHLIST_KEY, [])
}

export function saveWatchlistItem(item: WatchlistItem) {
  const items = loadWatchlist().filter((entry) => entry.companyName !== item.companyName)
  writeJson(WATCHLIST_KEY, [item, ...items])
}

export function removeWatchlistItem(companyName: string) {
  writeJson(WATCHLIST_KEY, loadWatchlist().filter((entry) => entry.companyName !== companyName))
}

export function loadReports(): DueDiligenceReport[] {
  return readJson<DueDiligenceReport[]>(REPORTS_KEY, [])
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

export function saveReport(report: DueDiligenceReport) {
  const reports = loadReports().filter((entry) => entry.id !== report.id)
  writeJson(REPORTS_KEY, [report, ...reports])
}
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
npm run test -- src/product/storage.test.ts
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/product/storage.ts frontend/src/product/storage.test.ts
git commit -m "feat: add product local persistence"
```

---

### Task 4: Replace Engineering Navigation With Product Routes

**Files:**
- Create: `frontend/src/router.ts`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/App.test.ts`
- Create: `frontend/src/views/RiskWorkbench.vue`
- Create: `frontend/src/views/WatchlistView.vue`
- Create: `frontend/src/views/ReportsView.vue`

- [ ] **Step 1: Write failing shell test**

Create `frontend/src/App.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import App from './App.vue'
import { router } from './router'

describe('App product shell', () => {
  it('shows product navigation and hides engineering navigation', async () => {
    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router]
      }
    })

    expect(wrapper.text()).toContain('风险工作台')
    expect(wrapper.text()).toContain('关注清单')
    expect(wrapper.text()).toContain('研判报告')
    expect(wrapper.text()).not.toContain('实时抽取')
    expect(wrapper.text()).not.toContain('质量监控')
    expect(wrapper.text()).not.toContain('定时更新')
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
npm run test -- src/App.test.ts
```

Expected: FAIL because `src/router.ts` does not exist and the current shell still exposes engineering navigation.

- [ ] **Step 3: Create minimal product views**

Create `frontend/src/views/RiskWorkbench.vue`:

```vue
<template>
  <section class="page workbench-page">
    <div class="page-header">
      <div>
        <h1>风险工作台</h1>
        <p>输入企业名称，查看风险摘要、关联图谱和证据链。</p>
      </div>
    </div>
  </section>
</template>
```

Create `frontend/src/views/WatchlistView.vue`:

```vue
<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>关注清单</h1>
        <p>持续跟踪重点企业的风险变化。</p>
      </div>
    </div>
  </section>
</template>
```

Create `frontend/src/views/ReportsView.vue`:

```vue
<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>研判报告</h1>
        <p>查看已生成的企业风险尽调报告。</p>
      </div>
    </div>
  </section>
</template>
```

- [ ] **Step 4: Extract router**

Create `frontend/src/router.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import ReportsView from './views/ReportsView.vue'
import RiskWorkbench from './views/RiskWorkbench.vue'
import WatchlistView from './views/WatchlistView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/workbench' },
    { path: '/workbench', component: RiskWorkbench },
    { path: '/watchlist', component: WatchlistView },
    { path: '/reports', component: ReportsView }
  ]
})
```

- [ ] **Step 5: Update app entry**

Modify `frontend/src/main.ts`:

```ts
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './styles.css'

createApp(App).use(router).mount('#app')
```

- [ ] **Step 6: Update shell navigation**

Modify `frontend/src/App.vue`:

```vue
<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">RI</div>
        <div>
          <strong>企业风险尽调</strong>
          <span>Risk Intelligence</span>
        </div>
      </div>
      <nav aria-label="产品导航">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path">
          <component :is="item.icon" :size="18" />
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="workspace">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { FileText, Radar, Star } from 'lucide-vue-next'

const navItems = [
  { path: '/workbench', label: '风险工作台', icon: Radar },
  { path: '/watchlist', label: '关注清单', icon: Star },
  { path: '/reports', label: '研判报告', icon: FileText }
]
</script>
```

- [ ] **Step 7: Run shell test**

Run:

```powershell
npm run test -- src/App.test.ts
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/router.ts frontend/src/main.ts frontend/src/App.vue frontend/src/App.test.ts frontend/src/views/RiskWorkbench.vue frontend/src/views/WatchlistView.vue frontend/src/views/ReportsView.vue
git commit -m "feat: replace frontend shell with product navigation"
```

---

### Task 5: Build Risk Workbench Data Flow And Summary Panels

**Files:**
- Create: `frontend/src/components/CompanySearch.vue`
- Create: `frontend/src/components/RiskSummaryPanel.vue`
- Create: `frontend/src/components/CompanyProfilePanel.vue`
- Modify: `frontend/src/views/RiskWorkbench.vue`
- Create: `frontend/src/views/RiskWorkbench.test.ts`

- [ ] **Step 1: Write failing workbench test**

Create `frontend/src/views/RiskWorkbench.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import RiskWorkbench from './RiskWorkbench.vue'

vi.mock('../api/graph', () => ({
  getCompanyProfile: vi.fn(async () => ({
    company: { name: '示例科技', industry: '金融科技', legal_representative: '张三' },
    profile: {},
    graph: {
      nodes: [
        { id: 'company_demo', label: '示例科技', type: 'Company', risk_level: 'normal', properties: { industry: '金融科技' } }
      ],
      edges: []
    }
  }))
}))

describe('RiskWorkbench', () => {
  it('loads productized risk content without raw output', async () => {
    const wrapper = mount(RiskWorkbench)
    await flushPromises()

    expect(wrapper.text()).toContain('示例科技')
    expect(wrapper.text()).toContain('风险等级')
    expect(wrapper.text()).toContain('暂未发现高风险路径')
    expect(wrapper.find('pre').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
npm run test -- src/views/RiskWorkbench.test.ts
```

Expected: FAIL because the workbench does not load data or render risk panels yet.

- [ ] **Step 3: Create company search component**

Create `frontend/src/components/CompanySearch.vue`:

```vue
<template>
  <form class="company-search" @submit.prevent="submit">
    <label for="company-search-input">企业名称或股票代码</label>
    <div class="search-row">
      <input id="company-search-input" v-model="localValue" type="search" />
      <button type="submit">开始尽调</button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
}>()

const localValue = ref(props.modelValue)

watch(() => props.modelValue, (value) => {
  localValue.value = value
})

function submit() {
  const value = localValue.value.trim()
  emit('update:modelValue', value)
  emit('search', value)
}
</script>
```

- [ ] **Step 4: Create summary panel**

Create `frontend/src/components/RiskSummaryPanel.vue`:

```vue
<template>
  <section class="panel risk-summary-panel" :data-risk="risk.level">
    <div class="panel-title-row">
      <span class="eyebrow">风险等级</span>
      <strong class="risk-score">{{ risk.score }}</strong>
    </div>
    <h2>{{ riskLabel }}</h2>
    <p>{{ risk.summary }}</p>
    <div class="risk-factor-list">
      <button
        v-for="factor in risk.factors"
        :key="factor.id"
        type="button"
        class="risk-factor"
        @click="$emit('select-factor', factor.relationIds)"
      >
        <strong>{{ factor.title }}</strong>
        <span>{{ factor.description }}</span>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RiskSummary } from '../product/types'

const props = defineProps<{
  risk: RiskSummary
}>()

defineEmits<{
  'select-factor': [relationIds: string[]]
}>()

const riskLabel = computed(() => {
  const labels = {
    high: '高风险',
    medium: '中风险',
    low: '低风险',
    unknown: '待补充数据'
  }
  return labels[props.risk.level]
})
</script>
```

- [ ] **Step 5: Create company profile panel**

Create `frontend/src/components/CompanyProfilePanel.vue`:

```vue
<template>
  <section class="panel company-profile-panel">
    <span class="eyebrow">尽调对象</span>
    <h2>{{ company.name }}</h2>
    <dl>
      <div>
        <dt>行业</dt>
        <dd>{{ company.industry }}</dd>
      </div>
      <div>
        <dt>法人</dt>
        <dd>{{ company.legalRepresentative }}</dd>
      </div>
    </dl>
    <div class="tag-list">
      <span v-for="tag in company.tags" :key="tag">{{ tag }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ProductCompany } from '../product/types'

defineProps<{
  company: ProductCompany
}>()
</script>
```

- [ ] **Step 6: Implement workbench data flow**

Modify `frontend/src/views/RiskWorkbench.vue`:

```vue
<template>
  <section class="page workbench-page">
    <div class="page-header">
      <div>
        <h1>风险工作台</h1>
        <p>输入企业名称，查看风险摘要、关联图谱和证据链。</p>
      </div>
      <CompanySearch v-model="keyword" @search="loadCompany" />
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
        <RiskSummaryPanel :risk="model.risk" @select-factor="highlightRelations" />
      </aside>
      <section class="panel workbench-main">
        <h2>关系图谱</h2>
        <p class="muted">图谱视图将在下一步升级为可交互风险路径。</p>
      </section>
      <aside class="panel workbench-right">
        <h2>证据链</h2>
        <div class="list">
          <article v-for="item in model.evidence" :key="item.id" class="list-item">
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
          </article>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import CompanyProfilePanel from '../components/CompanyProfilePanel.vue'
import CompanySearch from '../components/CompanySearch.vue'
import RiskSummaryPanel from '../components/RiskSummaryPanel.vue'
import { getCompanyProfile } from '../api/graph'
import { buildRiskWorkbenchModel } from '../product/riskAdapter'
import type { RiskWorkbenchModel } from '../product/types'

const keyword = ref('示例科技')
const loading = ref(false)
const error = ref('')
const model = ref<RiskWorkbenchModel | null>(null)
const highlightedRelationIds = ref<string[]>([])

async function loadCompany(value: string) {
  if (!value.trim()) {
    error.value = '请输入企业名称或股票代码。'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const profile = await getCompanyProfile(value)
    model.value = buildRiskWorkbenchModel(profile)
  } catch {
    error.value = '服务暂不可用，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function highlightRelations(relationIds: string[]) {
  highlightedRelationIds.value = relationIds
}

onMounted(() => {
  void loadCompany(keyword.value)
})
</script>
```

- [ ] **Step 7: Run workbench test**

Run:

```powershell
npm run test -- src/views/RiskWorkbench.test.ts
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/components/CompanySearch.vue frontend/src/components/RiskSummaryPanel.vue frontend/src/components/CompanyProfilePanel.vue frontend/src/views/RiskWorkbench.vue frontend/src/views/RiskWorkbench.test.ts
git commit -m "feat: add risk workbench summary flow"
```

---

### Task 6: Upgrade Graph And Evidence Interaction

**Files:**
- Create: `frontend/src/components/RelationFilterBar.vue`
- Create: `frontend/src/components/RiskGraphCanvas.vue`
- Create: `frontend/src/components/EvidenceDrawer.vue`
- Modify: `frontend/src/views/RiskWorkbench.vue`

- [ ] **Step 1: Create relation filter bar**

Create `frontend/src/components/RelationFilterBar.vue`:

```vue
<template>
  <div class="relation-filter-bar">
    <label>
      关系深度
      <select :value="depth" @change="$emit('update:depth', Number(($event.target as HTMLSelectElement).value))">
        <option :value="1">1 跳</option>
        <option :value="2">2 跳</option>
        <option :value="3">3 跳</option>
      </select>
    </label>
    <div class="segmented">
      <button
        v-for="type in relationTypes"
        :key="type"
        type="button"
        :class="{ active: selectedTypes.includes(type) }"
        @click="$emit('toggle-type', type)"
      >
        {{ type }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  depth: number
  relationTypes: string[]
  selectedTypes: string[]
}>()

defineEmits<{
  'update:depth': [depth: number]
  'toggle-type': [type: string]
}>()
</script>
```

- [ ] **Step 2: Create graph canvas**

Create `frontend/src/components/RiskGraphCanvas.vue`:

```vue
<template>
  <div ref="chartEl" class="risk-graph-canvas" role="img" aria-label="企业关系图谱"></div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { GraphEdge, GraphNode } from '../api/types'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightedRelationIds: string[]
}>()

const emit = defineEmits<{
  'select-edge': [edge: GraphEdge]
}>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const categories = computed(() => {
  return Array.from(new Set(props.nodes.map((node) => node.type))).map((name) => ({ name }))
})

function nodeColor(node: GraphNode): string {
  if (node.risk_level === 'high') return '#b91c1c'
  if (node.type === 'Company') return '#0f766e'
  if (node.type === 'Institution') return '#b45309'
  if (node.type === 'Event') return '#2563eb'
  return '#64748b'
}

function renderChart() {
  if (!chartEl.value) return
  chart ??= echarts.init(chartEl.value)

  chart.setOption({
    tooltip: {},
    legend: [{ data: categories.value.map((item) => item.name), bottom: 0 }],
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      categories: categories.value,
      force: { repulsion: 240, edgeLength: 120 },
      label: { show: true, formatter: '{b}' },
      data: props.nodes.map((node) => ({
        id: node.id,
        name: node.label,
        category: categories.value.findIndex((item) => item.name === node.type),
        itemStyle: { color: nodeColor(node) },
        symbolSize: node.type === 'Company' ? 58 : 44
      })),
      links: props.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        name: edge.label,
        lineStyle: {
          width: props.highlightedRelationIds.includes(edge.id) ? 4 : 1.5,
          color: props.highlightedRelationIds.includes(edge.id) ? '#b91c1c' : '#94a3b8',
          curveness: 0.15
        },
        label: { show: true, formatter: edge.label }
      }))
    }]
  })

  chart.off('click')
  chart.on('click', (params) => {
    if (params.dataType !== 'edge') return
    const edge = props.edges.find((item) => item.id === (params.data as { id?: string }).id)
    if (edge) emit('select-edge', edge)
  })
}

onMounted(renderChart)
watch(() => [props.nodes, props.edges, props.highlightedRelationIds], renderChart, { deep: true })

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})
</script>
```

- [ ] **Step 3: Create evidence drawer**

Create `frontend/src/components/EvidenceDrawer.vue`:

```vue
<template>
  <section class="panel evidence-drawer">
    <div class="panel-title-row">
      <div>
        <span class="eyebrow">证据链</span>
        <h2>{{ selectedTitle }}</h2>
      </div>
    </div>
    <div v-if="items.length === 0" class="empty-state">当前关系暂无可展示证据。</div>
    <div v-else class="list">
      <article v-for="item in items" :key="item.id" class="list-item">
        <div class="evidence-meta">
          <strong>{{ item.title }}</strong>
          <span>{{ Math.round(item.confidence * 100) }}%</span>
        </div>
        <p>{{ item.text }}</p>
        <small>{{ item.source }} · {{ item.date }}</small>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EvidenceItem } from '../product/types'

const props = defineProps<{
  evidence: EvidenceItem[]
  selectedRelationId: string
}>()

const items = computed(() => props.selectedRelationId
  ? props.evidence.filter((item) => item.relationId === props.selectedRelationId)
  : props.evidence)

const selectedTitle = computed(() => props.selectedRelationId ? '选中关系证据' : '全部证据')
</script>
```

- [ ] **Step 4: Wire graph and evidence into workbench**

Modify the central and right panels in `frontend/src/views/RiskWorkbench.vue` so the loaded state contains:

```vue
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
    :nodes="model.graph.nodes"
    :edges="filteredEdges"
    :highlighted-relation-ids="highlightedRelationIds"
    @select-edge="selectEdge"
  />
</section>
<EvidenceDrawer :evidence="model.evidence" :selected-relation-id="selectedRelationId" />
```

Add these imports and state to the script:

```ts
import { computed } from 'vue'
import type { GraphEdge } from '../api/types'
import EvidenceDrawer from '../components/EvidenceDrawer.vue'
import RelationFilterBar from '../components/RelationFilterBar.vue'
import RiskGraphCanvas from '../components/RiskGraphCanvas.vue'
```

```ts
const depth = ref(2)
const selectedRelationId = ref('')
const selectedRelationTypes = ref<string[]>([])

const relationTypes = computed(() => {
  return Array.from(new Set(model.value?.graph.edges.map((edge) => edge.label) ?? []))
})

const filteredEdges = computed(() => {
  const edges = model.value?.graph.edges ?? []
  if (selectedRelationTypes.value.length === 0) {
    return edges
  }
  return edges.filter((edge) => selectedRelationTypes.value.includes(edge.label))
})

function toggleRelationType(type: string) {
  selectedRelationTypes.value = selectedRelationTypes.value.includes(type)
    ? selectedRelationTypes.value.filter((item) => item !== type)
    : [...selectedRelationTypes.value, type]
}

function selectEdge(edge: GraphEdge) {
  selectedRelationId.value = edge.id
  highlightedRelationIds.value = [edge.id]
}
```

- [ ] **Step 5: Run focused build check**

Run:

```powershell
npm run build
```

Expected: PASS with TypeScript and Vite build success.

- [ ] **Step 6: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/components/RelationFilterBar.vue frontend/src/components/RiskGraphCanvas.vue frontend/src/components/EvidenceDrawer.vue frontend/src/views/RiskWorkbench.vue
git commit -m "feat: add interactive risk graph and evidence panel"
```

---

### Task 7: Add Productized Ask And Report Generation

**Files:**
- Create: `frontend/src/components/AskPanel.vue`
- Create: `frontend/src/components/ReportPreview.vue`
- Modify: `frontend/src/views/RiskWorkbench.vue`

- [ ] **Step 1: Create ask panel**

Create `frontend/src/components/AskPanel.vue`:

```vue
<template>
  <section class="panel ask-panel">
    <span class="eyebrow">追问</span>
    <h2>继续询问关联关系</h2>
    <form @submit.prevent="submit">
      <textarea v-model="question" rows="3" />
      <button type="submit" :disabled="loading">{{ loading ? '分析中' : '提交追问' }}</button>
    </form>
    <article v-if="answer" class="answer-card">
      <strong>回答</strong>
      <p>{{ answer }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { askGraphRag } from '../api/qa'

const props = defineProps<{
  companyName: string
}>()

const question = ref('这家公司有哪些需要关注的关联关系？')
const answer = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  answer.value = ''
  try {
    const result = await askGraphRag(`${props.companyName}：${question.value}`)
    answer.value = typeof result.answer === 'string' ? result.answer : '已生成回答，请结合证据链复核。'
  } catch {
    answer.value = '未能完成本次追问，请稍后重试。'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 2: Create report preview**

Create `frontend/src/components/ReportPreview.vue`:

```vue
<template>
  <section class="panel report-preview">
    <span class="eyebrow">研判报告</span>
    <h2>{{ model.company.name }} 风险尽调摘要</h2>
    <p>{{ model.risk.summary }}</p>
    <div class="list">
      <article v-for="factor in model.risk.factors" :key="factor.id" class="list-item">
        <strong>{{ factor.title }}</strong>
        <p>{{ factor.description }}</p>
      </article>
    </div>
    <button type="button" @click="$emit('save-report')">保存研判报告</button>
  </section>
</template>

<script setup lang="ts">
import type { RiskWorkbenchModel } from '../product/types'

defineProps<{
  model: RiskWorkbenchModel
}>()

defineEmits<{
  'save-report': []
}>()
</script>
```

- [ ] **Step 3: Wire ask and report actions into workbench**

Add imports in `frontend/src/views/RiskWorkbench.vue`:

```ts
import AskPanel from '../components/AskPanel.vue'
import ReportPreview from '../components/ReportPreview.vue'
import { saveReport, saveWatchlistItem } from '../product/storage'
```

Add action functions:

```ts
function addToWatchlist() {
  if (!model.value) return
  saveWatchlistItem({
    companyName: model.value.company.name,
    industry: model.value.company.industry,
    riskLevel: model.value.risk.level,
    summary: model.value.risk.summary,
    updatedAt: new Date().toISOString()
  })
}

function saveCurrentReport() {
  if (!model.value) return
  saveReport({
    id: `${model.value.company.id}-${Date.now()}`,
    companyName: model.value.company.name,
    riskLevel: model.value.risk.level,
    summary: model.value.risk.summary,
    factors: model.value.risk.factors,
    evidence: model.value.evidence,
    createdAt: new Date().toISOString()
  })
}
```

Add buttons and right-side modules in the loaded-state template:

```vue
<button type="button" class="secondary" @click="addToWatchlist">加入关注</button>
<AskPanel :company-name="model.company.name" />
<ReportPreview :model="model" @save-report="saveCurrentReport" />
```

- [ ] **Step 4: Run build check**

Run:

```powershell
npm run build
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/components/AskPanel.vue frontend/src/components/ReportPreview.vue frontend/src/views/RiskWorkbench.vue
git commit -m "feat: add product ask and report actions"
```

---

### Task 8: Implement Watchlist And Reports Views

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/ReportsView.vue`

- [ ] **Step 1: Implement watchlist view**

Modify `frontend/src/views/WatchlistView.vue`:

```vue
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
```

- [ ] **Step 2: Implement reports view**

Modify `frontend/src/views/ReportsView.vue`:

```vue
<template>
  <section class="page reports-page">
    <div class="page-header">
      <div>
        <h1>研判报告</h1>
        <p>查看已生成的企业风险尽调报告。</p>
      </div>
    </div>

    <div v-if="reports.length === 0" class="panel empty-state">
      暂无研判报告。请先在风险工作台中保存报告。
    </div>

    <div v-else class="reports-layout">
      <aside class="panel list">
        <button
          v-for="report in reports"
          :key="report.id"
          type="button"
          class="report-list-item"
          :class="{ active: selected?.id === report.id }"
          @click="selected = report"
        >
          <strong>{{ report.companyName }}</strong>
          <span>{{ formatTime(report.createdAt) }}</span>
        </button>
      </aside>
      <article v-if="selected" class="panel report-detail">
        <span class="eyebrow">企业风险尽调报告</span>
        <h2>{{ selected.companyName }}</h2>
        <p>{{ selected.summary }}</p>
        <h3>关键风险因素</h3>
        <div class="list">
          <section v-for="factor in selected.factors" :key="factor.id" class="list-item">
            <strong>{{ factor.title }}</strong>
            <p>{{ factor.description }}</p>
          </section>
        </div>
        <h3>证据链</h3>
        <div class="list">
          <section v-for="item in selected.evidence" :key="item.id" class="list-item">
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
          </section>
        </div>
        <p class="muted">本结果仅用于课程项目演示和研究辅助，不构成投资建议。</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { loadReports } from '../product/storage'
import type { DueDiligenceReport } from '../product/types'

const reports = ref<DueDiligenceReport[]>(loadReports())
const selected = ref<DueDiligenceReport | null>(reports.value[0] ?? null)

function formatTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
</script>
```

- [ ] **Step 3: Run build check**

Run:

```powershell
npm run build
```

Expected: PASS.

- [ ] **Step 4: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/views/WatchlistView.vue frontend/src/views/ReportsView.vue
git commit -m "feat: add product watchlist and reports"
```

---

### Task 9: Product Styling And Engineering Surface Cleanup

**Files:**
- Modify: `frontend/src/styles.css`
- Review: `frontend/src/views/*.vue`

- [ ] **Step 1: Add product layout styles**

Append these styles to `frontend/src/styles.css`:

```css
.workbench-grid {
  display: grid;
  grid-template-columns: 280px minmax(480px, 1fr) 340px;
  gap: 18px;
  align-items: start;
}

.workbench-left,
.workbench-right {
  display: grid;
  gap: 14px;
}

.workbench-main {
  min-height: 620px;
}

.company-search {
  min-width: 380px;
}

.company-search label,
.relation-filter-bar label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 13px;
}

.search-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

.eyebrow {
  color: var(--muted);
  display: block;
  font-size: 12px;
  letter-spacing: 0;
  margin-bottom: 8px;
}

.panel-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-score {
  align-items: center;
  border-radius: 999px;
  display: inline-flex;
  font-size: 24px;
  height: 54px;
  justify-content: center;
  width: 54px;
}

.risk-summary-panel[data-risk='high'] .risk-score {
  background: #fee2e2;
  color: #991b1b;
}

.risk-summary-panel[data-risk='medium'] .risk-score {
  background: #ffedd5;
  color: #9a3412;
}

.risk-summary-panel[data-risk='low'] .risk-score {
  background: #dcfce7;
  color: #166534;
}

.risk-factor-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.risk-factor {
  background: #ffffff;
  border: 1px solid var(--line);
  color: var(--ink);
  display: grid;
  gap: 4px;
  padding: 12px;
  text-align: left;
}

.risk-factor span {
  color: var(--muted);
  font-size: 13px;
}

.company-profile-panel dl {
  display: grid;
  gap: 8px;
  margin: 14px 0;
}

.company-profile-panel dl div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.company-profile-panel dt {
  color: var(--muted);
}

.company-profile-panel dd {
  margin: 0;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-list span {
  background: #e6ebe8;
  border-radius: 999px;
  color: var(--ink);
  font-size: 12px;
  padding: 5px 8px;
}

.relation-filter-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.segmented {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.segmented button,
.report-list-item {
  background: #ffffff;
  border: 1px solid var(--line);
  color: var(--ink);
}

.segmented button.active,
.report-list-item.active {
  border-color: var(--accent);
  color: var(--accent);
}

.risk-graph-canvas {
  height: 520px;
  width: 100%;
}

.evidence-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.ask-panel form {
  display: grid;
  gap: 10px;
}

.answer-card {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-top: 12px;
  padding: 12px;
}

.empty-state,
.state-panel {
  color: var(--muted);
}

.text-link {
  color: var(--accent);
  text-decoration: none;
}

.watchlist-row {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.reports-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 18px;
}

.report-list-item {
  display: grid;
  gap: 4px;
  padding: 12px;
  text-align: left;
}

.report-detail h3 {
  margin-top: 20px;
}

@media (max-width: 1180px) {
  .workbench-grid,
  .reports-layout {
    grid-template-columns: 1fr;
  }

  .company-search {
    min-width: 0;
    width: 100%;
  }
}
```

- [ ] **Step 2: Scan for raw-output and engineering labels**

Run:

```powershell
rg -n "<pre>|实时抽取|定时更新|质量监控|Text2Cypher|Cypher|JSON|接口状态|等待 Neo4j|等待真实数据|等待生成|暂无任务" frontend/src
```

Expected: no matches in user-facing Vue templates. Matches in legacy API files are acceptable only when they are not rendered.

- [ ] **Step 3: Remove user-facing legacy route files from navigation**

Do not delete legacy files in this task. Confirm only `frontend/src/router.ts` imports the three product views:

```powershell
rg -n "ExtractionDemo|GraphView|QAView|RiskAnalysis|StockAnalysis|UpdateStatus|Dashboard" frontend/src/router.ts frontend/src/App.vue frontend/src/main.ts
```

Expected: no matches.

- [ ] **Step 4: Run build check**

Run:

```powershell
npm run build
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If inside a git repo:

```bash
git add frontend/src/styles.css
git commit -m "style: productize risk workbench interface"
```

---

### Task 10: Final Verification

**Files:**
- Review all frontend changes.

- [ ] **Step 1: Run unit tests**

Run:

```powershell
npm run test
```

Expected: PASS for all frontend tests.

- [ ] **Step 2: Run production build**

Run:

```powershell
npm run build
```

Expected: PASS with `vue-tsc --noEmit` and Vite build success.

- [ ] **Step 3: Start the app locally**

Run:

```powershell
npm run dev
```

Expected: Vite serves the app. Open the shown local URL.

- [ ] **Step 4: Manual product acceptance**

Verify these items in the browser:

- Default route redirects to `/workbench`.
- Sidebar shows only `风险工作台`、`关注清单`、`研判报告`.
- Searching `示例科技` renders company facts, risk summary, graph area, evidence, ask panel, and report preview.
- The page contains no visible raw JSON, Cypher, interface status, extraction page, update page, or metrics page.
- `加入关注` adds the company to `关注清单`.
- `保存研判报告` adds a report to `研判报告`.
- If the API is unavailable, the workbench shows a business-friendly retry state.

- [ ] **Step 5: Final checkpoint**

If inside a git repo:

```bash
git status --short
git add frontend docs/superpowers
git commit -m "feat: rebuild frontend as risk workbench product"
```
