<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NText,
  NTooltip,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'
import type { ConfigOverrideItem } from '../types'
import { prettyJson } from '../utils'

type EditorKind = 'number' | 'string' | 'text' | 'bool' | 'json'

const loading = ref(true)
const items = ref<ConfigOverrideItem[]>([])
const drafts = ref<Record<string, any>>({})
const savingKey = ref('')
const expandedNames = ref<Array<string | number>>([])

const groups = computed(() => {
  const order: string[] = []
  const map = new Map<string, ConfigOverrideItem[]>()
  for (const item of items.value) {
    const g = item.group ?? '其他'
    if (!map.has(g)) {
      map.set(g, [])
      order.push(g)
    }
    map.get(g)?.push(item)
  }
  return order.map((g) => ({ group: g, items: map.get(g) ?? [] }))
})

function labelOf(item: ConfigOverrideItem): string {
  return item.label ?? item.key
}

function kindOf(item: ConfigOverrideItem): EditorKind {
  const d = item.default
  if (typeof d === 'number') return 'number'
  if (typeof d === 'boolean') return 'bool'
  if (typeof d === 'string') return d.length > 80 ? 'text' : 'string'
  if (d == null) {
    const v = item.value ?? item.effective
    if (typeof v === 'number') return 'number'
    if (typeof v === 'boolean') return 'bool'
    if (typeof v === 'string') return v.length > 80 ? 'text' : 'string'
    return 'json'
  }
  return 'json'
}

function currentValue(item: ConfigOverrideItem): unknown {
  return item.value ?? item.effective ?? item.default
}

function defaultHint(item: ConfigOverrideItem): string {
  const d = item.default
  if (d == null) return '无'
  if (typeof d === 'boolean') return d ? '是' : '否'
  if (typeof d === 'object') return prettyJson(d)
  const text = String(d)
  return text.length > 60 ? `${text.slice(0, 60)}…` : text
}

function initDraft(item: ConfigOverrideItem): unknown {
  const kind = kindOf(item)
  const current = currentValue(item)
  if (kind === 'number') return typeof current === 'number' ? current : null
  if (kind === 'bool') return typeof current === 'boolean' ? current : false
  if (kind === 'json') return current == null ? '' : prettyJson(current)
  return current == null ? '' : String(current)
}

function jsonError(item: ConfigOverrideItem): string {
  if (kindOf(item) !== 'json') return ''
  const text = String(drafts.value[item.key] ?? '').trim()
  if (text.length === 0) return ''
  try {
    JSON.parse(text)
    return ''
  } catch (err) {
    return err instanceof Error ? `JSON 格式错误：${err.message}` : 'JSON 格式错误'
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<{ items?: ConfigOverrideItem[] } | null>('config/overrides')
    const rows = data?.items
    items.value = Array.isArray(rows) ? rows : []
    const map: Record<string, unknown> = {}
    for (const item of items.value) map[item.key] = initDraft(item)
    drafts.value = map
    expandedNames.value = [...new Set(items.value.map((item) => item.group ?? '其他'))]
  } catch {
  } finally {
    loading.value = false
  }
}

async function save(item: ConfigOverrideItem): Promise<void> {
  const kind = kindOf(item)
  let value: unknown
  if (kind === 'json') {
    const text = String(drafts.value[item.key] ?? '').trim()
    if (text.length === 0) value = null
    else {
      try {
        value = JSON.parse(text)
      } catch {
        toastError(`「${labelOf(item)}」JSON 格式错误`)
        return
      }
    }
  } else if (kind === 'number') value = drafts.value[item.key] ?? null
  else if (kind === 'bool') value = !!drafts.value[item.key]
  else value = String(drafts.value[item.key] ?? '')
  savingKey.value = item.key
  try {
    await api.put(`config/overrides/${encodeURIComponent(item.key)}`, { value })
    toastSuccess('已保存')
    await load()
  } catch {
  } finally {
    savingKey.value = ''
  }
}

async function restore(item: ConfigOverrideItem): Promise<void> {
  savingKey.value = item.key
  try {
    await api.delete(`config/overrides/${encodeURIComponent(item.key)}`)
    toastSuccess('已恢复默认')
    await load()
  } catch {
  } finally {
    savingKey.value = ''
  }
}

onMounted(() => void load())
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-collapse v-model:expanded-names="expandedNames">
        <n-collapse-item v-for="group in groups" :key="group.group" :title="group.group" :name="group.group">
          <div class="tuning-list">
            <div v-for="item in group.items" :key="item.key" class="tuning-row">
              <div class="tuning-info">
                <n-space align="center" :size="6">
                  <span class="tuning-label">{{ labelOf(item) }}</span>
                  <n-tooltip v-if="item.description" trigger="hover" :style="{ maxWidth: '320px' }">
                    <template #trigger>
                      <span class="desc-dot">?</span>
                    </template>
                    {{ item.description }}
                  </n-tooltip>
                  <n-tag v-if="item.value != null" size="tiny" type="info" :bordered="false">已覆盖</n-tag>
                </n-space>
                <n-text depth="3" size="small">默认：{{ defaultHint(item) }}</n-text>
              </div>
              <div class="tuning-editor">
                <n-input-number
                  v-if="kindOf(item) === 'number'"
                  v-model:value="drafts[item.key]"
                  style="width: 240px"
                  :placeholder="defaultHint(item)"
                />
                <n-switch v-else-if="kindOf(item) === 'bool'" v-model:value="drafts[item.key]" />
                <n-input
                  v-else-if="kindOf(item) === 'text'"
                  v-model:value="drafts[item.key]"
                  type="textarea"
                  :rows="3"
                  :placeholder="defaultHint(item)"
                />
                <n-input
                  v-else-if="kindOf(item) === 'json'"
                  v-model:value="drafts[item.key]"
                  type="textarea"
                  class="mono"
                  :rows="4"
                />
                <n-input v-else v-model:value="drafts[item.key]" :placeholder="defaultHint(item)" />
                <n-text v-if="kindOf(item) === 'json' && jsonError(item)" type="error" size="small">
                  {{ jsonError(item) }}
                </n-text>
              </div>
              <div class="tuning-actions">
                <n-button size="small" type="primary" :loading="savingKey === item.key" @click="save(item)">保存</n-button>
                <n-popconfirm v-if="item.value != null" @positive-click="restore(item)">
                  <template #trigger>
                    <n-button size="small" type="warning" secondary>恢复默认</n-button>
                  </template>
                  确认恢复为默认值？
                </n-popconfirm>
              </div>
            </div>
          </div>
        </n-collapse-item>
      </n-collapse>
      <n-text v-if="groups.length === 0 && !loading" depth="3">暂无配置项</n-text>
    </n-space>
  </n-spin>
</template>

<style scoped>
.tuning-list {
  display: flex;
  flex-direction: column;
}
.tuning-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.tuning-row:last-child {
  border-bottom: none;
}
.tuning-info {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tuning-label {
  font-weight: 500;
}
.tuning-editor {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tuning-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.desc-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid currentColor;
  font-size: 10px;
  line-height: 1;
  cursor: help;
  color: rgba(255, 255, 255, 0.45);
}
</style>
