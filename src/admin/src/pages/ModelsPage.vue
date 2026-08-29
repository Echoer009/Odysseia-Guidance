<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  type DataTableColumns,
  type FormInst,
  type FormRules,
  type SelectOption,
} from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import CapabilityTags from '../components/CapabilityTags.vue'
import type { GenerationConfig, ModelConfig, PromptConfig, Provider } from '../types'

type EditableGeneration = {
  temperature: number | null
  top_p: number | null
  top_k: number | null
  max_output_tokens: number | null
  presence_penalty: number | null
  frequency_penalty: number | null
  thinking_budget_tokens: number | null
}

type EditablePrompt = {
  system_prompt: string
  jailbreak_user_prompt: string
  jailbreak_model_response: string
  jailbreak_final_instruction: string
  use_cache_optimized_build: boolean
}

type EditableModel = {
  id: number | null
  model_name: string
  display_name: string
  provider_id: number | null
  actual_model: string
  supports_vision: boolean
  supports_tools: boolean
  supports_thinking: boolean
  max_output_tokens: number | null
  enabled: boolean
  generation_config: EditableGeneration
  prompt_config: EditablePrompt
}

function defaultGeneration(): EditableGeneration {
  return {
    temperature: 1,
    top_p: 0.95,
    top_k: 0,
    max_output_tokens: 8192,
    presence_penalty: 0,
    frequency_penalty: 0,
    thinking_budget_tokens: 0,
  }
}

function defaultPrompt(): EditablePrompt {
  return {
    system_prompt: '',
    jailbreak_user_prompt: '',
    jailbreak_model_response: '',
    jailbreak_final_instruction: '',
    use_cache_optimized_build: false,
  }
}

function defaultForm(): EditableModel {
  return {
    id: null,
    model_name: '',
    display_name: '',
    provider_id: null,
    actual_model: '',
    supports_vision: false,
    supports_tools: false,
    supports_thinking: false,
    max_output_tokens: 8192,
    enabled: true,
    generation_config: defaultGeneration(),
    prompt_config: defaultPrompt(),
  }
}

const loading = ref(true)
const saving = ref(false)
const rows = ref<ModelConfig[]>([])
const providers = ref<Provider[]>([])
const showModal = ref(false)
const formRef = ref<FormInst | null>(null)
const form = reactive<EditableModel>(defaultForm())

const rules: FormRules = {
  model_name: { required: true, message: '请输入模型标识', trigger: ['blur', 'input'] },
  provider_id: { required: true, type: 'number', message: '请选择服务商', trigger: ['blur', 'change'] },
}

const providerOptions = computed<SelectOption[]>(() =>
  providers.value.map((p) => ({ label: `${p.display_name || p.name}（${p.name}）`, value: p.id })),
)

function providerName(id: number): string {
  const provider = providers.value.find((item) => item.id === id)
  return provider ? provider.display_name || provider.name : String(id)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const results = await Promise.all([api.get<ModelConfig[] | null>('models'), api.get<Provider[] | null>('providers')])
    rows.value = Array.isArray(results[0]) ? results[0] : []
    providers.value = Array.isArray(results[1]) ? results[1] : []
  } catch {} finally {
    loading.value = false
  }
}

function openCreate(): void {
  Object.assign(form, defaultForm())
  form.generation_config = defaultGeneration()
  form.prompt_config = defaultPrompt()
  showModal.value = true
}

function openEdit(row: ModelConfig): void {
  form.id = row.id
  form.model_name = row.model_name ?? ''
  form.display_name = row.display_name ?? ''
  form.provider_id = row.provider_id ?? null
  form.actual_model = row.actual_model ?? ''
  form.supports_vision = !!row.supports_vision
  form.supports_tools = !!row.supports_tools
  form.supports_thinking = !!row.supports_thinking
  form.max_output_tokens = row.max_output_tokens ?? null
  form.enabled = !!row.enabled
  Object.assign(form.generation_config, defaultGeneration(), (row.generation_config ?? {}) as Partial<GenerationConfig>)
  Object.assign(form.prompt_config, defaultPrompt(), (row.prompt_config ?? {}) as Partial<PromptConfig>)
  showModal.value = true
}

async function save(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const body = {
    model_name: form.model_name.trim(),
    display_name: form.display_name.trim(),
    provider_id: form.provider_id,
    actual_model: form.actual_model.trim(),
    supports_vision: form.supports_vision,
    supports_tools: form.supports_tools,
    supports_thinking: form.supports_thinking,
    max_output_tokens: form.max_output_tokens ?? 0,
    enabled: form.enabled,
    generation_config: {
      temperature: form.generation_config.temperature ?? 0,
      top_p: form.generation_config.top_p ?? 0,
      top_k: form.generation_config.top_k ?? 0,
      max_output_tokens: form.generation_config.max_output_tokens ?? 0,
      presence_penalty: form.generation_config.presence_penalty ?? 0,
      frequency_penalty: form.generation_config.frequency_penalty ?? 0,
      thinking_budget_tokens: form.generation_config.thinking_budget_tokens ?? 0,
    },
    prompt_config: { ...form.prompt_config },
  }
  saving.value = true
  try {
    if (form.id == null) await api.post('models', body)
    else await api.put(`models/${form.id}`, body)
    showModal.value = false
    toastSuccess('已保存')
    await load()
  } catch {} finally {
    saving.value = false
  }
}

async function remove(row: ModelConfig): Promise<void> {
  try {
    await api.delete(`models/${row.id}`)
    toastSuccess('已删除')
    await load()
  } catch {}
}

const columns: DataTableColumns<ModelConfig> = [
  { title: '模型标识', key: 'model_name', width: 180 },
  { title: '显示名', key: 'display_name', width: 160 },
  {
    title: '服务商',
    key: 'provider_id',
    width: 130,
    render: (row) => providerName(row.provider_id),
  },
  { title: '实际模型', key: 'actual_model', ellipsis: { tooltip: true } },
  {
    title: '能力',
    key: 'capabilities',
    width: 200,
    render: (row) =>
      h(CapabilityTags, { vision: row.supports_vision, tools: row.supports_tools, thinking: row.supports_thinking }),
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
              default: () => '确认删除该模型？',
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
  <n-card title="模型配置" class="page-card">
    <template #header-extra>
      <n-button type="primary" size="small" @click="openCreate">新增模型</n-button>
    </template>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :row-key="(row: ModelConfig) => row.id" size="small" />
    <n-modal v-model:show="showModal" preset="card" :title="form.id == null ? '新增模型' : '编辑模型'" style="width: 760px">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="140">
        <n-tabs type="line" animated>
          <n-tab-pane name="basic" tab="基本信息">
            <n-space vertical size="small">
              <n-form-item label="模型标识" path="model_name">
                <n-input v-model:value="form.model_name" placeholder="唯一标识，如 gemini-2.5-pro" />
              </n-form-item>
              <n-form-item label="显示名">
                <n-input v-model:value="form.display_name" placeholder="显示名称" />
              </n-form-item>
              <n-form-item label="服务商" path="provider_id">
                <n-select v-model:value="form.provider_id" :options="providerOptions" filterable placeholder="选择服务商" />
              </n-form-item>
              <n-form-item label="实际模型">
                <n-input v-model:value="form.actual_model" placeholder="实际调用的模型 ID" />
              </n-form-item>
              <n-form-item label="最大输出 Token">
                <n-input-number v-model:value="form.max_output_tokens" :min="1" :max="2000000" :step="256" style="width: 200px" />
              </n-form-item>
              <n-form-item label="支持视觉">
                <n-switch v-model:value="form.supports_vision" />
              </n-form-item>
              <n-form-item label="支持工具">
                <n-switch v-model:value="form.supports_tools" />
              </n-form-item>
              <n-form-item label="支持思考">
                <n-switch v-model:value="form.supports_thinking" />
              </n-form-item>
              <n-form-item label="启用">
                <n-switch v-model:value="form.enabled" />
              </n-form-item>
            </n-space>
          </n-tab-pane>
          <n-tab-pane name="params" tab="参数与提示词">
            <n-space vertical size="small">
              <n-form-item label="temperature">
                <n-input-number v-model:value="form.generation_config.temperature" :min="0" :max="2" :step="0.05" :precision="2" style="width: 200px" />
              </n-form-item>
              <n-form-item label="top_p">
                <n-input-number v-model:value="form.generation_config.top_p" :min="0" :max="1" :step="0.01" :precision="2" style="width: 200px" />
              </n-form-item>
              <n-form-item label="top_k">
                <n-input-number v-model:value="form.generation_config.top_k" :min="0" :max="4096" :step="1" :precision="0" style="width: 200px" />
              </n-form-item>
              <n-form-item label="生成最大 Token">
                <n-input-number v-model:value="form.generation_config.max_output_tokens" :min="0" :max="2000000" :step="256" style="width: 200px" />
              </n-form-item>
              <n-form-item label="presence_penalty">
                <n-input-number v-model:value="form.generation_config.presence_penalty" :min="-2" :max="2" :step="0.1" :precision="2" style="width: 200px" />
              </n-form-item>
              <n-form-item label="frequency_penalty">
                <n-input-number v-model:value="form.generation_config.frequency_penalty" :min="-2" :max="2" :step="0.1" :precision="2" style="width: 200px" />
              </n-form-item>
              <n-form-item label="思考预算 Token">
                <n-input-number v-model:value="form.generation_config.thinking_budget_tokens" :min="-1" :max="2000000" :step="128" :precision="0" style="width: 200px" />
              </n-form-item>
              <n-form-item label="System Prompt">
                <n-input v-model:value="form.prompt_config.system_prompt" type="textarea" :rows="6" placeholder="系统提示词" />
              </n-form-item>
              <n-form-item label="越狱用户提示">
                <n-input v-model:value="form.prompt_config.jailbreak_user_prompt" type="textarea" :rows="4" placeholder="jailbreak_user_prompt" />
              </n-form-item>
              <n-form-item label="越狱模型回复">
                <n-input v-model:value="form.prompt_config.jailbreak_model_response" type="textarea" :rows="4" placeholder="jailbreak_model_response" />
              </n-form-item>
              <n-form-item label="越狱最终指令">
                <n-input v-model:value="form.prompt_config.jailbreak_final_instruction" type="textarea" :rows="4" placeholder="jailbreak_final_instruction" />
              </n-form-item>
              <n-form-item label="缓存优化构建">
                <n-switch v-model:value="form.prompt_config.use_cache_optimized_build" />
              </n-form-item>
            </n-space>
          </n-tab-pane>
        </n-tabs>
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
