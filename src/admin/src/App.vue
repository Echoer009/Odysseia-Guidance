<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { NConfigProvider, NGlobalStyle, darkTheme, dateZhCN, zhCN } from 'naive-ui'
import { resetMe } from './router'

const router = useRouter()

function onUnauthorized(): void {
  resetMe()
  if (router.currentRoute.value.name !== 'login') {
    void router.push({ name: 'login' })
  }
}

onMounted(() => window.addEventListener('admin:unauthorized', onUnauthorized))
onUnmounted(() => window.removeEventListener('admin:unauthorized', onUnauthorized))
</script>

<template>
  <n-config-provider :theme="darkTheme" :locale="zhCN" :date-locale="dateZhCN" style="height: 100%">
    <n-global-style />
    <router-view />
  </n-config-provider>
</template>
