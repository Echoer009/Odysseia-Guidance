<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NEllipsis,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  type DataTableColumns,
  type SelectOption,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'
import type { BlacklistEntry } from '../types'
import { formatDateTime } from '../utils'

type MutedRow = {
  channel_id: string | number | null
  muted_at?: string | null
  muted_until?: string | null
}

const loadingBlacklist = ref(true)
const loadingMuted = ref(true)
const blacklist = ref<BlacklistEntry[]>([])
const muted = ref<MutedRow[]>([])
const addingBlacklist = ref(false)
const addingMuted = ref(false)

const addForm = reactive({
  scope: 'global' as string | null,
  user_id: '',
  guild_id: '',
  reason: '',
})
const mutedForm = reactive({ channel_id: '', duration_minutes: 60 as number | null })

const scopeOptions: SelectOption[] = [
  { label: '全局', value: 'global' },
  { label: '服务器', value: 'guild' },
]

function scopeLabel(scope: unknown): string {
  return String(scope ?? 'global') === 'guild' ? '服务器' : '全局'
}

function scopeRaw(scope: unknown): string {
  return String(scope ?? 'global') === 'guild' ? 'guild' : 'global'
}

function isGuildScope(scope: unknown): boolean {
  return scopeRaw(scope) === 'guild'
}

async function loadBlacklist(): Promise<void> {
  loadingBlacklist.value = true
  try {
    const data = await api.get<unknown>('moderation/blacklist')
    const rows: BlacklistEntry[] = []
    if (data != null && typeof data === 'object') {
      const record = data as Record<string, unknown>
      const guild = Array.isArray(record.guild) ? record.guild : []
      const global = Array.isArray(record.global) ? record.global : []
      for (const row of guild) {
        if (row != null && typeof row === 'object') rows.push({ ...(row as BlacklistEntry), scope: 'guild' })
      }
      for (const row of global) {
        if (row != null && typeof row === 'object') rows.push({ ...(row as BlacklistEntry), scope: 'global' })
      }
    } else if (Array.isArray(data)) {
      rows.push(...data)
    }
    blacklist.value = rows
  } catch {
  } finally {
    loadingBlacklist.value = false
  }
}

async function loadMuted(): Promise<void> {
  loadingMuted.value = true
  try {
    const data = await api.get<unknown>('moderation/muted')
    const raw = Array.isArray(data)
      ? data
      : data != null && typeof data === 'object' && Array.isArray((data as { items?: unknown[] }).items)
        ? (data as { items: unknown[] }).items
        : []
    muted.value = raw
      .map((row): MutedRow => {
        if (typeof row === 'string') return { channel_id: row }
        if (row != null && typeof row === 'object') {
          const record = row as Record<string, unknown>
          return {
            channel_id: (record.channel_id ?? null) as string | number | null,
            muted_at: (record.muted_at ?? null) as string | null,
            muted_until: (record.muted_until ?? null) as string | null,
          }
        }
        return { channel_id: null }
      })
      .filter((row) => row.channel_id != null)
  } catch {
  } finally {
    loadingMuted.value = false
  }
}

async function addBlacklist(): Promise<void> {
  const scope = scopeRaw(addForm.scope)
  if (addForm.user_id.trim().length === 0) {
    toastError('请填写用户 ID')
    return
  }
  if (scope === 'guild' && addForm.guild_id.trim().length === 0) {
    toastError('服务器范围需要填写服务器 ID')
    return
  }
  addingBlacklist.value = true
  try {
    const body: Record<string, unknown> = {
      scope,
      user_id: addForm.user_id.trim(),
      reason: addForm.reason.trim(),
    }
    if (scope === 'guild') body.guild_id = addForm.guild_id.trim()
    await api.post('moderation/blacklist', body)
    toastSuccess('已加入黑名单')
    addForm.user_id = ''
    addForm.guild_id = ''
    addForm.reason = ''
    await loadBlacklist()
  } catch {
  } finally {
    addingBlacklist.value = false
  }
}

async function unban(row: BlacklistEntry): Promise<void> {
  const userId = row.user_id
  if (userId == null || String(userId).length === 0) {
    toastError('缺少用户 ID，无法解封')
    return
  }
  const params = new URLSearchParams()
  params.set('scope', scopeRaw(row.scope))
  const guildId = row.guild_id
  if (isGuildScope(row.scope) && guildId != null && String(guildId).length > 0) params.set('guild_id', String(guildId))
  try {
    await api.delete(`moderation/blacklist/${encodeURIComponent(String(userId))}?${params.toString()}`)
    toastSuccess('已解封')
    await loadBlacklist()
  } catch {
  }
}

async function addMuted(): Promise<void> {
  if (mutedForm.channel_id.trim().length === 0) {
    toastError('请填写频道 ID')
    return
  }
  addingMuted.value = true
  try {
    const body: Record<string, unknown> = { channel_id: mutedForm.channel_id.trim() }
    if (mutedForm.duration_minutes != null) body.duration_minutes = mutedForm.duration_minutes
    await api.post('moderation/muted', body)
    toastSuccess('已添加静音频道')
    mutedForm.channel_id = ''
    await loadMuted()
  } catch {
  } finally {
    addingMuted.value = false
  }
}

async function removeMuted(row: MutedRow): Promise<void> {
  if (row.channel_id == null) return
  try {
    await api.delete(`moderation/muted/${encodeURIComponent(String(row.channel_id))}`)
    toastSuccess('已移除')
    await loadMuted()
  } catch {
  }
}

const blacklistColumns: DataTableColumns<BlacklistEntry> = [
  {
    title: '范围',
    key: 'scope',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { type: isGuildScope(row.scope) ? 'warning' : 'error', size: 'small', bordered: false },
        { default: () => scopeLabel(row.scope) },
      ),
  },
  { title: '用户 ID', key: 'user_id', width: 190, render: (row) => String(row.user_id ?? '—') },
  {
    title: '服务器 ID',
    key: 'guild_id',
    width: 190,
    render: (row) => (row.guild_id == null || String(row.guild_id).length === 0 ? '—' : String(row.guild_id)),
  },
  {
    title: '原因',
    key: 'reason',
    render: (row) =>
      h(
        NEllipsis,
        { style: 'max-width: 240px' },
        { default: () => (row.reason == null || String(row.reason).length === 0 ? '—' : String(row.reason)) },
      ),
  },
  {
    title: '到期时间',
    key: 'expires_at',
    width: 170,
    render: (row) => {
      const value = row.expires_at ?? row.created_at
      return value == null ? '—' : formatDateTime(value)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row) =>
      h(
        NPopconfirm,
        { onPositiveClick: () => void unban(row) },
        {
          default: () => `确认解封 ${String(row.user_id ?? '')}？`,
          trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '解封' }),
        },
      ),
  },
]

const mutedColumns: DataTableColumns<MutedRow> = [
  { title: '频道 ID', key: 'channel_id', width: 200, render: (row) => String(row.channel_id ?? '—') },
  { title: '禁言时间', key: 'muted_at', width: 170, render: (row) => (row.muted_at == null ? '—' : formatDateTime(row.muted_at)) },
  {
    title: '到期时间',
    key: 'muted_until',
    width: 170,
    render: (row) => (row.muted_until == null ? '—' : formatDateTime(row.muted_until)),
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row) =>
      h(
        NPopconfirm,
        { onPositiveClick: () => void removeMuted(row) },
        {
          default: () => '确认移除该频道？',
          trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '移除' }),
        },
      ),
  },
]

onMounted(() => {
  void loadBlacklist()
  void loadMuted()
})
</script>

<template>
  <n-grid :x-gap="16" :y-gap="16" :cols="1" m="2" responsive="screen">
    <n-grid-item>
      <n-space vertical :size="16">
        <n-card title="黑名单" size="small">
          <n-data-table
            :columns="blacklistColumns"
            :data="blacklist"
            :loading="loadingBlacklist"
            :row-key="(row: BlacklistEntry) => `${scopeRaw(row.scope)}-${String(row.user_id ?? '')}-${String(row.guild_id ?? '')}`"
            size="small"
          />
        </n-card>
        <n-card title="添加黑名单" size="small">
          <n-form label-placement="left" label-width="90">
            <n-form-item label="范围">
              <n-select v-model:value="addForm.scope" :options="scopeOptions" style="width: 160px" />
            </n-form-item>
            <n-form-item label="用户 ID">
              <n-input v-model:value="addForm.user_id" placeholder="user_id" style="width: 280px" />
            </n-form-item>
            <n-form-item v-if="isGuildScope(addForm.scope)" label="服务器 ID">
              <n-input v-model:value="addForm.guild_id" placeholder="guild_id" style="width: 280px" />
            </n-form-item>
            <n-form-item label="原因">
              <n-input v-model:value="addForm.reason" placeholder="封禁原因（可选）" style="width: 320px" />
            </n-form-item>
          </n-form>
          <template #footer>
            <n-space justify="end">
              <n-button type="primary" :loading="addingBlacklist" @click="addBlacklist">添加</n-button>
            </n-space>
          </template>
        </n-card>
      </n-space>
    </n-grid-item>
    <n-grid-item>
      <n-space vertical :size="16">
        <n-card title="静音频道" size="small">
          <n-data-table
            :columns="mutedColumns"
            :data="muted"
            :loading="loadingMuted"
            :row-key="(row: MutedRow) => String(row.channel_id ?? '')"
            size="small"
          />
        </n-card>
        <n-card title="添加静音频道" size="small">
          <n-form label-placement="left" label-width="110">
            <n-form-item label="频道 ID">
              <n-input v-model:value="mutedForm.channel_id" placeholder="channel_id" style="width: 280px" />
            </n-form-item>
            <n-form-item label="时长（分钟）">
              <n-input-number v-model:value="mutedForm.duration_minutes" :min="1" :precision="0" style="width: 180px" />
            </n-form-item>
          </n-form>
          <template #footer>
            <n-space justify="end">
              <n-button type="primary" :loading="addingMuted" @click="addMuted">添加</n-button>
            </n-space>
          </template>
        </n-card>
      </n-space>
    </n-grid-item>
  </n-grid>
</template>
