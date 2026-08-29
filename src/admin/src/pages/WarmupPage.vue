<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NDynamicTags, NSpace, NSpin, NText } from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'

const loading = ref(true)
const saving = ref(false)
const channels = ref<string[]>([])
let initial: string[] = []

const dirty = computed(() => JSON.stringify(channels.value) !== JSON.stringify(initial))

function normalizeChannelIds(data: unknown): string[] {
  if (Array.isArray(data)) return data.map((item) => String(item))
  if (data != null && typeof data === 'object') {
    const ids = (data as Record<string, unknown>).channel_ids
    if (Array.isArray(ids)) return ids.map((item) => String(item))
  }
  return []
}

onMounted(async () => {
  try {
    channels.value = normalizeChannelIds(await api.get<unknown>('warmup/channels'))
    initial = [...channels.value]
  } catch {} finally {
    loading.value = false
  }
})

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.put('warmup/channels', { channel_ids: channels.value })
    initial = [...channels.value]
    toastSuccess('已保存')
  } catch {} finally {
    saving.value = false
  }
}
</script>

<template>
  <n-spin :show="loading">
    <n-card title="预热频道" class="page-card">
      <n-space vertical size="large">
        <n-text depth="3" size="small">在下列频道中，机器人会定期主动预热生成，保持模型响应速度</n-text>
        <n-dynamic-tags v-model:value="channels" />
        <n-button type="primary" :disabled="!dirty" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </n-card>
  </n-spin>
</template>
