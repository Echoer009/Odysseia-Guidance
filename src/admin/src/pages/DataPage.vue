<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NButton,
  NCard,
  NDataTable,
  NEllipsis,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NPopconfirm,
  NPopover,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  type DataTableColumns,
  type DataTableRowData,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'
import type { DataField, DataListResult, DataResourceInfo } from '../types'
import { formatDateTime, prettyJson } from '../utils'

const route = useRoute()

const loading = ref(false)
const saving = ref(false)
const items = ref<DataTableRowData[]>([])
const total = ref(0)
const fields = ref<DataField[]>([])
const resourceLabels = ref<Record<string, string>>({})

const searchText = ref('')
const appliedSearch = ref('')
const page = ref(1)
const pageSize = ref(20)

const showModal = ref(false)
const editingRow = ref<DataTableRowData | null>(null)
const drafts = ref<Record<string, any>>({})
const readOnlyNames = ref<string[]>([])

const resource = computed(() => String(route.params.resource ?? ''))
const resourceLabel = computed(() => resourceLabels.value[resource.value] ?? resource.value)
const isReadOnly = computed(() => readOnlyNames.value.includes(resource.value))
const hasEditable = computed(() => fields.value.some((field) => field.editable !== false))
const editableFields = computed(() => fields.value.filter((field) => field.editable !== false))
const pkName = computed(() => fields.value.find((field) => field.name === 'id')?.name ?? fields.value[0]?.name ?? 'id')
const scrollX = computed(() => Math.max(640, fields.value.length * 150))

const pageSizeOptions = [20, 50, 100].map((n) => ({ label: `每页 ${n} 条`, value: n }))

function fieldType(field: DataField): string {
  return String(field.type ?? 'string').toLowerCase()
}

function formKind(field: DataField): 'string' | 'text' | 'number' | 'bool' | 'json' {
  const t = fieldType(field)
  if (t === 'text') return 'text'
  if (t === 'int' || t === 'float' || t === 'number') return 'number'
  if (t === 'bool' || t === 'boolean') return 'bool'
  if (t === 'json') return 'json'
  return 'string'
}

function fieldLabel(field: DataField): string {
  return field.label ?? field.name
}

function inferFields(rows: DataTableRowData[]): DataField[] {
  if (rows.length === 0) return []
  const sample = rows[0]
  return Object.keys(sample).map((name) => {
    const value = sample[name]
    let type = 'string'
    if (typeof value === 'boolean') type = 'bool'
    else if (typeof value === 'number') type = 'int'
    else if (value != null && typeof value === 'object') type = 'json'
    else if (typeof value === 'string' && /(_at|_time|_date)$/.test(name)) type = 'datetime'
    else if (typeof value === 'string' && value.length > 120) type = 'text'
    return { name, type, editable: true }
  })
}

async function load(): Promise<void> {
  if (resource.value.length === 0) return
  loading.value = true
  try {
    const params = new URLSearchParams()
    const q = appliedSearch.value.trim()
    if (q.length > 0) params.set('q', q)
    params.set('page', String(page.value))
    params.set('page_size', String(pageSize.value))
    const data = await api.get<DataListResult | null>(`data/${encodeURIComponent(resource.value)}?${params.toString()}`)
    const rows = data?.items
    items.value = Array.isArray(rows) ? rows : []
    const totalCount = data?.total
    total.value = typeof totalCount === 'number' ? totalCount : items.value.length
    const rawFields = data?.fields
    fields.value = Array.isArray(rawFields) ? rawFields : inferFields(items.value)
  } catch {
  } finally {
    loading.value = false
  }
}

function applySearch(): void {
  appliedSearch.value = searchText.value
  page.value = 1
  void load()
}

function changePageSize(value: unknown): void {
  const n = Number(value)
  if (!Number.isFinite(n)) return
  pageSize.value = n
  page.value = 1
  void load()
}

function openCreate(): void {
  editingRow.value = null
  drafts.value = {}
  for (const field of editableFields.value) {
    const kind = formKind(field)
    if (kind === 'number') drafts.value[field.name] = null
    else if (kind === 'bool') drafts.value[field.name] = false
    else drafts.value[field.name] = ''
  }
  showModal.value = true
}

function openEdit(row: DataTableRowData): void {
  editingRow.value = row
  drafts.value = {}
  for (const field of editableFields.value) {
    const value = row[field.name]
    const kind = formKind(field)
    if (kind === 'bool') drafts.value[field.name] = !!value
    else if (kind === 'number') {
      if (typeof value === 'number') drafts.value[field.name] = value
      else if (value != null && Number.isFinite(Number(value))) drafts.value[field.name] = Number(value)
      else drafts.value[field.name] = null
    } else if (kind === 'json') drafts.value[field.name] = value == null ? '' : prettyJson(value)
    else drafts.value[field.name] = value == null ? '' : String(value)
  }
  showModal.value = true
}

function jsonFieldError(field: DataField): string {
  if (formKind(field) !== 'json') return ''
  const text = String(drafts.value[field.name] ?? '').trim()
  if (text.length === 0) return ''
  try {
    JSON.parse(text)
    return ''
  } catch (err) {
    return err instanceof Error ? `JSON 格式错误：${err.message}` : 'JSON 格式错误'
  }
}

async function saveModal(): Promise<void> {
  const body: Record<string, unknown> = {}
  for (const field of editableFields.value) {
    const kind = formKind(field)
    if (kind === 'bool') body[field.name] = !!drafts.value[field.name]
    else if (kind === 'number') body[field.name] = drafts.value[field.name] ?? null
    else if (kind === 'json') {
      const text = String(drafts.value[field.name] ?? '').trim()
      if (text.length === 0) body[field.name] = null
      else {
        try {
          body[field.name] = JSON.parse(text)
        } catch {
          toastError(`「${fieldLabel(field)}」不是合法的 JSON`)
          return
        }
      }
    } else body[field.name] = String(drafts.value[field.name] ?? '')
  }
  saving.value = true
  try {
    if (editingRow.value == null) {
      await api.post(`data/${encodeURIComponent(resource.value)}`, body)
    } else {
      const pk = editingRow.value[pkName.value]
      if (pk == null || String(pk).length === 0) {
        toastError('缺少主键，无法保存')
        return
      }
      await api.put(`data/${encodeURIComponent(resource.value)}/${encodeURIComponent(String(pk))}`, body)
    }
    showModal.value = false
    toastSuccess('已保存')
    await load()
  } catch {
  } finally {
    saving.value = false
  }
}

async function removeRow(row: DataTableRowData): Promise<void> {
  const pk = row[pkName.value]
  if (pk == null || String(pk).length === 0) {
    toastError('缺少主键，无法删除')
    return
  }
  try {
    await api.delete(`data/${encodeURIComponent(resource.value)}/${encodeURIComponent(String(pk))}`)
    toastSuccess('已删除')
    await load()
  } catch {
  }
}

function renderCell(field: DataField, value: unknown) {
  if (value == null) return '—'
  const t = fieldType(field)
  if (t === 'bool' || t === 'boolean') {
    return h(
      NTag,
      { type: value ? 'success' : 'default', size: 'small', bordered: false },
      { default: () => (value ? '是' : '否') },
    )
  }
  if (t === 'json') {
    const text = prettyJson(value)
    const flat = text.replace(/\s+/g, ' ')
    const collapsed = flat.length > 48 ? `${flat.slice(0, 48)}…` : flat
    return h(
      NPopover,
      { trigger: 'click', scrollable: true, style: { maxWidth: '480px' } },
      {
        trigger: () => h('span', { class: 'cell-json' }, collapsed),
        default: () => h('pre', { class: 'json-pre' }, text),
      },
    )
  }
  if (t === 'datetime') return formatDateTime(value)
  const text = typeof value === 'object' ? prettyJson(value) : String(value)
  if (t === 'text' || text.length > 80) {
    return h(NEllipsis, { style: 'max-width: 280px' }, { default: () => text })
  }
  return text
}

const columns = computed<DataTableColumns<DataTableRowData>>(() => {
  const cols: DataTableColumns<DataTableRowData> = fields.value.map((field) => ({
    title: fieldLabel(field),
    key: field.name,
    render: (row: DataTableRowData) => renderCell(field, row[field.name]),
  }))
  cols.push({
    title: '操作',
    key: '__actions',
    width: hasEditable.value ? 150 : 100,
    render: (row: DataTableRowData) =>
      h(
        NSpace,
        { size: 8 },
        {
          default: () => [
            hasEditable.value
              ? h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' })
              : null,
            isReadOnly.value
              ? null
              : h(
                  NPopconfirm,
                  { onPositiveClick: () => void removeRow(row) },
                  {
                    default: () => '确认删除该记录？',
                    trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '删除' }),
                  },
                ),
          ],
        },
      ),
  })
  return cols
})

function rowKeyOf(row: DataTableRowData): string | number {
  const pk = row[pkName.value]
  return pk == null ? JSON.stringify(row).slice(0, 64) : pk
}

watch(resource, () => {
  page.value = 1
  searchText.value = ''
  appliedSearch.value = ''
  showModal.value = false
  void load()
})

onMounted(() => {
  void load()
  void (async () => {
    let list: DataResourceInfo[] | null = null
    try {
      const wrapped = await api.get<{ resources?: DataResourceInfo[] } | null>('data')
      const arr = wrapped?.resources
      if (Array.isArray(arr)) list = arr
    } catch {
    }
    if (list == null) {
      try {
        const direct = await api.get<DataResourceInfo[] | null>('data/resources')
        if (Array.isArray(direct)) list = direct
      } catch {
      }
    }
    if (list != null) {
      const labels: Record<string, string> = {}
      const readOnly: string[] = []
      for (const entry of list) {
        labels[entry.name] = entry.label ?? entry.name
        if ((entry as { read_only?: boolean }).read_only === true) readOnly.push(entry.name)
      }
      resourceLabels.value = labels
      readOnlyNames.value = readOnly
    }
  })()
})
</script>

<template>
  <n-card :title="`数据管理 · ${resourceLabel}`" class="page-card">
    <template #header-extra>
      <n-space align="center" :size="12">
        <n-input
          v-model:value="searchText"
          clearable
          placeholder="搜索关键字，回车执行"
          size="small"
          style="width: 240px"
          @keyup.enter="applySearch"
        />
        <n-select
          :value="pageSize"
          :options="pageSizeOptions"
          size="small"
          style="width: 130px"
          @update:value="changePageSize"
        />
        <n-button v-if="hasEditable" type="primary" size="small" @click="openCreate">新增</n-button>
      </n-space>
    </template>
    <n-space vertical :size="12">
      <n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="rowKeyOf"
        :scroll-x="scrollX"
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
    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editingRow == null ? '新增记录' : '编辑记录'"
      style="width: 640px"
    >
      <n-form label-placement="top" :style="{ maxHeight: '60vh', overflow: 'auto' }">
        <n-form-item
          v-for="field in editableFields"
          :key="field.name"
          :label="fieldLabel(field)"
          :feedback="jsonFieldError(field) || undefined"
          :validation-status="jsonFieldError(field) ? 'error' : undefined"
        >
          <n-input
            v-if="formKind(field) === 'string'"
            v-model:value="drafts[field.name]"
            :placeholder="fieldType(field) === 'datetime' ? 'ISO 时间，如 2026-01-01T12:00:00' : undefined"
          />
          <n-input
            v-else-if="formKind(field) === 'text'"
            v-model:value="drafts[field.name]"
            type="textarea"
            :rows="3"
          />
          <n-input-number
            v-else-if="formKind(field) === 'number'"
            v-model:value="drafts[field.name]"
            style="width: 100%"
            :precision="fieldType(field) === 'int' ? 0 : undefined"
          />
          <n-switch v-else-if="formKind(field) === 'bool'" v-model:value="drafts[field.name]" />
          <n-input
            v-else
            v-model:value="drafts[field.name]"
            type="textarea"
            class="mono"
            :rows="5"
            placeholder="JSON 内容"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveModal">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-card>
</template>
