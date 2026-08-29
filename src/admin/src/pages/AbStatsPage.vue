<script setup lang="ts">
import { computed, h, onMounted, ref, watch, type VNodeChild } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsCoreOption } from 'echarts/core'
import {
  NButton,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NGrid,
  NGridItem,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NText,
  type DataTableColumns,
  type SelectOption,
} from 'naive-ui'
import { API_BASE, api } from '../api'
import { toastSuccess } from '../feedback'
import type { AbFeedback, AbStats, AbStatsArm } from '../types'
import { formatDateTime, normalizeStringArray, percent, signedNumber, toNumber } from '../utils'

type DailyPoint = {
  date: string
  arm_id: number
  routed: number
  better: number
  worse: number
  same: number
}

type Metric = 'routed' | 'better' | 'worse'

use([CanvasRenderer, BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent])

const route = useRoute()
const router = useRouter()

const experimentId = computed(() => String(route.params.id ?? ''))
const loading = ref(true)
const stats = ref<AbStats | null>(null)
const feedback = ref<AbFeedback[]>([])
const days = ref(30)
const metric = ref<Metric>('routed')

const dayOptions: SelectOption[] = [
  { label: '最近 7 天', value: 7 },
  { label: '最近 30 天', value: 30 },
  { label: '最近 90 天', value: 90 },
]

const experiment = computed(() => stats.value?.experiment ?? null)

const arms = computed<AbStatsArm[]>(() =>
  (stats.value?.arms ?? []).map((arm) => ({
    arm_id: toNumber(arm.arm_id),
    label: arm.label ?? `#${toNumber(arm.arm_id)}`,
    model_full_id: arm.model_full_id ?? '',
    traffic_percent: toNumber(arm.traffic_percent),
    routed_count: toNumber(arm.routed_count),
    votes: {
      better: toNumber(arm.votes?.better),
      worse: toNumber(arm.votes?.worse),
      same: toNumber(arm.votes?.same),
      total: toNumber(arm.votes?.total),
    },
    better_rate: toNumber(arm.better_rate),
    worse_rate: toNumber(arm.worse_rate),
    net_score: toNumber(arm.net_score),
  })),
)

const daily = computed<DailyPoint[]>(() =>
  (stats.value?.daily ?? []).map((point) => ({
    date: String(point.date ?? ''),
    arm_id: toNumber(point.arm_id),
    routed: toNumber(point.routed),
    better: toNumber(point.better),
    worse: toNumber(point.worse),
    same: toNumber(point.same),
  })),
)

const reasons = computed(() =>
  [...(stats.value?.reasons ?? [])]
    .map((item) => ({ reason: String(item?.reason ?? ''), count: toNumber(item?.count) }))
    .sort((a, b) => b.count - a.count),
)

const totals = computed(() => {
  const rows: Array<{ key: string; value: string }> = []
  const source = stats.value?.totals
  if (source != null && typeof source === 'object') {
    for (const [key, value] of Object.entries(source)) {
      rows.push({ key, value: value == null ? '—' : String(value) })
    }
  }
  return rows
})

const totalRouted = computed(() => arms.value.reduce((sum, arm) => sum + arm.routed_count, 0))
const totalVotes = computed(() => arms.value.reduce((sum, arm) => sum + arm.votes.total, 0))

const votesChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: {},
  grid: { left: 48, right: 16, top: 40, bottom: 32 },
  xAxis: { type: 'category', data: arms.value.map((arm) => arm.label) },
  yAxis: { type: 'value', minInterval: 1 },
  series: [
    { name: '更好', type: 'bar', data: arms.value.map((arm) => arm.votes.better), itemStyle: { color: '#63e2b7' } },
    { name: '更差', type: 'bar', data: arms.value.map((arm) => arm.votes.worse), itemStyle: { color: '#e88080' } },
    { name: '差不多', type: 'bar', data: arms.value.map((arm) => arm.votes.same), itemStyle: { color: '#8fbcbb' } },
  ],
}))

const dates = computed(() => Array.from(new Set(daily.value.map((point) => point.date))).sort())

const dailyChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: {},
  grid: { left: 48, right: 16, top: 40, bottom: 32 },
  xAxis: { type: 'category', data: dates.value },
  yAxis: { type: 'value', minInterval: 1 },
  series: arms.value.map((arm) => ({
    name: arm.label,
    type: 'line',
    data: dates.value.map((date) => {
      const point = daily.value.find((item) => item.date === date && item.arm_id === arm.arm_id)
      return point ? point[metric.value] : 0
    }),
  })),
}))

const reasonsChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: {},
  grid: { left: 150, right: 24, top: 16, bottom: 32 },
  xAxis: { type: 'value', minInterval: 1 },
  yAxis: {
    type: 'category',
    data: reasons.value.map((item) => item.reason).reverse(),
    axisLabel: { width: 140, overflow: 'truncate' },
  },
  series: [{ type: 'bar', data: reasons.value.map((item) => item.count).reverse(), itemStyle: { color: '#70c0e8' } }],
}))

function netScoreClass(value: number): string {
  if (value > 0) return 'net-pos'
  if (value < 0) return 'net-neg'
  return 'net-zero'
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const results = await Promise.all([
      api.get<AbStats | null>(`ab/experiments/${experimentId.value}/stats?days=${days.value}`),
      api.get<AbFeedback[] | null>(`ab/experiments/${experimentId.value}/feedback?limit=200`),
    ])
    stats.value = results[0]
    feedback.value = Array.isArray(results[1]) ? results[1] : []
  } catch {} finally {
    loading.value = false
  }
}

async function toggleEnabled(value: boolean): Promise<void> {
  if (experiment.value == null) return
  try {
    await api.put(`ab/experiments/${experiment.value.id}/enabled`, { enabled: value })
    toastSuccess(value ? '已启用' : '已停用')
    await load()
  } catch {}
}

function exportCsv(): void {
  window.open(`${API_BASE}/ab/experiments/${experimentId.value}/export.csv?days=${days.value}`, '_blank')
}

function renderReasonTags(value: unknown): VNodeChild {
  const list = normalizeStringArray(value)
  if (list.length === 0) return '—'
  return h(
    NSpace,
    { size: 4, wrap: true },
    { default: () => list.map((reason) => h(NTag, { size: 'small', bordered: false }, { default: () => reason })) },
  )
}

const feedbackColumns: DataTableColumns<AbFeedback> = [
  {
    title: '时间',
    key: 'created_at',
    width: 165,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '模型',
    key: 'arm_id',
    width: 150,
    render: (row) =>
      h(NTag, { size: 'small', bordered: false, type: 'info' }, { default: () => armLabelOf(row) }),
  },
  {
    title: '用户',
    key: 'user_id',
    width: 110,
    render: (row) => String(row.user_id ?? '—'),
  },
  {
    title: '原因',
    key: 'reasons',
    width: 240,
    render: (row) => renderReasonTags(row.reasons),
  },
  {
    title: '补充说明',
    key: 'free_text',
    ellipsis: { tooltip: true },
    render: (row) => row.free_text || '—',
  },
  {
    type: 'expand',
    renderExpand: (row) =>
      h('div', { class: 'feedback-expand' }, [
        h('div', null, [
          h('div', { class: 'feedback-expand-label' }, '提问内容'),
          h('pre', null, row.question_text || '（未记录）'),
        ]),
        h('div', null, [
          h('div', { class: 'feedback-expand-label' }, '回复内容'),
          h('pre', null, row.reply_text || '（未记录）'),
        ]),
      ]),
  },
]

const feedbackArmFilter = ref<number | 'all'>('all')

const filteredFeedback = computed(() => {
  if (feedbackArmFilter.value === 'all') return feedback.value
  return feedback.value.filter((row) => toNumber(row.arm_id) === feedbackArmFilter.value)
})

const feedbackReasonSummary = computed(() => {
  const counter = new Map<string, number>()
  for (const row of filteredFeedback.value) {
    for (const reason of normalizeStringArray(row.reasons)) {
      counter.set(reason, (counter.get(reason) ?? 0) + 1)
    }
  }
  return Array.from(counter.entries())
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count)
})

function armLabelOf(row: AbFeedback): string {
  const arm = arms.value.find((item) => item.arm_id === toNumber(row.arm_id))
  return arm ? arm.label : String(row.model_full_id ?? '—')
}

watch(days, () => void load())

onMounted(() => void load())
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-card size="small" class="page-card">
        <n-space vertical :size="10" v-if="experiment">
          <n-space align="center" :size="10" wrap>
            <n-button size="small" quaternary @click="router.push({ name: 'ab' })">返回列表</n-button>
            <span class="experiment-name">{{ experiment.name }}</span>
            <n-switch :value="experiment.enabled" size="small" @update:value="(value: boolean) => toggleEnabled(value)" />
            <n-text depth="3" size="small">创建于 {{ formatDateTime(experiment.created_at) }}</n-text>
            <n-button size="small" type="primary" @click="exportCsv">导出 CSV</n-button>
          </n-space>
          <n-text v-if="experiment.note" depth="2" size="small">{{ experiment.note }}</n-text>
          <n-space :size="6" wrap>
            <n-tag v-for="arm in experiment.arms" :key="arm.id" size="small" :type="arm.enabled ? 'info' : 'default'" :bordered="false">
              {{ arm.label }} · {{ arm.model_full_id }}（{{ arm.traffic_percent }}%）
            </n-tag>
          </n-space>
          <n-space :size="16" align="center">
            <n-select v-model:value="days" :options="dayOptions" size="small" style="width: 140px" />
            <n-text size="small">总中签 {{ totalRouted }} · 总投票 {{ totalVotes }}</n-text>
          </n-space>
        </n-space>
        <n-text v-else depth="3">无法加载实验信息</n-text>
      </n-card>

      <n-grid :x-gap="16" :y-gap="16" :cols="1" s="2" m="3" responsive="screen">
        <n-grid-item v-for="arm in arms" :key="arm.arm_id">
          <n-card size="small">
            <template #header>
              <n-space align="center" :size="8" wrap>
                <span>{{ arm.label }}</span>
                <n-tag size="tiny" :bordered="false">{{ arm.traffic_percent }}%</n-tag>
              </n-space>
            </template>
            <n-space vertical :size="6">
              <n-text depth="3" size="small" style="word-break: break-all">{{ arm.model_full_id || '—' }}</n-text>
              <n-descriptions :column="1" size="small" bordered>
                <n-descriptions-item label="中签数">{{ arm.routed_count }}</n-descriptions-item>
                <n-descriptions-item label="更好">{{ arm.votes.better }}（{{ percent(arm.votes.better, arm.votes.total) }}）</n-descriptions-item>
                <n-descriptions-item label="更差">{{ arm.votes.worse }}（{{ percent(arm.votes.worse, arm.votes.total) }}）</n-descriptions-item>
                <n-descriptions-item label="差不多">{{ arm.votes.same }}（{{ percent(arm.votes.same, arm.votes.total) }}）</n-descriptions-item>
                <n-descriptions-item label="净得分">
                  <span :class="netScoreClass(arm.net_score)">{{ signedNumber(arm.net_score) }}</span>
                </n-descriptions-item>
              </n-descriptions>
            </n-space>
          </n-card>
        </n-grid-item>
      </n-grid>

      <n-card title="投票分布" size="small" class="page-card">
        <v-chart :option="votesChartOption" autoresize style="height: 300px" />
      </n-card>

      <n-card size="small" class="page-card">
        <template #header>
          <n-space align="center" :size="12">
            <span>每日趋势</span>
            <n-radio-group v-model:value="metric" size="small">
              <n-radio-button value="routed">中签数</n-radio-button>
              <n-radio-button value="better">更好</n-radio-button>
              <n-radio-button value="worse">更差</n-radio-button>
            </n-radio-group>
          </n-space>
        </template>
        <v-chart :option="dailyChartOption" autoresize style="height: 340px" />
      </n-card>

      <n-card title="投票原因排名" size="small" class="page-card">
        <v-chart v-if="reasons.length > 0" :option="reasonsChartOption" autoresize style="height: 320px" />
        <n-text v-else depth="3">暂无投票原因数据</n-text>
      </n-card>

      <n-card v-if="totals.length > 0" title="汇总" size="small" class="page-card">
        <n-descriptions :column="2" size="small" bordered>
          <n-descriptions-item v-for="row in totals" :key="row.key" :label="row.key">{{ row.value }}</n-descriptions-item>
        </n-descriptions>
      </n-card>

      <n-card size="small" class="page-card">
        <template #header>
          <n-space align="center" :size="12" wrap>
            <span>用户反馈</span>
            <n-radio-group v-model:value="feedbackArmFilter" size="small">
              <n-radio-button value="all">全部</n-radio-button>
              <n-radio-button v-for="arm in arms" :key="arm.arm_id" :value="arm.arm_id">
                {{ arm.label }}
              </n-radio-button>
            </n-radio-group>
            <n-text depth="3" size="small">共 {{ filteredFeedback.length }} 条</n-text>
          </n-space>
        </template>
        <n-space v-if="feedbackReasonSummary.length > 0" :size="6" wrap style="margin-bottom: 12px">
          <n-tag v-for="item in feedbackReasonSummary" :key="item.reason" size="small" :bordered="false">
            {{ item.reason }} × {{ item.count }}
          </n-tag>
        </n-space>
        <n-data-table
          :columns="feedbackColumns"
          :data="filteredFeedback"
          :row-key="(row: AbFeedback) => row.id"
          :max-height="520"
          size="small"
        />
      </n-card>
    </n-space>
  </n-spin>
</template>

<style scoped>
.experiment-name {
  font-size: 16px;
  font-weight: 500;
}
.net-pos {
  color: #63e2b7;
}
.net-neg {
  color: #e88080;
}
.net-zero {
  opacity: 0.7;
}
</style>
