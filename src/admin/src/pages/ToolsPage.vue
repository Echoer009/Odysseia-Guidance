<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NSpace,
  NSwitch,
  NTag,
  type DataTableColumns,
} from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { ToolInfo } from '../types'

type ToolRow = ToolInfo & { original: boolean }

const loading = ref(true)
const saving = ref(false)
const rows = ref<ToolRow[]>([])

const dirty = computed(() => rows.value.some((row) => row.enabled !== row.original))

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<ToolInfo[] | null>('tools')
    rows.value = (Array.isArray(data) ? data : []).map((tool) => ({ ...tool, original: tool.enabled }))
  } catch {} finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.put('tools', { disabled_tools: rows.value.filter((row) => !row.enabled).map((row) => row.name) })
    rows.value.forEach((row) => {
      row.original = row.enabled
    })
    toastSuccess('已保存')
  } catch {} finally {
    saving.value = false
  }
}

const columns: DataTableColumns<ToolRow> = [
  {
    title: '名称',
    key: 'name',
    width: 240,
    render: (row) =>
      h(NSpace, { size: 6, align: 'center', wrapItem: false }, {
        default: () => [
          h('span', null, row.name),
          row.protected ? h(NTag, { size: 'tiny', type: 'warning', bordered: false }, { default: () => '受保护' }) : null,
        ],
      }),
  },
  { title: '描述', key: 'description', ellipsis: { tooltip: true } },
  {
    title: '启用',
    key: 'enabled',
    width: 100,
    render: (row) =>
      h(NSwitch, {
        value: row.enabled,
        disabled: row.protected,
        'onUpdate:value': (value: boolean) => {
          row.enabled = value
        },
      }),
  },
]

onMounted(() => void load())
</script>

<template>
  <n-card title="AI 工具" class="page-card">
    <template #header-extra>
      <n-button type="primary" size="small" :disabled="!dirty" :loading="saving" @click="save">保存修改</n-button>
    </template>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :row-key="(row: ToolRow) => row.name" size="small" />
  </n-card>
</template>
