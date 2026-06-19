<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import gsap from 'gsap'
import type { Expression, ChapterMood, Diary, DiaryEntry } from './types'
import { setupChildBridge } from './child-bridge'
import CharacterSprite from './components/CharacterSprite.vue'
import DialogueBox from './components/DialogueBox.vue'

const baseUrl = import.meta.env.BASE_URL
const queryParams = new URLSearchParams(window.location.search)
const isEmbedded = queryParams.get('frame_id') != null

let accessToken: string | null = null

const currentScene = ref<'loading' | 'diary'>('loading')
const coverVisible = ref(false)
const diary = ref<Diary | null>(null)
const userName = ref('')

const entryIndex = ref(0)
const activeText = ref('')
const dialogueComplete = ref(false)
const mood = ref<ChapterMood>('normal')

const stageRef = ref<HTMLElement | null>(null)
const petalContainer = ref<HTMLElement | null>(null)
const dialogueRef = ref<InstanceType<typeof DialogueBox> | null>(null)
const coverRef = ref<HTMLElement | null>(null)

// --- BGM ---
const audioRef = ref<HTMLAudioElement | null>(null)
const muted = ref(false)
let bgmStarted = false
const bgmSrc = baseUrl + 'audio/bgm.mp3'

const currentEntry = computed<DiaryEntry | null>(
  () => diary.value?.entries[entryIndex.value] ?? null,
)
const currentExpression = computed<Expression>(
  () => currentEntry.value?.expression ?? 'normal',
)
const isFinale = computed(() => {
  if (!diary.value) return false
  return entryIndex.value === diary.value.entries.length - 1 && dialogueComplete.value
})

// ---------------------------------------------------------------------------
// API / Auth
// ---------------------------------------------------------------------------

async function apiCall(endpoint: string, method: 'GET' | 'POST' | 'DELETE', body?: object, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const headers: HeadersInit = { 'Content-Type': 'application/json' }
      if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`
      const response = await fetch(baseUrl + endpoint.replace(/^\//, ''), {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'API请求失败' }))
        throw new Error(err.detail || 'API请求失败')
      }
      return response.json()
    } catch (error) {
      if (i === retries) throw error
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, i)))
    }
  }
}

async function setupDiscordSdk() {
  const { DiscordSDK } = await import('@discord/embedded-app-sdk')
  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID
  if (!clientId) throw new Error('VITE_DISCORD_CLIENT_ID is not set.')
  const discordSdk = new DiscordSDK(clientId)
  await discordSdk.ready()
  const { code } = await discordSdk.commands.authorize({
    client_id: discordSdk.clientId,
    response_type: 'code',
    state: '',
    prompt: 'none',
    scope: ['identify', 'guilds'],
  })
  const response = await fetch(baseUrl + 'api/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  if (!response.ok) throw new Error(`Token exchange failed: ${response.status}`)
  const { access_token } = await response.json()
  const auth = await discordSdk.commands.authenticate({ access_token })
  if (!auth) throw new Error('Authenticate failed')
  accessToken = access_token
}

async function fetchUserInfo() {
  try {
    const data = await apiCall('/api/user', 'GET')
    if (data.username) userName.value = data.username
  } catch {
    userName.value = '旅行者'
  }
}

async function fetchDiary() {
  diary.value = await apiCall('/api/diary', 'GET')
}

// ---------------------------------------------------------------------------
// BGM
// ---------------------------------------------------------------------------

function tryPlayBgm() {
  if (!audioRef.value) return
  audioRef.value.volume = 0.45
  audioRef.value.play().catch(() => {})
}

function ensureBgm() {
  if (bgmStarted) return
  bgmStarted = true
  tryPlayBgm()
}

function toggleMute() {
  muted.value = !muted.value
  if (audioRef.value) audioRef.value.muted = muted.value
}

// ---------------------------------------------------------------------------
// 场景推进
// ---------------------------------------------------------------------------

function showEntry() {
  const e = currentEntry.value
  if (!e) return
  if (e.mood !== mood.value) {
    mood.value = e.mood
    spawnPetalsForMood(e.mood)
  }
  activeText.value = e.text
  dialogueComplete.value = false
}

function transitionEntry(done: () => void) {
  const el = stageRef.value
  if (!el) {
    done()
    return
  }
  gsap.to(el, {
    opacity: 0,
    duration: 0.3,
    ease: 'power2.in',
    onComplete: () => {
      done()
      requestAnimationFrame(() => {
        gsap.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.4, ease: 'power2.out' })
      })
    },
  })
}

function advanceEntry() {
  if (!diary.value) return
  const total = diary.value.entries.length
  if (entryIndex.value < total - 1) {
    transitionEntry(() => {
      entryIndex.value++
      showEntry()
    })
  } else {
    // 到头了：回到开头循环
    transitionEntry(() => {
      entryIndex.value = 0
      showEntry()
    })
  }
}

function openDiary() {
  ensureBgm()
  if (!coverRef.value) {
    coverVisible.value = false
    nextTick(() => showEntry())
    return
  }
  gsap.to(coverRef.value, {
    xPercent: -100,
    duration: 0.7,
    ease: 'power3.inOut',
    onComplete: () => {
      coverVisible.value = false
      nextTick(() => showEntry())
    },
  })
}

function onSceneClick() {
  ensureBgm()
  if (dialogueComplete.value) {
    advanceEntry()
  }
}

function onDialogueComplete() {
  dialogueComplete.value = true
}

// ---------------------------------------------------------------------------
// 画廊 / 边注
// ---------------------------------------------------------------------------

function galleryImg(category: string | undefined, name: string): string {
  return baseUrl + `assets/gallery/${category || 'food'}/${name}.webp`
}

function onGalleryError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

// 每张照片一个稳定的微旋转，像随手贴的
const POLAROID_ROTS = [-7, 5, -4, 8, -6, 3, -5, 6, -3, 4]
function polaroidRot(i: number): number {
  return POLAROID_ROTS[i % POLAROID_ROTS.length]
}

// 把句子里的数字拆出来，单独高亮（数字用强调色加粗）
function splitNumbers(s: string): { text: string; num: boolean }[] {
  const parts: { text: string; num: boolean }[] = []
  const re = /[\d][\d,]*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(s))) {
    if (m.index > last) parts.push({ text: s.slice(last, m.index), num: false })
    parts.push({ text: m[0], num: true })
    last = m.index + m[0].length
  }
  if (last < s.length) parts.push({ text: s.slice(last), num: false })
  return parts
}

// ---------------------------------------------------------------------------
// 花瓣 / 氛围
// ---------------------------------------------------------------------------

function spawnPetalsForMood(m: ChapterMood) {
  if (!petalContainer.value) return
  petalContainer.value.innerHTML = ''
  if (m === 'normal') return

  const palette =
    m === 'sad'
      ? ['#cfc8bd', '#b8b0a3', '#a99f90']
      : ['#d98a4e', '#c08a3e', '#b5462d', '#e3b87a']

  const count = m === 'sad' ? 22 : 30
  for (let i = 0; i < count; i++) {
    const petal = document.createElement('div')
    petal.className = 'petal'
    const color = palette[Math.floor(Math.random() * palette.length)]
    petal.style.background = color
    petal.style.left = `${Math.random() * 100}%`
    petalContainer.value.appendChild(petal)

    gsap.to(petal, {
      y: window.innerHeight + 50,
      x: (Math.random() - 0.5) * 80,
      rotation: Math.random() * 720,
      duration: 4 + Math.random() * 4,
      delay: Math.random() * 2.5,
      ease: 'none',
      onComplete: () => petal.remove(),
    })
  }
}

// ---------------------------------------------------------------------------
// 启动
// ---------------------------------------------------------------------------

async function main() {
  try {
    const bridgeData = await setupChildBridge()
    if (bridgeData) {
      accessToken = bridgeData.accessToken
      if (bridgeData.user?.username) userName.value = bridgeData.user.username
    } else if (isEmbedded) {
      await setupDiscordSdk()
    }
    await fetchUserInfo()
  } catch (e) {
    console.error('Init error:', e)
  }

  await fetchDiary()

  if (diary.value && diary.value.entries.length) {
    currentScene.value = 'diary'
    coverVisible.value = true
  }
}

onMounted(main)
</script>

<template>
  <div class="app-root" :class="['mood-' + mood]">
    <!-- 背景层 -->
    <div class="bg-layer bg-paper"></div>
    <div class="bg-vignette"></div>
    <div class="mood-overlay"></div>

    <!-- 花瓣 -->
    <div ref="petalContainer" class="petal-container"></div>

    <!-- BGM -->
    <audio ref="audioRef" :src="bgmSrc" loop preload="auto"></audio>
    <button
      v-if="!coverVisible"
      class="bgm-control"
      @click.stop="toggleMute"
      :title="muted ? '取消静音' : '静音'"
    >
      {{ muted ? '静音中' : '音乐' }}
    </button>

    <!-- 加载 -->
    <div v-if="currentScene === 'loading'" class="scene scene-loading">
      <div class="loading-spinner"></div>
      <div class="loading-text">翻开日记本……</div>
    </div>

    <!-- 日记正文 -->
    <div v-if="currentScene === 'diary'" class="scene scene-diary" @click="onSceneClick">
      <div ref="stageRef" class="diary-stage">
        <!-- 日期戳 -->
        <div class="entry-date hand">{{ currentEntry?.date }}</div>

        <!-- 立绘（画廊页隐藏，让位给照片） -->
        <CharacterSprite
          v-if="currentEntry?.type !== 'gallery'"
          :expression="currentExpression"
          position="right"
          :scale="1"
          skip-entrance
          interactive
        />

        <!-- 照片墙：冲洗出来的照片，贴在旁边 -->
        <div v-if="currentEntry?.type === 'gallery'" class="photo-board">
          <div
            v-for="(item, i) in currentEntry.gallery_items"
            :key="item"
            class="polaroid"
            :style="{ '--rot': polaroidRot(i) + 'deg' }"
          >
            <div class="pol-img">
              <span class="pol-fallback hand">{{ item }}</span>
              <img
                :src="galleryImg(currentEntry.gallery_category, item)"
                :alt="item"
                @error="onGalleryError"
              />
            </div>
          </div>
        </div>

        <!-- 边注数据 -->
        <Transition name="data">
          <div
            v-if="currentEntry?.data_label"
            class="margin-note serif"
            :key="entryIndex"
          >
            <div class="mn-label">{{ currentEntry.data_label }}</div>
            <div class="mn-value">
              <span
                v-for="(p, i) in splitNumbers(currentEntry.data_value || '')"
                :key="i"
                :class="{ num: p.num }"
              >{{ p.text }}</span>
            </div>
            <div v-if="currentEntry.data_secondary" class="mn-secondary">
              {{ currentEntry.data_secondary }}
            </div>
          </div>
        </Transition>

        <!-- 对话框（手写日记正文，写在纸上） -->
        <DialogueBox
          ref="dialogueRef"
          :text="activeText"
          :expression="currentExpression"
          :speaker="diary?.bot_name"
          :clickable="false"
          @complete="onDialogueComplete"
          @advance="advanceEntry"
        />

        <!-- 尾声提示 -->
        <div v-if="isFinale" class="finale-hint serif">
          点击重新翻阅 · 未完待续
        </div>
      </div>
    </div>

    <!-- 封面：纯黑 + 日记本（点击后向左滑走） -->
    <div v-if="coverVisible" ref="coverRef" class="cover-overlay" @click="openDiary">
      <h1 class="cover-title serif">日记本</h1>
    </div>
  </div>
</template>

<style>
.app-root {
  height: 100%;
  width: 100%;
  position: relative;
  overflow: hidden;
}

.bg-layer {
  position: absolute;
  inset: 0;
  z-index: 0;
  transition: filter 0.8s ease;
}

/* 横线笔记本纸面 */
.bg-paper {
  background-color: #f6f1e7;
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 38px,
    rgba(43, 38, 32, 0.06) 38px,
    rgba(43, 38, 32, 0.06) 39px
  );
}

.bg-vignette {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(60,45,30,0.18) 100%);
}

/* 氛围层：叠色实现「灯光」，内容层不受影响 */
.mood-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: rgba(20, 18, 14, 0);
  transition: background 0.9s ease;
}

.mood-sad .mood-overlay {
  background: rgba(18, 20, 28, 0.55);
}

.mood-sad .bg-paper {
  filter: brightness(0.7) saturate(0.7);
}

.mood-sad {
  --ink: #efe6d4;
  --ink-soft: #c4b8a3;
  --ink-muted: #968a76;
}

.mood-celebration .mood-overlay {
  background: rgba(255, 210, 150, 0.10);
}

.petal-container {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  overflow: hidden;
}

.petal {
  position: absolute;
  top: -30px;
  width: 12px;
  height: 18px;
  clip-path: ellipse(50% 40% at 50% 50%);
  opacity: 0.7;
  pointer-events: none;
}

/* 场景 */
.scene {
  position: absolute;
  inset: 0;
  z-index: 5;
}

.scene-diary {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.scene-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  z-index: 6;
}

.loading-spinner {
  width: 46px;
  height: 46px;
  border: 3px solid rgba(181, 70, 45, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 16px;
  color: var(--ink-soft);
  letter-spacing: 2px;
}

.diary-stage {
  position: absolute;
  inset: 0;
}

/* 日期戳 */
.entry-date {
  position: absolute;
  top: 42px;
  left: 60px;
  z-index: 13;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-soft);
  letter-spacing: 2px;
}

/* 照片墙：冲洗出来的照片贴在右侧 */
.photo-board {
  position: absolute;
  top: 76px;
  bottom: 30px;
  left: 56%;
  right: 20px;
  z-index: 11;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 20px 14px;
  align-items: center;
  justify-items: center;
  padding: 10px 8px;
}

.polaroid {
  width: 100%;
  max-width: 280px;
  box-sizing: border-box;
  background: #fffdfa;
  padding: 9px 9px 14px;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.16), 0 2px 5px rgba(0, 0, 0, 0.10);
  transform: rotate(var(--rot, 0deg));
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  position: relative;
}

.polaroid:hover {
  transform: rotate(0deg) translateY(-5px) scale(1.05);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.22);
  z-index: 5;
}

/* 顶部胶带 */
.polaroid::before {
  content: '';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%) rotate(-4deg);
  width: 44px;
  height: 17px;
  background: rgba(214, 196, 148, 0.5);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.pol-img {
  width: 100%;
  position: relative;
  background: #efe9da;
  overflow: hidden;
  min-height: 70px;
}

.pol-img img {
  position: relative;
  display: block;
  width: 100%;
  height: auto;
  z-index: 1;
}

.pol-fallback {
  position: absolute;
  inset: 0;
  z-index: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #b3ab9c;
  text-align: center;
  padding: 6px;
  line-height: 1.4;
}

/* 边注数据：无卡片框，细竖线 + 类别 + 数字高亮 */
.margin-note {
  position: absolute;
  top: 210px;
  left: 60px;
  z-index: 12;
  max-width: 320px;
  padding: 4px 0 4px 16px;
  border-left: 2px solid var(--accent);
}

.mn-label {
  font-size: 11px;
  letter-spacing: 4px;
  color: var(--ink-muted);
  margin-bottom: 8px;
}

.mn-value {
  font-size: 44px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.2;
}

.mn-value .num {
  color: var(--gold);
  font-weight: 900;
  font-size: 1.2em;
}

.mn-secondary {
  margin-top: 8px;
  font-size: 13px;
  color: var(--ink-soft);
  line-height: 1.6;
}

.data-enter-active,
.data-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.data-enter-from {
  opacity: 0;
  transform: translateY(-12px);
}
.data-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* 封面：纯黑 + 日记本 */
.cover-overlay {
  position: absolute;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  cursor: pointer;
  animation: cover-in 0.6s ease-out both;
}

.cover-title {
  font-size: 64px;
  font-weight: 600;
  color: #e8e0d0;
  letter-spacing: 24px;
  padding-left: 24px;
  animation: cover-text-in 1.6s ease-out 0.2s both;
}

@keyframes cover-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes cover-text-in {
  from { opacity: 0; letter-spacing: 40px; }
  to { opacity: 1; letter-spacing: 24px; }
}

/* 尾声 */
.finale-hint {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  font-size: 14px;
  color: var(--ink-muted);
  letter-spacing: 3px;
  pointer-events: none;
  animation: hint-fade 2.4s ease-in-out infinite;
}

@keyframes hint-fade {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

/* BGM 控件 */
.bgm-control {
  position: absolute;
  bottom: 14px;
  right: 16px;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--ink-soft);
  background: var(--card);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  box-shadow: var(--shadow-normal);
  letter-spacing: 2px;
}

.bgm-control:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
