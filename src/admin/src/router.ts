import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { API_BASE } from './api'
import type { MeInfo } from './types'

let cached: MeInfo | null = null

export function resetMe(): void {
  cached = null
}

export async function fetchMe(): Promise<MeInfo | null> {
  if (cached != null) return cached
  try {
    const res = await fetch(`${API_BASE}/me`, { credentials: 'same-origin' })
    if (res.ok) {
      const data: unknown = await res.json()
      if (data != null && typeof data === 'object' && 'user_id' in data) {
        cached = data as MeInfo
      }
    }
  } catch {}
  return cached
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('./pages/LoginPage.vue'),
  },
  {
    path: '/',
    component: () => import('./layouts/AdminLayout.vue'),
    children: [
      { path: '', name: 'overview', component: () => import('./pages/OverviewPage.vue'), meta: { title: '总览' } },
      { path: 'settings/global', name: 'settings-global', component: () => import('./pages/GlobalSettingsPage.vue'), meta: { title: '全局设置' } },
      { path: 'settings/models', name: 'settings-models', component: () => import('./pages/ModelSettingsPage.vue'), meta: { title: '模型选择' } },
      { path: 'providers', name: 'providers', component: () => import('./pages/ProvidersPage.vue'), meta: { title: '服务商' } },
      { path: 'models', name: 'models', component: () => import('./pages/ModelsPage.vue'), meta: { title: '模型配置' } },
      { path: 'tools', name: 'tools', component: () => import('./pages/ToolsPage.vue'), meta: { title: 'AI 工具' } },
      { path: 'embedding', name: 'embedding', component: () => import('./pages/EmbeddingPage.vue'), meta: { title: '向量模型' } },
      { path: 'cooldown', name: 'cooldown', component: () => import('./pages/CooldownPage.vue'), meta: { title: '频道冷却' } },
      { path: 'warmup', name: 'warmup', component: () => import('./pages/WarmupPage.vue'), meta: { title: '预热频道' } },
      { path: 'filter', name: 'filter', component: () => import('./pages/FilterPage.vue'), meta: { title: '词过滤' } },
      { path: 'ab', name: 'ab', component: () => import('./pages/AbPage.vue'), meta: { title: 'A/B 实验' } },
      { path: 'ab/:id/stats', name: 'ab-stats', component: () => import('./pages/AbStatsPage.vue'), meta: { title: '实验统计' } },
      { path: 'data/:resource', name: 'data-resource', component: () => import('./pages/DataPage.vue'), meta: { title: '数据管理' } },
      { path: 'economy', name: 'economy', component: () => import('./pages/EconomyPage.vue'), meta: { title: '经济工具' } },
      { path: 'moderation', name: 'moderation', component: () => import('./pages/ModerationPage.vue'), meta: { title: '封禁与频道' } },
      { path: 'events', name: 'events', component: () => import('./pages/EventsPage.vue'), meta: { title: '活动管理' } },
      { path: 'persona', name: 'persona', component: () => import('./pages/PersonaPage.vue'), meta: { title: '人设与文案' } },
      { path: 'tuning', name: 'tuning', component: () => import('./pages/TuningPage.vue'), meta: { title: '数值调参' } },
      { path: 'audit', name: 'audit', component: () => import('./pages/AuditPage.vue'), meta: { title: '操作日志' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'overview' } },
]

export const router = createRouter({
  history: createWebHistory('/admin/'),
  routes,
})

router.beforeEach(async (to) => {
  if (to.name === 'login') return true
  const me = await fetchMe()
  if (me == null) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})
