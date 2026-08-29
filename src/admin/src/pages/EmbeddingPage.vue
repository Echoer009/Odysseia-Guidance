<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NCard, NCheckbox, NCheckboxGroup, NForm, NFormItem, NSelect, NSpace, NSpin, NText } from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { EmbeddingOptionSource, EmbeddingSettings } from '../types'

const loading = ref(true)
const saving = ref(false)
const embeddingModel = ref<string | null>(null)
const disabledModels = ref<string[]>([])
const available = ref<Array<{ value: string; label: string }>>([])

function normalizeAvailable(list: EmbeddingOptionSource[]): Array<{ value: string; label: string }> {
  const out: Array<{ value: string; label: string }> = []
  for (const item of list) {
    if (typeof item === 'string') {
      out.push({ value: item, label: item })
      continue
    }
    const value = item.full_id ?? (item.id != null ? String(item.id) : undefined) ?? item.value ?? item.model ?? item.name
    if (value == null) continue
    out.push({ value, label: item.display_name ?? item.label ?? item.name ?? value })
  }
  return out
}

onMounted(async () => {
  try {
    const data = await api.get<EmbeddingSettings | null>('settings/embedding')
    if (data != null) {
      embeddingModel.value = data.embedding_model ?? null
      disabledModels.value = Array.isArray(data.disabled_embedding_models) ? data.disabled_embedding_models : []
      available.value = normalizeAvailable(Array.isArray(data.available) ? data.available : [])
    }
  } catch {} finally {
    loading.value = false
  }
})

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.put('settings/embedding', {
      embedding_model: embeddingModel.value,
      disabled_embedding_models: disabledModels.value,
    })
    toastSuccess('已保存')
  } catch {} finally {
    saving.value = false
  }
}
</script>

<template>
  <n-spin :show="loading">
    <n-card title="向量模型" class="page-card">
      <n-space vertical size="large">
        <n-form label-placement="left" label-width="120">
          <n-form-item label="当前向量模型">
            <n-select v-model:value="embeddingModel" :options="available" filterable clearable placeholder="选择向量模型" style="max-width: 420px" />
          </n-form-item>
          <n-form-item label="停用列表">
            <n-checkbox-group v-model:value="disabledModels">
              <n-space vertical size="small">
                <n-checkbox v-for="item in available" :key="item.value" :value="item.value" :label="item.label" />
              </n-space>
            </n-checkbox-group>
          </n-form-item>
        </n-form>
        <n-text depth="3" size="small">勾选的模型将被停用，不参与向量检索相关任务</n-text>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </n-card>
  </n-spin>
</template>
