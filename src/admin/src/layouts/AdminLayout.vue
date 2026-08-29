<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NSpace,
  NTag,
  type MenuOption,
} from 'naive-ui'
import { api } from '../api'
import { fetchMe, resetMe } from '../router'
import type { MeInfo } from '../types'

const router = useRouter()
const route = useRoute()
const me = ref<MeInfo | null>(null)
const collapsed = ref(false)

function link(label: string, path: string): MenuOption {
  return {
    key: path,
    label: () => h(RouterLink, { to: { path } }, { default: () => label }),
  }
}

const menuOptions: MenuOption[] = [
  link('总览', '/'),
  {
    key: 'settings',
    label: '系统设置',
    children: [link('全局开关', '/settings/global'), link('模型选择', '/settings/models')],
  },
  link('服务商', '/providers'),
  link('模型配置', '/models'),
  link('AI 工具', '/tools'),
  link('向量模型', '/embedding'),
  {
    key: 'channels',
    label: '频道',
    children: [link('聊天冷却', '/cooldown'), link('预热频道', '/warmup')],
  },
  link('词过滤', '/filter'),
  link('A/B 实验', '/ab'),
  {
    key: 'data',
    label: '数据管理',
    children: [
      link('成员档案', '/data/member_profiles'),
      link('记忆笔记', '/data/memory_notes'),
      link('通用知识', '/data/knowledge_documents'),
      link('对话块', '/data/conversation_blocks'),
      link('帖子索引', '/data/forum_threads'),
      link('用户金币', '/data/user_coins'),
      link('金币流水（只读）', '/data/coin_transactions'),
      link('贷款', '/data/coin_loans'),
      link('好感度', '/data/user_affection'),
      link('警告记录（只读）', '/data/user_warnings'),
      link('商店商品', '/data/shop_items'),
      link('工作事件', '/data/work_events'),
      link('人设偏好', '/data/user_persona_preference'),
    ],
  },
  link('经济工具', '/economy'),
  link('封禁与频道', '/moderation'),
  link('活动管理', '/events'),
  link('人设与文案', '/persona'),
  link('数值调参', '/tuning'),
  link('操作日志', '/audit'),
]

const activeKey = computed(() => {
  if (route.path.startsWith('/ab')) return '/ab'
  return route.path
})

async function logout(): Promise<void> {
  try {
    await api.post('auth/logout')
  } catch {}
  resetMe()
  void router.push({ name: 'login' })
}

onMounted(async () => {
  me.value = await fetchMe()
})
</script>

<template>
  <n-layout style="height: 100vh" has-sider>
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :collapsed="collapsed"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="brand">{{ collapsed ? '类' : '类脑娘' }}</div>
      <n-menu :collapsed="collapsed" :collapsed-width="64" :collapsed-icon-size="20" :options="menuOptions" :value="activeKey" />
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="header">
        <span class="header-title">{{ String(route.meta.title ?? '') }}</span>
        <n-space align="center" :size="12">
          <n-tag v-if="me" type="info" size="small" :bordered="false">{{ me.user_id }}</n-tag>
          <n-button quaternary size="small" @click="logout">退出登录</n-button>
        </n-space>
      </n-layout-header>
      <n-layout-content class="content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<style scoped>
.brand {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 2px;
}
.header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}
.header-title {
  font-size: 15px;
  font-weight: 500;
}
.content {
  padding: 16px;
  min-height: calc(100vh - 48px);
}
</style>
