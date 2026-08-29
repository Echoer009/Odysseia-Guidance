<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  type DataTableColumns,
  type FormInst,
  type FormRules,
  type SelectOption,
} from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { Provider } from '../types'

const loading = ref(true)
const saving = ref(false)
const rows = ref<Provider[]>([])
const showModal = ref(false)
const formRef = ref<FormInst | null>(null)

const providerTypeOptions: SelectOption[] = [
  { label: 'gemini', value: 'gemini' },
  { label: 'deepseek', value: 'deepseek' },
  { label: 'openai_compatible', value: 'openai_compatible' },
  { label: 'grok', value: 'grok' },
  { label: 'custom', value: 'custom' },
]

const form = reactive({
  id: null as number | null,
  name: '',
  provider_type: null as string | null,
  display_name: '',
  base_url: '',
  api_key: '',
  enabled: true,
})

const rules: FormRules = {
  name: { required: true, message: '请输入名称', trigger: ['blur', 'input'] },
  provider_type: { required: true, message: '请选择类型', trigger: ['blur', 'change'] },
}

function resetForm(): void {
  form.id = null
  form.name = ''
  form.provider_type = null
  form.display_name = ''
  form.base_url = ''
  form.api_key = ''
  form.enabled = true
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<Provider[] | null>('providers')
    rows.value = Array.isArray(data) ? data : []
  } catch {} finally {
    loading.value = false
  }
}

function openCreate(): void {
  resetForm()
  showModal.value = true
}

function openEdit(row: Provider): void {
  form.id = row.id
  form.name = row.name
  form.provider_type = row.provider_type
  form.display_name = row.display_name
  form.base_url = row.base_url
  form.api_key = ''
  form.enabled = row.enabled
  showModal.value = true
}

async function save(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const body: Record<string, unknown> = {
    name: form.name.trim(),
    provider_type: form.provider_type,
    display_name: form.display_name.trim(),
    base_url: form.base_url.trim(),
    enabled: form.enabled,
  }
  if (form.api_key.length > 0) body.api_key = form.api_key
  saving.value = true
  try {
    if (form.id == null) await api.post('providers', body)
    else await api.put(`providers/${form.id}`, body)
    showModal.value = false
    toastSuccess('已保存')
    await load()
  } catch {} finally {
    saving.value = false
  }
}

async function remove(row: Provider): Promise<void> {
  try {
    await api.delete(`providers/${row.id}`)
    toastSuccess('已删除')
    await load()
  } catch {}
}

const columns: DataTableColumns<Provider> = [
  { title: '名称', key: 'name', width: 140 },
  { title: '显示名', key: 'display_name', width: 140 },
  {
    title: '类型',
    key: 'provider_type',
    width: 150,
    render: (row) => h(NTag, { size: 'small' }, { default: () => row.provider_type }),
  },
  { title: 'Base URL', key: 'base_url', ellipsis: { tooltip: true } },
  {
    title: 'API Key',
    key: 'has_api_key',
    width: 100,
    render: (row) => (row.has_api_key ? '已配置' : '未配置'),
  },
  {
    title: '状态',
    key: 'enabled',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { type: row.enabled ? 'success' : 'default', size: 'small', bordered: false },
        { default: () => (row.enabled ? '启用' : '停用') },
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (row) =>
      h(NSpace, { size: 8 }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
          h(
            NPopconfirm,
            { onPositiveClick: () => void remove(row) },
            {
              default: () => '确认删除该服务商？',
              trigger: () =>
                h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '删除' }),
            },
          ),
        ],
      }),
  },
]

onMounted(() => void load())
</script>

<template>
  <n-card title="服务商" class="page-card">
    <template #header-extra>
      <n-button type="primary" size="small" @click="openCreate">新增服务商</n-button>
    </template>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :row-key="(row: Provider) => row.id" size="small" />
    <n-modal v-model:show="showModal" preset="card" :title="form.id == null ? '新增服务商' : '编辑服务商'" style="width: 520px">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-form-item label="名称" path="name">
          <n-input v-model:value="form.name" placeholder="唯一标识，如 google" />
        </n-form-item>
        <n-form-item label="类型" path="provider_type">
          <n-select v-model:value="form.provider_type" :options="providerTypeOptions" placeholder="选择类型" />
        </n-form-item>
        <n-form-item label="显示名">
          <n-input v-model:value="form.display_name" placeholder="显示名称" />
        </n-form-item>
        <n-form-item label="Base URL">
          <n-input v-model:value="form.base_url" placeholder="https://..." />
        </n-form-item>
        <n-form-item label="API Key">
          <n-input v-model:value="form.api_key" type="password" show-password-on="click" placeholder="留空则不修改" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-card>
</template>
