<template>
  <div ref="chartEl" class="risk-graph-canvas" role="img" aria-label="企业关系图谱"></div>
</template>

<script setup lang="ts">
import { GraphChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { GraphEdge, GraphNode } from '../api/types'

use([GraphChart, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightedRelationIds: string[]
}>()

const emit = defineEmits<{
  'select-edge': [edge: GraphEdge]
}>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null

const highlightedRelationIdSet = computed(() => new Set(props.highlightedRelationIds))
const categories = computed(() => Array.from(new Set(props.nodes.map((node) => nodeTypeLabel(node)))).map((name) => ({ name })))

function nodeTypeLabel(node: GraphNode): string {
  const typeLabels: Record<string, string> = {
    company: '企业',
    institution: '机构',
    event: '事件',
    person: '人员'
  }
  const normalizedType = node.type.trim().toLowerCase()

  return typeLabels[normalizedType] ?? (/[A-Za-z_]/.test(node.type) ? '其他对象' : node.type)
}

function nodeColor(node: GraphNode): string {
  if (node.risk_level === 'high') return '#b91c1c'
  if (node.type === 'Company') return '#2563eb'
  if (node.type === 'Institution') return '#8b5cf6'
  if (node.type === 'Event') return '#f59e0b'
  return '#64748b'
}

function renderChart() {
  if (!chartEl.value) {
    return
  }

  chart ??= init(chartEl.value)
  chart.setOption({
    tooltip: {
      trigger: 'item'
    },
    legend: [{
      data: categories.value.map((item) => item.name),
      bottom: 0,
      icon: 'circle'
    }],
    series: [{
      type: 'graph',
      layout: 'force',
      roam: 'scale',
      categories: categories.value,
      force: { repulsion: 260, edgeLength: 118 },
      label: {
        show: true,
        formatter: '{b}'
      },
      edgeLabel: {
        show: true,
        color: '#63706b',
        fontSize: 11,
        formatter: '{c}'
      },
      data: props.nodes.map((node) => ({
        id: node.id,
        name: node.label,
        category: categories.value.findIndex((item) => item.name === nodeTypeLabel(node)),
        draggable: true,
        itemStyle: { color: nodeColor(node) },
        symbolSize: node.type === 'Company' ? 62 : 46
      })),
      links: props.edges.map((edge) => {
        const highlighted = highlightedRelationIdSet.value.has(edge.id)

        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          value: edge.label,
          name: edge.label,
          lineStyle: {
            width: highlighted ? 4 : 1.6,
            color: highlighted ? '#b91c1c' : '#94a3b8',
            curveness: 0.14
          },
          label: {
            show: true,
            formatter: edge.label
          }
        }
      })
    }]
  })

  chart.off('click')
  chart.on('click', (params: unknown) => {
    if (!isEdgeClickEvent(params)) {
      return
    }

    const edge = props.edges.find((item) => item.id === params.data?.id)
    if (edge) {
      emit('select-edge', edge)
    }
  })
}

function isEdgeClickEvent(value: unknown): value is { dataType: 'edge'; data?: { id?: string } } {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const event = value as { dataType?: unknown; data?: unknown }
  const data = event.data

  return event.dataType === 'edge'
    && typeof data === 'object'
    && data !== null
    && (typeof (data as { id?: unknown }).id === 'string' || (data as { id?: unknown }).id === undefined)
}

onMounted(renderChart)
watch(() => [props.nodes, props.edges, props.highlightedRelationIds], renderChart, { deep: true })

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.risk-graph-canvas {
  min-height: 520px;
  width: 100%;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, #f8fbff, #f0f9ff 50%, #fefce8 100%);
  box-shadow: var(--shadow);
  transition: all var(--transition-base) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.risk-graph-canvas::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #0ea5e9, #6366f1, #8b5cf6);
  opacity: 0.5;
}

.risk-graph-canvas:hover {
  box-shadow: var(--shadow-lg);
  border-color: var(--line-strong);
}
</style>
