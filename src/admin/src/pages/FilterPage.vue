<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NCard, NGrid, NGridItem, NInput, NSpace, NTag, NText } from 'naive-ui'
import { api } from '../api'
import { toastSuccess } from '../feedback'
import type { KeywordFilter } from '../types'
import { normalizeStringArray } from '../utils'

const loading = ref(true)
const keywords = ref<string[]>([])
const ignore = ref<string[]>([])
const newKeyword = ref('')
const newIgnore = ref('')

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<KeywordFilter | null>('filter/keywords')
    keywords.value = normalizeStringArray(data?.keywords)
    ignore.value = normalizeStringArray(data?.ignore)
  } catch {} finally {
    loading.value = false
  }
}

async function addKeyword(target: 'keywords' | 'ignore'): Promise<void> {
  const value = (target === 'keywords' ? newKeyword.value : newIgnore.value).trim()
  if (value.length === 0) return
  try {
    await api.post('filter/keywords', { keyword: value, ignore: target === 'ignore' })
    if (target === 'keywords') newKeyword.value = ''
    else newIgnore.value = ''
    toastSuccess('已添加')
    await load()
  } catch {}
}

async function removeKeyword(keyword: string): Promise<void> {
  try {
    await api.delete(`filter/keywords/${encodeURIComponent(keyword)}`)
    toastSuccess('已删除')
    await load()
  } catch {}
}

onMounted(() => void load())
</script>

<template>
  <n-grid :x-gap="16" :y-gap="16" :cols="1" m="2" responsive="screen">
    <n-grid-item>
      <n-card title="屏蔽词" size="small">
        <template #header-extra>
          <n-text depth="3" size="small">命中后拒绝处理</n-text>
        </template>
        <n-space vertical :size="12">
          <n-space :size="6" wrap>
            <n-tag v-for="keyword in keywords" :key="keyword" closable type="error" :bordered="false" @close="removeKeyword(keyword)">
              {{ keyword }}
            </n-tag>
            <n-text v-if="keywords.length === 0" depth="3">暂无</n-text>
          </n-space>
          <n-space :size="8">
            <n-input v-model:value="newKeyword" placeholder="输入屏蔽词" size="small" style="width: 240px" @keyup.enter="addKeyword('keywords')" />
            <n-button size="small" @click="addKeyword('keywords')">添加</n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-grid-item>
    <n-grid-item>
      <n-card title="忽略词" size="small">
        <template #header-extra>
          <n-text depth="3" size="small">命中后跳过，不触发屏蔽</n-text>
        </template>
        <n-space vertical :size="12">
          <n-space :size="6" wrap>
            <n-tag v-for="keyword in ignore" :key="keyword" closable type="warning" :bordered="false" @close="removeKeyword(keyword)">
              {{ keyword }}
            </n-tag>
            <n-text v-if="ignore.length === 0" depth="3">暂无</n-text>
          </n-space>
          <n-space :size="8">
            <n-input v-model:value="newIgnore" placeholder="输入忽略词" size="small" style="width: 240px" @keyup.enter="addKeyword('ignore')" />
            <n-button size="small" @click="addKeyword('ignore')">添加</n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-grid-item>
  </n-grid>
</template>
