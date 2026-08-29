<script setup lang="ts">
import { NSpace, NTag } from 'naive-ui'

defineProps<{ vision: boolean; tools: boolean; thinking: boolean }>()
</script>

<template>
  <n-space :size="4">
    <n-tag v-if="vision" size="small" type="success" :bordered="false">视觉</n-tag>
    <n-tag v-if="tools" size="small" type="info" :bordered="false">工具</n-tag>
    <n-tag v-if="thinking" size="small" type="warning" :bordered="false">思考</n-tag>
    <n-tag v-if="!vision && !tools && !thinking" size="small" :bordered="false">纯文本</n-tag>
  </n-space>
</template>
