<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NFormItem, NInputNumber, NSpace, NSpin, NSwitch } from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { GlobalSettings } from '../types'

const loading = ref(true)
const saving = ref(false)

const form = reactive<GlobalSettings>({
  chat_enabled: false,
  two_stage_enabled: false,
  api_fallback_enabled: false,
  feeding_image_enabled: false,
  feeding_command_enabled: false,
  warm_up_enabled: false,
  reply_delay_seconds: 0,
})

onMounted(async () => {
  try {
    const data = await api.get<GlobalSettings | null>('settings/global')
    if (data != null) Object.assign(form, data)
  } catch {} finally {
    loading.value = false
  }
})

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.put('settings/global', { ...form })
    toastSuccess('已保存')
  } catch {} finally {
    saving.value = false
  }
}
</script>

<template>
  <n-spin :show="loading">
    <n-card title="全局设置" class="page-card">
      <n-space vertical size="large">
        <n-form-item label="聊天功能" label-placement="left">
          <n-switch v-model:value="form.chat_enabled" />
        </n-form-item>
        <n-form-item label="两阶段生成" label-placement="left">
          <n-switch v-model:value="form.two_stage_enabled" />
        </n-form-item>
        <n-form-item label="API 故障转移" label-placement="left">
          <n-switch v-model:value="form.api_fallback_enabled" />
        </n-form-item>
        <n-form-item label="图片投喂" label-placement="left">
          <n-switch v-model:value="form.feeding_image_enabled" />
        </n-form-item>
        <n-form-item label="投喂指令" label-placement="left">
          <n-switch v-model:value="form.feeding_command_enabled" />
        </n-form-item>
        <n-form-item label="预热" label-placement="left">
          <n-switch v-model:value="form.warm_up_enabled" />
        </n-form-item>
        <n-form-item label="回复延迟（秒）" label-placement="left">
          <n-input-number v-model:value="form.reply_delay_seconds" :min="0" :max="600" :step="1" style="width: 180px" />
        </n-form-item>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </n-card>
  </n-spin>
</template>
