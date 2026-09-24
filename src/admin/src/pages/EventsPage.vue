<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NEllipsis,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NText,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'
import type {
  EventInfo,
  EventSettlement,
  EventStats,
  FactionSummary,
  LeaderboardRow,
} from '../types'
import { formatDateTime, prettyJson } from '../utils'

const loading = ref(true)
const events = ref<EventInfo[]>([])

// --- 通用取值 ---
function nameOf(event: EventInfo | null): string {
  if (event == null) return ''
  const name = event.event_name ?? event.name
  return name == null || String(name).length === 0 ? `#${String(event.id)}` : String(name)
}

function startOf(event: EventInfo): string | null {
  return event.start_date ?? event.start_at ?? event.start ?? null
}

function endOf(event: EventInfo): string | null {
  return event.end_date ?? event.end_at ?? event.end ?? null
}

function emojiOf(event: EventInfo): string {
  const emoji = event.theme?.emoji
  return emoji == null || String(emoji).length === 0 ? '' : `${String(emoji)} `
}

function enabledOf(event: EventInfo): boolean {
  return event.enabled ?? event.is_active ?? false
}

function statusOf(event: EventInfo): { label: string; type: 'success' | 'info' | 'warning' | 'default' } {
  const now = Date.now()
  const start = startOf(event) == null ? null : Date.parse(String(startOf(event)))
  const end = endOf(event) == null ? null : Date.parse(String(endOf(event)))
  if (start != null && !Number.isNaN(start) && now < start) return { label: '未开始', type: 'info' }
  if (end != null && !Number.isNaN(end) && now >= end) return { label: '已结束', type: 'default' }
  if (event.is_active) return { label: '进行中', type: 'success' }
  return { label: '未启用', type: 'warning' }
}

function filesOf(event: EventInfo | null): string[] {
  if (event == null) return []
  const raw: unknown = event.files
  if (Array.isArray(raw)) {
    return raw.map((item) => (typeof item === 'string' ? item : String((item as Record<string, unknown>)?.name ?? '')))
      .filter((name) => name.length > 0)
  }
  return typeof raw === 'string' && raw.length > 0 ? [raw] : []
}

function fileUrl(eventId: string | number, name: string): string {
  const encoded = name.split('/').map(encodeURIComponent).join('/')
  return `events/${encodeURIComponent(String(eventId))}/file/${encoded}`
}

function tsToIso(ts: number | null): string | null {
  return ts == null ? null : new Date(ts).toISOString()
}

function isoToTs(iso: unknown): number | null {
  if (iso == null) return null
  const ts = Date.parse(String(iso))
  return Number.isNaN(ts) ? null : ts
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<unknown>('events')
    const raw = Array.isArray(data) ? data : []
    events.value = raw.filter((item): item is EventInfo => item != null && typeof item === 'object')
  } catch {
  } finally {
    loading.value = false
  }
}

// --- 启用/停用 ---
const togglingId = ref('')

async function toggleActive(event: EventInfo, value: boolean): Promise<void> {
  togglingId.value = String(event.id)
  try {
    await api.patch(`events/${encodeURIComponent(String(event.id))}/manifest`, { is_active: value })
    toastSuccess(value ? '活动已启用' : '活动已停用')
    await load()
  } catch {
  } finally {
    togglingId.value = ''
  }
}

// --- 重载 ---
const reloadingId = ref('')

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

// --- 创建活动 ---
const showCreate = ref(false)
const creating = ref(false)

const createForm = reactive({
  event_id: '',
  event_name: '',
  start: null as number | null,
  end: null as number | null,
  description: '',
  theme_emoji: '',
  theme_color: '',
  theme_footer: '',
  theme_empty: '',
})

function openCreate(): void {
  createForm.event_id = ''
  createForm.event_name = ''
  createForm.start = null
  createForm.end = null
  createForm.description = ''
  createForm.theme_emoji = ''
  createForm.theme_color = ''
  createForm.theme_footer = ''
  createForm.theme_empty = ''
  showCreate.value = true
}

function buildTheme(form: { theme_emoji: string; theme_color: string; theme_footer: string; theme_empty: string }): Record<string, string> | undefined {
  const theme: Record<string, string> = {}
  if (form.theme_emoji.trim().length > 0) theme.emoji = form.theme_emoji.trim()
  if (form.theme_color.trim().length > 0) theme.color = form.theme_color.trim()
  if (form.theme_footer.trim().length > 0) theme.footer = form.theme_footer.trim()
  if (form.theme_empty.trim().length > 0) theme.empty_leaderboard_text = form.theme_empty.trim()
  return Object.keys(theme).length > 0 ? theme : undefined
}

async function submitCreate(): Promise<void> {
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(createForm.event_id.trim())) {
    toastError('目录名仅允许小写字母、数字、下划线和连字符')
    return
  }
  if (createForm.event_name.trim().length === 0) {
    toastError('请填写活动名称')
    return
  }
  if (createForm.start == null || createForm.end == null) {
    toastError('请填写起止时间')
    return
  }
  if (createForm.end <= createForm.start) {
    toastError('结束时间必须晚于开始时间')
    return
  }
  creating.value = true
  try {
    const body: Record<string, unknown> = {
      event_id: createForm.event_id.trim(),
      event_name: createForm.event_name.trim(),
      start_date: tsToIso(createForm.start),
      end_date: tsToIso(createForm.end),
      description: createForm.description,
    }
    const theme = buildTheme(createForm)
    if (theme != null) body.theme = theme
    await api.post('events', body)
    toastSuccess('活动已创建')
    showCreate.value = false
    await load()
  } catch {
  } finally {
    creating.value = false
  }
}

// --- 编辑 manifest ---
const showEdit = ref(false)
const savingManifest = ref(false)
const editTarget = ref<EventInfo | null>(null)

const editForm = reactive({
  event_name: '',
  start: null as number | null,
  end: null as number | null,
  description: '',
  announcement_channel_id: null as number | null,
  theme_emoji: '',
  theme_color: '',
  theme_footer: '',
  theme_empty: '',
})

function toNumberOrNull(value: unknown): number | null {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function openEdit(event: EventInfo): void {
  editTarget.value = event
  editForm.event_name = nameOf(event) === `#${String(event.id)}` ? '' : nameOf(event)
  editForm.start = isoToTs(startOf(event))
  editForm.end = isoToTs(endOf(event))
  editForm.description = event.description == null ? '' : String(event.description)
  editForm.announcement_channel_id = toNumberOrNull(event.announcement_channel_id)
  editForm.theme_emoji = event.theme?.emoji == null ? '' : String(event.theme.emoji)
  editForm.theme_color = event.theme?.color == null ? '' : String(event.theme.color)
  editForm.theme_footer = event.theme?.footer == null ? '' : String(event.theme.footer)
  editForm.theme_empty = event.theme?.empty_leaderboard_text == null ? '' : String(event.theme.empty_leaderboard_text)
  showEdit.value = true
}

async function saveManifest(): Promise<void> {
  const event = editTarget.value
  if (event == null) return
  if (editForm.event_name.trim().length === 0) {
    toastError('活动名称不能为空')
    return
  }
  if (editForm.start == null || editForm.end == null) {
    toastError('请填写起止时间')
    return
  }
  if (editForm.end <= editForm.start) {
    toastError('结束时间必须晚于开始时间')
    return
  }
  savingManifest.value = true
  try {
    const body: Record<string, unknown> = {
      event_name: editForm.event_name.trim(),
      start_date: tsToIso(editForm.start),
      end_date: tsToIso(editForm.end),
      description: editForm.description,
      announcement_channel_id: editForm.announcement_channel_id,
    }
    const theme = buildTheme(editForm)
    if (theme != null) body.theme = theme
    await api.patch(`events/${encodeURIComponent(String(event.id))}/manifest`, body)
    toastSuccess('manifest 已保存，bot 30 秒内生效')
    showEdit.value = false
    await load()
  } catch {
  } finally {
    savingManifest.value = false
  }
}

// --- 文件编辑器 ---
const showDrawer = ref(false)
const drawerEvent = ref<EventInfo | null>(null)
const selectedFile = ref<string | null>(null)
const fileContent = ref('')
const fileLoading = ref(false)
const fileSaving = ref(false)

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
      const data = await api.get<unknown>(fileUrl(event.id, name))
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
    await api.put(fileUrl(event.id, name), { content: fileContent.value })
    toastSuccess('文件已保存')
    await load()
  } catch {
  } finally {
    fileSaving.value = false
  }
}

// --- 派系选择 ---
const showFactions = ref(false)
const factionsEvent = ref<EventInfo | null>(null)
const factions = ref<FactionSummary[]>([])
const factionsLoading = ref(false)
const selectingFactionId = ref('')

async function openFactions(event: EventInfo): Promise<void> {
  factionsEvent.value = event
  factions.value = []
  showFactions.value = true
  factionsLoading.value = true
  try {
    const data = await api.get<unknown>(`events/${encodeURIComponent(String(event.id))}/factions-summary`)
    factions.value = Array.isArray(data) ? (data as FactionSummary[]) : []
  } catch {
  } finally {
    factionsLoading.value = false
  }
}

async function pickFaction(faction: FactionSummary): Promise<void> {
  const event = factionsEvent.value
  if (event == null) return
  selectingFactionId.value = String(faction.id)
  try {
    await api.post('events/select-faction', {
      event_id: event.id,
      faction_id: faction.id,
    })
    toastSuccess('已提交，bot 30 秒内生效')
    await openFactions(event)
  } catch {
  } finally {
    selectingFactionId.value = ''
  }
}

// --- 排行榜与结算 ---
const showBoard = ref(false)
const boardEvent = ref<EventInfo | null>(null)
const boardRows = ref<LeaderboardRow[]>([])
const settlement = ref<EventSettlement | null>(null)
const stats = ref<EventStats | null>(null)
const boardLoading = ref(false)
const settling = ref(false)

async function openBoard(event: EventInfo): Promise<void> {
  boardEvent.value = event
  boardRows.value = []
  settlement.value = null
  stats.value = null
  showBoard.value = true
  await refreshBoard()
}

async function refreshBoard(): Promise<void> {
  const event = boardEvent.value
  if (event == null) return
  boardLoading.value = true
  try {
    const base = `events/${encodeURIComponent(String(event.id))}`
    const [board, settle, stat] = await Promise.all([
      api.get<unknown>(`${base}/leaderboard`),
      api.get<unknown>(`${base}/settlement`),
      api.get<unknown>(`${base}/stats`),
    ])
    boardRows.value = Array.isArray(board) ? (board as LeaderboardRow[]) : []
    settlement.value = settle == null || typeof settle !== 'object' ? null : settle as EventSettlement
    stats.value = stat == null || typeof stat !== 'object' ? null : stat as EventStats
  } catch {
  } finally {
    boardLoading.value = false
  }
}

function settlementName(): string {
  const s = settlement.value
  if (s == null) return ''
  const row = boardRows.value.find((r) => r.faction_id === s.winning_faction)
  return row?.faction_name ?? s.winning_faction
}

async function settleNow(): Promise<void> {
  const event = boardEvent.value
  if (event == null) return
  settling.value = true
  try {
    const data = await api.post<{ faction_name?: string | null; winning_faction?: string } | null>(
      `events/${encodeURIComponent(String(event.id))}/settle`,
    )
    const winner = data?.faction_name ?? data?.winning_faction ?? ''
    toastSuccess(`结算完成，获胜派系：${winner}`)
    await refreshBoard()
  } catch {
  } finally {
    settling.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-space justify="space-between" align="center">
        <n-text depth="3" size="small">共 {{ events.length }} 个活动</n-text>
        <n-button type="primary" size="small" @click="openCreate">创建活动</n-button>
      </n-space>
      <n-grid v-if="events.length > 0" :x-gap="16" :y-gap="16" :cols="1" m="2" l="3" responsive="screen">
        <n-grid-item v-for="event in events" :key="String(event.id)">
          <n-card :title="`${emojiOf(event)}${nameOf(event)}`" size="small">
            <template #header-extra>
              <n-space align="center" :size="10">
                <n-tag :type="statusOf(event).type" size="small" :bordered="false">
                  {{ statusOf(event).label }}
                </n-tag>
                <n-switch
                  :value="enabledOf(event)"
                  :loading="togglingId === String(event.id)"
                  size="small"
                  @update:value="(v: boolean) => toggleActive(event, v)"
                />
              </n-space>
            </template>
            <n-space vertical :size="8">
              <n-text depth="2" size="small">ID：{{ String(event.id) }}</n-text>
              <n-text depth="2" size="small">开始：{{ formatDateTime(startOf(event)) }}</n-text>
              <n-text depth="2" size="small">结束：{{ formatDateTime(endOf(event)) }}</n-text>
              <n-ellipsis v-if="event.description != null && String(event.description).length > 0" :line-clamp="2" :tooltip="false">
                <n-text depth="3" size="small">{{ String(event.description) }}</n-text>
              </n-ellipsis>
              <n-text v-if="event.note != null && String(event.note).length > 0" type="warning" size="small">
                {{ String(event.note) }}
              </n-text>
              <n-space v-if="filesOf(event).length > 0" :size="6">
                <n-tag v-for="name in filesOf(event)" :key="name" size="small" :bordered="false">{{ name }}</n-tag>
              </n-space>
              <n-space :size="8">
                <n-button size="small" @click="openEdit(event)">编辑配置</n-button>
                <n-button size="small" @click="openFiles(event)">文件管理</n-button>
                <n-button size="small" @click="openFactions(event)">派系选择</n-button>
                <n-button size="small" @click="openBoard(event)">排行榜</n-button>
                <n-button size="small" :loading="reloadingId === String(event.id)" @click="reloadEvent(event)">重载</n-button>
              </n-space>
            </n-space>
          </n-card>
        </n-grid-item>
      </n-grid>
      <n-text v-else-if="!loading" depth="3">暂无活动</n-text>
    </n-space>
  </n-spin>

  <n-modal v-model:show="showCreate" preset="card" title="创建活动" style="width: 680px">
    <n-form label-placement="top">
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item label="目录名（event_id）" required>
            <n-input v-model:value="createForm.event_id" placeholder="如 spring_festival_2027" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="活动名称" required>
            <n-input v-model:value="createForm.event_name" placeholder="如 新春庙会" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item label="开始时间" required>
            <n-date-picker v-model:value="createForm.start" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="结束时间" required>
            <n-date-picker v-model:value="createForm.end" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item label="描述">
        <n-input v-model:value="createForm.description" type="textarea" :rows="3" placeholder="活动描述（可选）" />
      </n-form-item>
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item label="主题 emoji">
            <n-input v-model:value="createForm.theme_emoji" placeholder="如 🎃（可选）" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="主题颜色">
            <n-input v-model:value="createForm.theme_color" placeholder="如 #f97316（可选）" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item label="页脚文案">
        <n-input v-model:value="createForm.theme_footer" placeholder="排行榜页脚（可选）" />
      </n-form-item>
      <n-form-item label="空排行榜文案">
        <n-input v-model:value="createForm.theme_empty" placeholder="排行榜为空时显示（可选）" />
      </n-form-item>
    </n-form>
    <n-space vertical :size="4">
      <n-text depth="3" size="small">创建后自动生成 manifest.json / factions.json / items.json / prompts.json 骨架，默认停用状态</n-text>
      <n-space justify="end">
        <n-button @click="showCreate = false">取消</n-button>
        <n-button type="primary" :loading="creating" @click="submitCreate">创建</n-button>
      </n-space>
    </n-space>
  </n-modal>

  <n-modal v-model:show="showEdit" preset="card" :title="editTarget == null ? '编辑配置' : `编辑配置 · ${nameOf(editTarget)}`" style="width: 680px">
    <n-form label-placement="top">
      <n-form-item label="活动名称" required>
        <n-input v-model:value="editForm.event_name" />
      </n-form-item>
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item label="开始时间" required>
            <n-date-picker v-model:value="editForm.start" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="结束时间" required>
            <n-date-picker v-model:value="editForm.end" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item label="描述">
        <n-input v-model:value="editForm.description" type="textarea" :rows="3" />
      </n-form-item>
      <n-form-item label="公告频道 ID">
        <n-input-number v-model:value="editForm.announcement_channel_id" :precision="0" style="width: 100%" placeholder="结算公告发送到的频道（可选）" />
      </n-form-item>
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item label="主题 emoji">
            <n-input v-model:value="editForm.theme_emoji" placeholder="如 🎃" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="主题颜色">
            <n-input v-model:value="editForm.theme_color" placeholder="如 #f97316" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item label="页脚文案">
        <n-input v-model:value="editForm.theme_footer" />
      </n-form-item>
      <n-form-item label="空排行榜文案">
        <n-input v-model:value="editForm.theme_empty" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showEdit = false">取消</n-button>
        <n-button type="primary" :loading="savingManifest" @click="saveManifest">保存</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal v-model:show="showFactions" preset="card" :title="factionsEvent == null ? '派系选择' : `派系选择 · ${nameOf(factionsEvent)}`" style="width: 640px">
    <n-spin :show="factionsLoading">
      <n-space v-if="factions.length > 0" :size="10" item-style="display: flex">
        <n-button
          v-for="faction in factions"
          :key="String(faction.id)"
          :type="faction.selected ? 'primary' : 'default'"
          :loading="selectingFactionId === String(faction.id)"
          @click="pickFaction(faction)"
        >
          {{ faction.icon == null || String(faction.icon).length === 0 ? '' : `${String(faction.icon)} ` }}{{ faction.name ?? faction.id }}{{ faction.selected ? ' · 当前' : '' }}
        </n-button>
      </n-space>
      <n-text v-else depth="3">暂无派系配置（factions.json 为空或缺失）</n-text>
    </n-spin>
    <template #footer>
      <n-space justify="space-between" align="center">
        <n-text depth="3" size="small">点击派系即可切换，bot 30 秒内生效</n-text>
        <n-button @click="showFactions = false">关闭</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal v-model:show="showBoard" preset="card" :title="boardEvent == null ? '排行榜' : `排行榜 · ${nameOf(boardEvent)}`" style="width: 640px">
    <n-spin :show="boardLoading">
      <n-space vertical :size="16">
        <n-text v-if="stats != null" depth="3" size="small">
          参与人数 {{ stats.participants }} · 总贡献 {{ stats.total_points }} · 贡献记录 {{ stats.entries }} 条
        </n-text>
        <n-space v-if="boardRows.length > 0" vertical :size="10">
          <n-space v-for="(row, index) in boardRows" :key="row.faction_id" justify="space-between" align="center">
            <n-space :size="8" align="center">
              <n-tag size="small" :type="index === 0 ? 'success' : 'default'" :bordered="false">#{{ index + 1 }}</n-tag>
              <n-text>{{ row.icon == null || String(row.icon).length === 0 ? '' : `${String(row.icon)} ` }}{{ row.faction_name ?? row.faction_id }}</n-text>
            </n-space>
            <n-text depth="2">{{ row.total_points }} 分</n-text>
          </n-space>
        </n-space>
        <n-text v-else depth="3">排行榜暂无数据</n-text>
        <n-alert v-if="settlement != null" type="success" :bordered="false">
          已结算 · 获胜派系：{{ settlementName() }}（{{ settlement.total_points }} 分） ·
          结算时间：{{ formatDateTime(settlement.settled_at) }}
        </n-alert>
        <n-space v-else vertical :size="8">
          <n-text depth="3" size="small">尚无结算记录，结算将以排行榜第一名作为获胜派系</n-text>
          <n-popconfirm @positive-click="settleNow">
            <template #trigger>
              <n-button type="primary" :loading="settling" :disabled="boardRows.length === 0">立即结算</n-button>
            </template>
            确定结算吗？该操作不可撤销
          </n-popconfirm>
        </n-space>
      </n-space>
    </n-spin>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showBoard = false">关闭</n-button>
        <n-button :loading="boardLoading" @click="refreshBoard">刷新</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-drawer v-model:show="showDrawer" :width="680">
    <n-drawer-content :title="drawerEvent == null ? '文件管理' : `文件管理 · ${nameOf(drawerEvent)}`" closable>
      <n-space vertical :size="12">
        <n-select
          v-model:value="selectedFile"
          :options="filesOf(drawerEvent).map((name) => ({ label: name, value: name }))"
          placeholder="选择文件"
        />
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
