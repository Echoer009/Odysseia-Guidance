<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NDrawer,
  NDrawerContent,
  NEllipsis,
  NInput,
  NPopconfirm,
  NSpace,
  NSpin,
  NTag,
  NText,
} from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { PersonaData, PersonaItem } from '../types'

type GroupedItem = { item: PersonaItem; group: string }

const GROUP_ORDER = ['人设变体', '基础提示词', '身份信息', '功能文案']

const loading = ref(true)
const groupedItems = ref<GroupedItem[]>([])

const showDrawer = ref(false)
const currentItem = ref<PersonaItem | null>(null)
const editValue = ref('')
const saving = ref(false)

function mapGroup(item: PersonaItem, identity: boolean): string {
  if (identity) return '身份信息'
  const raw = String(item.group ?? '').trim()
  if (raw.length > 0 && GROUP_ORDER.includes(raw)) return raw
  const g = raw.toLowerCase()
  if (g.includes('variant') || g.includes('persona') || g.includes('人设')) return '人设变体'
  if (g.includes('base') || g.includes('system') || g.includes('prompt') || g.includes('基础') || g.includes('提示')) return '基础提示词'
  if (g.includes('identity') || g.includes('身份')) return '身份信息'
  return '功能文案'
}

const groups = computed(() => {
  const order: string[] = []
  const map = new Map<string, PersonaItem[]>()
  for (const entry of groupedItems.value) {
    if (!map.has(entry.group)) {
      map.set(entry.group, [])
      order.push(entry.group)
    }
    map.get(entry.group)?.push(entry.item)
  }
  const ordered = GROUP_ORDER.filter((g) => map.has(g))
  for (const g of order) {
    if (!ordered.includes(g)) ordered.push(g)
  }
  return ordered.map((g) => ({ group: g, items: map.get(g) ?? [] }))
})

function labelOf(item: PersonaItem): string {
  return item.label ?? item.key
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<PersonaData | PersonaItem[] | null>('persona')
    const rawTexts = Array.isArray(data) ? data : data?.texts
    const rawIdentity = Array.isArray(data) ? undefined : data?.identity
    const texts = Array.isArray(rawTexts) ? rawTexts : []
    const identity = Array.isArray(rawIdentity) ? rawIdentity : []
    groupedItems.value = [
      ...texts.map((item) => ({ item, group: mapGroup(item, false) })),
      ...identity.map((item) => ({ item, group: mapGroup(item, true) })),
    ]
  } catch {
  } finally {
    loading.value = false
  }
}

function openItem(item: PersonaItem): void {
  currentItem.value = item
  editValue.value = item.value ?? ''
  showDrawer.value = true
}

async function save(): Promise<void> {
  const item = currentItem.value
  if (item == null) return
  saving.value = true
  try {
    await api.put(`persona/${encodeURIComponent(item.key)}`, { value: editValue.value })
    toastSuccess('已保存')
    showDrawer.value = false
    await load()
  } catch {
  } finally {
    saving.value = false
  }
}

async function restoreDefault(): Promise<void> {
  const item = currentItem.value
  if (item == null) return
  saving.value = true
  try {
    await api.delete(`persona/${encodeURIComponent(item.key)}`)
    toastSuccess('已恢复默认')
    showDrawer.value = false
    await load()
  } catch {
  } finally {
    saving.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-card v-for="group in groups" :key="group.group" :title="group.group" size="small">
        <div class="persona-list">
          <div v-for="item in group.items" :key="item.key" class="persona-row" @click="openItem(item)">
            <div class="persona-row-main">
              <n-space align="center" :size="8">
                <span class="persona-label">{{ labelOf(item) }}</span>
                <n-tag v-if="item.overridden === true" type="warning" size="tiny" :bordered="false">已自定义</n-tag>
              </n-space>
              <n-ellipsis :line="1">
                {{ item.value == null || String(item.value).length === 0 ? '（空）' : String(item.value) }}
              </n-ellipsis>
            </div>
            <n-button size="tiny" text type="primary">编辑</n-button>
          </div>
        </div>
      </n-card>
      <n-text v-if="groups.length === 0 && !loading" depth="3">暂无数据</n-text>
    </n-space>
  </n-spin>

  <n-drawer v-model:show="showDrawer" :width="720">
    <n-drawer-content :title="currentItem == null ? '' : labelOf(currentItem)" closable>
      <n-input
        v-model:value="editValue"
        type="textarea"
        class="mono"
        :autosize="{ minRows: 12 }"
        placeholder="文本内容"
      />
      <template #footer>
        <n-space justify="space-between" style="width: 100%">
          <n-popconfirm @positive-click="restoreDefault">
            <template #trigger>
              <n-button type="warning" secondary :loading="saving">恢复默认</n-button>
            </template>
            确认恢复默认值？
          </n-popconfirm>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.persona-list {
  display: flex;
  flex-direction: column;
}
.persona-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  cursor: pointer;
}
.persona-row:last-child {
  border-bottom: none;
}
.persona-row:hover {
  background: rgba(255, 255, 255, 0.04);
}
.persona-row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.persona-label {
  font-weight: 500;
}
</style>
