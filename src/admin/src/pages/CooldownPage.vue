<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSpace,
  NSwitch,
  NTag,
  type DataTableColumns,
} from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { CooldownChannel } from '../types'

const loading = ref(true)
const saving = ref(false)
const rows = ref<CooldownChannel[]>([])
const showModal = ref(false)
const isCreate = ref(false)

const form = reactive({
  guild_id: '',
  entity_id: '',
  chat_enabled: true,
  fixed_cooldown: 0 as number | null,
  frequency_cooldown: 0 as number | null,
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<CooldownChannel[] | null>('cooldown/channels')
    rows.value = Array.isArray(data) ? data : []
  } catch {} finally {
    loading.value = false
  }
}

function openCreate(): void {
  isCreate.value = true
  form.guild_id = ''
  form.entity_id = ''
  form.chat_enabled = true
  form.fixed_cooldown = 0
  form.frequency_cooldown = 0
  showModal.value = true
}

function openEdit(row: CooldownChannel): void {
  isCreate.value = false
  form.guild_id = String(row.guild_id ?? '')
  form.entity_id = String(row.entity_id ?? '')
  form.chat_enabled = !!row.chat_enabled
  form.fixed_cooldown = row.fixed_cooldown ?? 0
  form.frequency_cooldown = row.frequency_cooldown ?? 0
  showModal.value = true
}

async function save(): Promise<void> {
  if (form.guild_id.trim().length === 0 || form.entity_id.trim().length === 0) {
    showModal.value = false
    return
  }
  saving.value = true
  try {
    await api.put('cooldown/channels', {
      guild_id: form.guild_id.trim(),
      entity_id: form.entity_id.trim(),
      chat_enabled: form.chat_enabled,
      fixed_cooldown: form.fixed_cooldown ?? 0,
      frequency_cooldown: form.frequency_cooldown ?? 0,
    })
    showModal.value = false
    toastSuccess('已保存')
    await load()
  } catch {} finally {
    saving.value = false
  }
}

const columns: DataTableColumns<CooldownChannel> = [
  { title: '服务器 ID', key: 'guild_id', width: 160 },
  { title: '频道 ID', key: 'entity_id', width: 160 },
  {
    title: '频道聊天',
    key: 'chat_enabled',
    width: 110,
    render: (row) =>
      h(
        NTag,
        { type: row.chat_enabled ? 'success' : 'default', size: 'small', bordered: false },
        { default: () => (row.chat_enabled ? '开启' : '关闭') },
      ),
  },
  {
    title: '固定冷却（秒）',
    key: 'fixed_cooldown',
    width: 140,
    render: (row) => String(row.fixed_cooldown ?? 0),
  },
  {
    title: '频率冷却（秒）',
    key: 'frequency_cooldown',
    width: 140,
    render: (row) => String(row.frequency_cooldown ?? 0),
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
  },
]

onMounted(() => void load())
</script>

<template>
  <n-card title="频道冷却" class="page-card">
    <template #header-extra>
      <n-button type="primary" size="small" @click="openCreate">新增频道配置</n-button>
    </template>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :row-key="(row: CooldownChannel) => `${row.guild_id}-${row.entity_id}`" size="small" />
    <n-modal v-model:show="showModal" preset="card" :title="isCreate ? '新增频道配置' : '编辑频道配置'" style="width: 480px">
      <n-form label-placement="left" label-width="120">
        <n-form-item label="服务器 ID">
          <n-input v-model:value="form.guild_id" :disabled="!isCreate" placeholder="guild_id" />
        </n-form-item>
        <n-form-item label="频道 ID">
          <n-input v-model:value="form.entity_id" :disabled="!isCreate" placeholder="entity_id" />
        </n-form-item>
        <n-form-item label="频道聊天">
          <n-switch v-model:value="form.chat_enabled" />
        </n-form-item>
        <n-form-item label="固定冷却（秒）">
          <n-input-number v-model:value="form.fixed_cooldown" :min="0" :max="86400" style="width: 200px" />
        </n-form-item>
        <n-form-item label="频率冷却（秒）">
          <n-input-number v-model:value="form.frequency_cooldown" :min="0" :max="86400" style="width: 200px" />
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
