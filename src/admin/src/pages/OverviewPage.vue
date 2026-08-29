<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NGrid,
  NGridItem,
  NSpace,
  NSpin,
  NTag,
  NText,
} from 'naive-ui'
import { api } from '../api'
import type { AbExperiment, AbStats, AuditEntry, AuditListResult, GlobalSettings } from '../types'
import { auditActionTagType, formatDateTime, toNumber } from '../utils'

const router = useRouter()
const loading = ref(true)

const globalSettings = ref<GlobalSettings | null>(null)
const usageRows = ref<Array<{ key: string; value: string }>>([])
const experiments = ref<AbExperiment[]>([])
const abTotals = ref<Record<number, { routed: number; votes: number }>>({})
const statsOverview = ref<Record<string, unknown> | null>(null)
const recentAudit = ref<AuditEntry[]>([])

function pickStat(...keys: string[]): string | null {
  const source = statsOverview.value
  if (source == null) return null
  for (const key of keys) {
    const value = source[key]
    if (value != null) return typeof value === 'number' ? value.toLocaleString('zh-CN') : String(value)
  }
  return null
}

const activeExperimentName = computed(() => {
  const source = statsOverview.value
  if (source == null) return null
  const value = source.active_experiment
  if (value != null && typeof value === 'object') {
    const name = (value as Record<string, unknown>).name
    return name == null ? null : String(name)
  }
  return null
})

const statRows = computed(() => [
  { label: '实验数', value: pickStat('ab_experiments_count', 'experiments_total', 'experiments') },
  { label: '活跃实验', value: activeExperimentName.value ?? pickStat('experiments_active', 'active_experiments') ?? null },
  { label: '商品数', value: pickStat('shop_items_count', 'shop_items') },
  { label: '黑名单数', value: pickStat('blacklist_count', 'blacklist') },
  { label: '成员数', value: pickStat('member_count', 'members') },
])

function displayScalar(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'number') return value.toLocaleString('zh-CN')
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function flattenUsage(value: unknown, prefix: string, out: Array<{ key: string; value: string }>, depth: number): void {
  if (value != null && typeof value === 'object' && !Array.isArray(value)) {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const label = prefix ? `${prefix} · ${k}` : k
      if (v != null && typeof v === 'object' && depth < 2) flattenUsage(v, label, out, depth + 1)
      else out.push({ key: label, value: displayScalar(v) })
    }
    return
  }
  out.push({ key: prefix || '值', value: displayScalar(value) })
}

onMounted(async () => {
  const results = await Promise.allSettled([
    api.get<GlobalSettings | null>('settings/global'),
    api.get<unknown>('token-usage'),
    api.get<AbExperiment[] | null>('ab/experiments'),
    api.get<Record<string, unknown> | null>('stats/overview'),
    api.get<AuditListResult | AuditEntry[] | null>('audit?page_size=8'),
  ])
  if (results[0].status === 'fulfilled') globalSettings.value = results[0].value
  if (results[1].status === 'fulfilled') {
    usageRows.value = []
    flattenUsage(results[1].value, '', usageRows.value, 0)
  }
  if (results[3].status === 'fulfilled') statsOverview.value = results[3].value ?? null
  if (results[4].status === 'fulfilled') {
    const data = results[4].value
    const rows = Array.isArray(data) ? data : data?.items
    recentAudit.value = Array.isArray(rows) ? rows.slice(0, 8) : []
  }
  if (results[2].status === 'fulfilled' && Array.isArray(results[2].value)) {
    experiments.value = results[2].value
    const enabled = experiments.value.filter((e) => e.enabled)
    const statsResults = await Promise.allSettled(
      enabled.map((e) => api.get<AbStats | null>(`ab/experiments/${e.id}/stats?days=30`)),
    )
    enabled.forEach((experiment, index) => {
      const result = statsResults[index]
      if (result.status === 'fulfilled' && result.value != null && Array.isArray(result.value.arms)) {
        abTotals.value[experiment.id] = {
          routed: result.value.arms.reduce((sum, arm) => sum + toNumber(arm.routed_count), 0),
          votes: result.value.arms.reduce((sum, arm) => sum + toNumber(arm.votes?.total), 0),
        }
      }
    })
  }
  loading.value = false
})
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-grid :x-gap="16" :y-gap="16" :cols="1" s="2" m="2" l="3" responsive="screen">
        <n-grid-item>
          <n-card title="运行状态" size="small">
            <template v-if="globalSettings">
              <n-space :size="8">
                <n-tag :type="globalSettings.chat_enabled ? 'success' : 'error'" :bordered="false">
                  聊天{{ globalSettings.chat_enabled ? '开启' : '关闭' }}
                </n-tag>
                <n-tag :type="globalSettings.two_stage_enabled ? 'info' : 'default'" :bordered="false">
                  两阶段{{ globalSettings.two_stage_enabled ? '开' : '关' }}
                </n-tag>
                <n-tag :type="globalSettings.api_fallback_enabled ? 'info' : 'default'" :bordered="false">
                  故障转移{{ globalSettings.api_fallback_enabled ? '开' : '关' }}
                </n-tag>
                <n-tag :type="globalSettings.warm_up_enabled ? 'info' : 'default'" :bordered="false">
                  预热{{ globalSettings.warm_up_enabled ? '开' : '关' }}
                </n-tag>
                <n-tag :bordered="false">回复延迟 {{ globalSettings.reply_delay_seconds }} 秒</n-tag>
              </n-space>
            </template>
            <n-text v-else depth="3">无法加载全局设置</n-text>
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="Token 用量" size="small">
            <n-descriptions v-if="usageRows.length > 0" :column="1" size="small" label-placement="left" bordered>
              <n-descriptions-item v-for="row in usageRows" :key="row.key" :label="row.key">
                {{ row.value }}
              </n-descriptions-item>
            </n-descriptions>
            <n-text v-else depth="3">暂无数据</n-text>
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="A/B 实验" size="small">
            <template v-if="experiments.length > 0">
              <n-space vertical :size="10">
                <div v-for="experiment in experiments" :key="experiment.id" class="ab-row">
                  <n-space align="center" :size="8">
                    <n-tag :type="experiment.enabled ? 'success' : 'default'" size="small" :bordered="false">
                      {{ experiment.enabled ? '进行中' : '已停用' }}
                    </n-tag>
                    <span>{{ experiment.name }}</span>
                    <n-text depth="3" size="small">
                      中签 {{ abTotals[experiment.id]?.routed ?? 0 }} · 投票 {{ abTotals[experiment.id]?.votes ?? 0 }}
                    </n-text>
                    <n-button text type="primary" size="tiny" @click="router.push({ name: 'ab-stats', params: { id: experiment.id } })">
                      查看
                    </n-button>
                  </n-space>
                </div>
              </n-space>
            </template>
            <n-text v-else depth="3">暂无实验</n-text>
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="平台数据" size="small">
            <template v-if="statsOverview != null">
              <div class="stat-grid">
                <div v-for="row in statRows" :key="row.label" class="stat-item">
                  <n-text depth="3" size="small">{{ row.label }}</n-text>
                  <div class="stat-value">{{ row.value ?? '—' }}</div>
                </div>
              </div>
            </template>
            <n-text v-else depth="3">暂无数据</n-text>
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="最近操作" size="small">
            <template v-if="recentAudit.length > 0">
              <n-space vertical :size="8">
                <div v-for="(entry, index) in recentAudit" :key="entry.id ?? index" class="audit-row">
                  <n-space align="center" :size="8">
                    <n-tag :type="auditActionTagType(entry.action)" size="small" :bordered="false">
                      {{ entry.action ?? '—' }}
                    </n-tag>
                    <span>{{ entry.target_type ?? '—' }} · {{ entry.target_id ?? '—' }}</span>
                  </n-space>
                  <n-text depth="3" size="small">{{ formatDateTime(entry.created_at) }}</n-text>
                </div>
              </n-space>
            </template>
            <n-text v-else depth="3">暂无数据</n-text>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-space>
  </n-spin>
</template>

<style scoped>
.stat-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 28px;
}
.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 88px;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
}
.audit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
