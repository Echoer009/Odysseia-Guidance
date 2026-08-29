<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import {
  NCard,
  NDataTable,
  NPagination,
  NPopover,
  NSelect,
  NSpace,
  NTag,
  type DataTableColumns,
  type SelectOption,
} from 'naive-ui'
import { api } from '../api'
import type { AuditEntry, AuditListResult } from '../types'
import { auditActionTagType, formatDateTime, prettyJson } from '../utils'

const loading = ref(true)
const items = ref<AuditEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const targetType = ref<string | null>(null)
const knownTypes = ref<string[]>([])

const pageSizeOptions = [20, 50, 100].map((n) => ({ label: `每页 ${n} 条`, value: n }))
const typeOptions = computed<SelectOption[]>(() => knownTypes.value.map((t) => ({ label: t, value: t })))

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('page', String(page.value))
    params.set('page_size', String(pageSize.value))
    const filter = targetType.value == null ? '' : targetType.value.trim()
    if (filter.length > 0) params.set('target_type', filter)
    const data = await api.get<AuditListResult | AuditEntry[] | null>(`audit?${params.toString()}`)
    const rows = Array.isArray(data) ? data : data?.items
    items.value = Array.isArray(rows) ? rows : []
    const totalCount = Array.isArray(data) ? undefined : data?.total
    total.value = typeof totalCount === 'number' ? totalCount : items.value.length
    for (const row of items.value) {
      const t = row.target_type
      if (t != null && String(t).length > 0 && !knownTypes.value.includes(String(t))) knownTypes.value.push(String(t))
    }
  } catch {
  } finally {
    loading.value = false
  }
}

function changePageSize(value: unknown): void {
  const n = Number(value)
  if (!Number.isFinite(n)) return
  pageSize.value = n
  page.value = 1
  void load()
}

watch(targetType, () => {
  page.value = 1
  void load()
})

const columns: DataTableColumns<AuditEntry> = [
  {
    title: '时间',
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at ?? row.time),
  },
  { title: '操作者', key: 'user_id', width: 170, render: (row) => String(row.user_id ?? '—') },
  {
    title: '动作',
    key: 'action',
    width: 130,
    render: (row) =>
      h(
        NTag,
        { type: auditActionTagType(row.action), size: 'small', bordered: false },
        { default: () => String(row.action ?? '—') },
      ),
  },
  {
    title: '对象',
    key: 'target',
    minWidth: 220,
    render: (row) => `${String(row.target_type ?? '—')} · ${String(row.target_id ?? '—')}`,
  },
  {
    title: '详情',
    key: 'detail',
    width: 90,
    render: (row) => {
      const detail: unknown = row.detail
      if (detail == null) return '—'
      return h(
        NPopover,
        { trigger: 'click', scrollable: true, style: { maxWidth: '440px' } },
        {
          trigger: () => h('span', { class: 'cell-json' }, '查看'),
          default: () => h('pre', { class: 'json-pre' }, prettyJson(detail)),
        },
      )
    },
  },
]

function rowKeyOf(row: AuditEntry): string {
  if (row.id != null) return String(row.id)
  return `${String(row.action ?? '')}|${String(row.target_type ?? '')}|${String(row.target_id ?? '')}|${String(row.created_at ?? '')}`
}

onMounted(() => void load())
</script>

<template>
  <n-card title="操作日志" class="page-card">
    <template #header-extra>
      <n-space align="center" :size="12">
        <n-select
          v-model:value="targetType"
          :options="typeOptions"
          filterable
          tag
          clearable
          placeholder="对象类型筛选（可输入）"
          size="small"
          style="width: 260px"
        />
        <n-select
          :value="pageSize"
          :options="pageSizeOptions"
          size="small"
          style="width: 130px"
          @update:value="changePageSize"
        />
      </n-space>
    </template>
    <n-space vertical :size="12">
      <n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="rowKeyOf"
        size="small"
      />
      <n-space justify="end">
        <n-pagination
          :page="page"
          :item-count="total"
          :page-size="pageSize"
          @update:page="(p: number) => { page = p; void load() }"
        />
      </n-space>
    </n-space>
  </n-card>
</template>
