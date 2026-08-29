<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NInput, NInputNumber, NSelect, NSpace, NSwitch, NText, type SelectOption } from 'naive-ui'
import type { AvailableModel, EditableArm } from '../types'

const props = defineProps<{ models: AvailableModel[] }>()
const arms = defineModel<EditableArm[]>({ required: true })

const options = computed<SelectOption[]>(() =>
  props.models.map((m) => ({
    label: `${m.display_name}（${m.provider_name}）`,
    value: m.full_id,
    disabled: !m.enabled,
  })),
)

const totalPercent = computed(() => arms.value.reduce((sum, arm) => sum + (arm.traffic_percent || 0), 0))
const remaining = computed(() => 100 - totalPercent.value)

function addArm(): void {
  arms.value = [...arms.value, { label: '', model_full_id: null, traffic_percent: 0, enabled: true }]
}

function removeArm(index: number): void {
  arms.value = arms.value.filter((_, i) => i !== index)
}
</script>

<template>
  <n-space vertical :size="10">
    <div v-for="(arm, index) in arms" :key="index" class="arm-row">
      <n-input v-model:value="arm.label" placeholder="分组标签" size="small" style="width: 140px" />
      <n-select
        v-model:value="arm.model_full_id"
        :options="options"
        placeholder="选择模型"
        size="small"
        filterable
        style="flex: 1; min-width: 220px"
      />
      <n-input-number v-model:value="arm.traffic_percent" :min="0" :max="100" size="small" style="width: 110px">
        <template #suffix>%</template>
      </n-input-number>
      <n-switch v-model:value="arm.enabled" size="small" />
      <n-button size="small" type="error" quaternary @click="removeArm(index)">删除</n-button>
    </div>
    <n-button dashed size="small" style="width: 100%" @click="addArm">添加分组</n-button>
    <n-text :type="remaining < 0 ? 'error' : 'default'">
      分流合计 {{ totalPercent }}%，剩余 {{ remaining }}% 走默认模型
    </n-text>
  </n-space>
</template>

<style scoped>
.arm-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
