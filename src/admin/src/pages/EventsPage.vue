<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NText,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'
import type { EventInfo } from '../types'
import { formatDateTime, prettyJson } from '../utils'

const loading = ref(true)
const events = ref<EventInfo[]>([])

const showDrawer = ref(false)
const drawerEvent = ref<EventInfo | null>(null)
const selectedFile = ref<string | null>(null)
const fileContent = ref('')
const fileLoading = ref(false)
const fileSaving = ref(false)

const selecting = ref(false)
const reloadingId = ref('')
const factionForm = reactive({ event_id: null as string | number | null, faction_id: '' })

function nameOf(event: EventInfo): string {
  const name = (event as Record<string, unknown>).event_name ?? event.name
  return name == null || String(name).length === 0 ? `#${String(event.id)}` : String(name)
}

function startOf(event: EventInfo): unknown {
  const record = event as Record<string, unknown>
  return record.start_date ?? record.start_at ?? record.start ?? null
}

function endOf(event: EventInfo): unknown {
  const record = event as Record<string, unknown>
  return record.end_date ?? record.end_at ?? record.end ?? null
}

function noteOf(event: EventInfo): string {
  const note = (event as Record<string, unknown>).note
  return note == null ? '' : String(note)
}

function filesOf(event: EventInfo | null): string[] {
  if (event == null) return []
  const raw: unknown = event.files
  if (Array.isArray(raw)) {
    return raw
      .map((item) => {
        if (typeof item === 'string') return item
        if (item != null && typeof item === 'object') {
          const name = (item as Record<string, unknown>).name
          return name == null ? '' : String(name)
        }
        return item == null ? '' : String(item)
      })
      .filter((name) => name.length > 0)
  }
  return typeof raw === 'string' && raw.length > 0 ? [raw] : []
}

const eventOptions = computed(() =>
  events.value.map((event) => ({ label: `${nameOf(event)}（${String(event.id)}）`, value: event.id })),
)

const fileOptions = computed(() => filesOf(drawerEvent.value).map((name) => ({ label: name, value: name })))

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<unknown>('events')
    const raw = Array.isArray(data)
      ? data
      : data != null && typeof data === 'object' && Array.isArray((data as { items?: unknown[] }).items)
        ? (data as { items: unknown[] }).items
        : []
    events.value = raw.filter((item): item is EventInfo => item != null && typeof item === 'object')
  } catch {
  } finally {
    loading.value = false
  }
}

function openFiles(event: EventInfo): void {
  drawerEvent.value = event
  selectedFile.value = null
  fileContent.value = ''
  showDrawer.value = true
}

watch(selectedFile, (name) => {
  const event = drawerEvent.value
  if (name == null || name.length === 0 || event == null) {
    fileContent.value = ''
    return
  }
  void (async () => {
    fileLoading.value = true
    try {
      const data = await api.get<unknown>(
        `events/${encodeURIComponent(String(event.id))}/file/${encodeURIComponent(name)}`,
      )
      if (typeof data === 'string') fileContent.value = data
      else if (data != null && typeof data === 'object' && typeof (data as Record<string, unknown>).content === 'string') {
        fileContent.value = String((data as Record<string, unknown>).content)
      } else fileContent.value = data == null ? '' : prettyJson(data)
    } catch {
      fileContent.value = ''
    } finally {
      fileLoading.value = false
    }
  })()
})

async function saveFile(): Promise<void> {
  const event = drawerEvent.value
  const name = selectedFile.value
  if (event == null || name == null || name.length === 0) return
  if (name.toLowerCase().endsWith('.json')) {
    try {
      JSON.parse(fileContent.value)
    } catch (err) {
      toastError(`JSON 校验失败：${err instanceof Error ? err.message : '格式错误'}`)
      return
    }
  }
  fileSaving.value = true
  try {
    await api.put(`events/${encodeURIComponent(String(event.id))}/file/${encodeURIComponent(name)}`, {
      content: fileContent.value,
    })
    toastSuccess('文件已保存')
  } catch {
  } finally {
    fileSaving.value = false
  }
}

async function reloadEvent(event: EventInfo): Promise<void> {
  reloadingId.value = String(event.id)
  try {
    await api.post(`events/${encodeURIComponent(String(event.id))}/reload`)
    toastSuccess('已触发重载')
  } catch {
  } finally {
    reloadingId.value = ''
  }
}

async function selectFaction(): Promise<void> {
  if (factionForm.event_id == null || factionForm.faction_id.trim().length === 0) {
    toastError('请选择活动并填写派系 ID')
    return
  }
  selecting.value = true
  try {
    await api.post('events/select-faction', {
      event_id: factionForm.event_id,
      faction_id: factionForm.faction_id.trim(),
    })
    toastSuccess('已提交，bot 30 秒内生效')
  } catch {
  } finally {
    selecting.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-grid v-if="events.length > 0" :x-gap="16" :y-gap="16" :cols="1" m="2" l="3" responsive="screen">
        <n-grid-item v-for="event in events" :key="String(event.id)">
          <n-card :title="`${String(event.id)} · ${nameOf(event)}`" size="small">
            <template #header-extra>
              <n-tag :type="event.is_active ? 'success' : 'default'" size="small" :bordered="false">
                {{ event.is_active ? '进行中' : '未激活' }}
              </n-tag>
            </template>
            <n-space vertical :size="8">
              <n-text depth="2" size="small">开始：{{ formatDateTime(startOf(event)) }}</n-text>
              <n-text depth="2" size="small">结束：{{ formatDateTime(endOf(event)) }}</n-text>
              <n-text v-if="noteOf(event).length > 0" type="warning" size="small">{{ noteOf(event) }}</n-text>
              <n-space v-if="filesOf(event).length > 0" :size="6">
                <n-tag v-for="name in filesOf(event)" :key="name" size="small" :bordered="false">{{ name }}</n-tag>
              </n-space>
              <n-space :size="8">
                <n-button size="small" @click="openFiles(event)">编辑文件</n-button>
                <n-button size="small" :loading="reloadingId === String(event.id)" @click="reloadEvent(event)">重载</n-button>
              </n-space>
            </n-space>
          </n-card>
        </n-grid-item>
      </n-grid>
      <n-text v-else-if="!loading" depth="3">暂无活动</n-text>
      <n-card title="选派系" size="small" style="max-width: 560px">
        <n-form label-placement="top">
          <n-form-item label="活动">
            <n-select v-model:value="factionForm.event_id" :options="eventOptions" placeholder="选择活动" />
          </n-form-item>
          <n-form-item label="派系 ID">
            <n-input v-model:value="factionForm.faction_id" placeholder="faction_id，如 factions.json 中的 faction_id" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space vertical :size="4" align="end">
            <n-text depth="3" size="small">bot 30 秒内生效</n-text>
            <n-button type="primary" :loading="selecting" @click="selectFaction">提交</n-button>
          </n-space>
        </template>
      </n-card>
    </n-space>
  </n-spin>

  <n-drawer v-model:show="showDrawer" :width="680">
    <n-drawer-content :title="drawerEvent == null ? '编辑文件' : `编辑文件 · ${nameOf(drawerEvent)}`" closable>
      <n-space vertical :size="12">
        <n-select v-model:value="selectedFile" :options="fileOptions" placeholder="选择文件" />
        <n-spin :show="fileLoading">
          <n-input
            v-model:value="fileContent"
            type="textarea"
            class="mono"
            :autosize="{ minRows: 16, maxRows: 28 }"
            placeholder="文件内容"
            style="width: 100%"
          />
        </n-spin>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDrawer = false">关闭</n-button>
          <n-button type="primary" :loading="fileSaving" :disabled="selectedFile == null" @click="saveFile">保存</n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>
