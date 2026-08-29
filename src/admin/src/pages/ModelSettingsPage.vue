<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  type DataTableColumns,
  type SelectOption,
} from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import CapabilityTags from '../components/CapabilityTags.vue'
import type { AvailableModel, GlobalSettings, ModelSelectionSettings } from '../types'

const loading = ref(true)
const saving = ref(false)
const available = ref<AvailableModel[]>([])
const twoStage = ref(false)

const form = reactive({
  ai_model: null as string | null,
  tool_model: null as string | null,
  writer_model: null as string | null,
})

const modelOptions = computed<SelectOption[]>(() =>
  available.value.map((m) => ({
    label: `${m.display_name}（${m.provider_name}）`,
    value: m.full_id,
    disabled: !m.enabled,
  })),
)

const columns: DataTableColumns<AvailableModel> = [
  { title: '模型', key: 'display_name' },
  { title: 'ID', key: 'full_id', ellipsis: { tooltip: true } },
  { title: '服务商', key: 'provider_name' },
  {
    title: '能力',
    key: 'capabilities',
    render: (row) =>
      h(CapabilityTags, { vision: row.supports_vision, tools: row.supports_tools, thinking: row.supports_thinking }),
  },
  {
    title: '状态',
    key: 'enabled',
    render: (row) =>
      h(
        NTag,
        { type: row.enabled ? 'success' : 'default', size: 'small', bordered: false },
        { default: () => (row.enabled ? '可用' : '已停用') },
      ),
  },
]

onMounted(async () => {
  try {
    const results = await Promise.all([
      api.get<ModelSelectionSettings | null>('settings/models'),
      api.get<GlobalSettings | null>('settings/global'),
    ])
    if (results[0] != null) {
      available.value = Array.isArray(results[0].available) ? results[0].available : []
      form.ai_model = results[0].ai_model
      form.tool_model = results[0].tool_model
      form.writer_model = results[0].writer_model
    }
    if (results[1] != null) twoStage.value = !!results[1].two_stage_enabled
  } catch {} finally {
    loading.value = false
  }
})

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.put('settings/models', {
      ai_model: form.ai_model,
      tool_model: form.tool_model,
      writer_model: form.writer_model,
    })
    await api.put('settings/global', { two_stage_enabled: twoStage.value })
    toastSuccess('已保存')
  } catch {} finally {
    saving.value = false
  }
}
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-card title="模型选择" class="page-card">
        <n-space vertical size="large">
          <n-form label-placement="left" label-width="120">
            <n-form-item label="主模型">
              <n-select v-model:value="form.ai_model" :options="modelOptions" filterable clearable placeholder="选择主模型" />
            </n-form-item>
            <n-form-item label="工具模型">
              <n-select v-model:value="form.tool_model" :options="modelOptions" filterable clearable placeholder="选择工具模型" />
            </n-form-item>
            <n-form-item label="写作模型">
              <n-select v-model:value="form.writer_model" :options="modelOptions" filterable clearable placeholder="选择写作模型" />
            </n-form-item>
            <n-form-item label="两阶段生成">
              <n-switch v-model:value="twoStage" />
            </n-form-item>
          </n-form>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </n-card>
      <n-card title="可用模型" class="page-card">
        <n-data-table :columns="columns" :data="available" :row-key="(row: AvailableModel) => row.full_id" size="small" />
      </n-card>
    </n-space>
  </n-spin>
</template>
