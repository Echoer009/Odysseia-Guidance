<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NSpace, NText } from 'naive-ui'
import { API_BASE } from '../api'
import { fetchMe } from '../router'

const router = useRouter()

function login(): void {
  window.location.href = `${API_BASE}/auth/login`
}

onMounted(async () => {
  const me = await fetchMe()
  if (me != null) void router.replace({ name: 'overview' })
})
</script>

<template>
  <div class="login-wrap">
    <n-card class="login-card" title="类脑娘 管理面板">
      <n-space vertical :size="16">
        <n-button type="primary" size="large" block @click="login">使用 Discord 登录</n-button>
        <n-text depth="3" style="display: block; text-align: center">仅管理员可用</n-text>
      </n-space>
    </n-card>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card {
  width: 360px;
}
</style>
