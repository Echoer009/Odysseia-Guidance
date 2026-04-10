<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import gsap from 'gsap'
import type { SceneName, Expression, TourSlide } from './types'
import { welcomeDialogues, selectionHint, tourStartDialogue } from './data/dialogues'
import { buildTourQueue } from './data/channelData'
import { buildChannelUrl } from './utils/parser'
import { cloudAssets, backgroundAssets, expressions } from './data/assetsConfig'
import CharacterSprite from './components/CharacterSprite.vue'
import DialogueBox from './components/DialogueBox.vue'
import CardSelect from './components/CardSelect.vue'
import ChannelTour from './components/ChannelTour.vue'

const currentScene = ref<SceneName>('loading')
const userName = ref('')

const currentDialogue = ref('')
const currentExpression = ref<Expression>('normal')
const currentImage = ref<string | undefined>(undefined)
const dialogueIndex = ref(0)
const dialogueComplete = ref(false)

const selectedTags = ref<string[]>([])
const channelsQueue = ref<TourSlide[]>([])
const charOrigin = ref<{ x: number; y: number } | null>(null)

const finishChannels = ref<{ name: string; url: string }[]>([])
const petalContainer = ref<HTMLElement | null>(null)
const awakeOverlayRef = ref<HTMLElement | null>(null)
const welcomeDialogueRef = ref<InstanceType<typeof DialogueBox> | null>(null)

const GUILD_ID = '1234431460159160360'

const queryParams = new URLSearchParams(window.location.search)
const isEmbedded = queryParams.get('frame_id') != null

let accessToken: string | null = null

const finishExpression = computed<Expression>(() => 'happy')

const skyBgLoaded = ref(false)
const finishBgLoaded = ref(false)

function tryLoadBg(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(true)
    img.onerror = () => resolve(false)
    img.src = url
  })
}

async function initBackgrounds() {
  const [skyOk, finishOk] = await Promise.all([
    tryLoadBg(backgroundAssets.sky),
    tryLoadBg(backgroundAssets.finish),
  ])
  skyBgLoaded.value = skyOk
  finishBgLoaded.value = finishOk
}

function handleCloudError(event: Event) {
  const el = event.target as HTMLElement
  if (el.parentElement) el.parentElement.style.display = 'none'
}

function handleSunflowerError(event: Event) {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
  const fallback = img.nextElementSibling as HTMLElement
  if (fallback) fallback.style.display = 'flex'
}

async function apiCall(endpoint: string, method: 'GET' | 'POST', body?: object, retries = 2) {
  if (isEmbedded && !accessToken) {
    throw new Error('Access Token is not available in embedded mode.')
  }

  for (let i = 0; i <= retries; i++) {
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      }
      if (isEmbedded && accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`
      }

      const response = await fetch(endpoint, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'API请求失败' }))
        throw new Error(errorData.detail || 'API请求失败')
      }
      return response.json()
    } catch (error) {
      if (i === retries) throw error
      await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)))
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

  const response = await fetch('/api/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  const { access_token } = await response.json()
  const auth = await discordSdk.commands.authenticate({ access_token })
  if (!auth) throw new Error('Authenticate command failed')

  accessToken = access_token
  if (auth.user?.username) {
    userName.value = auth.user.username
  }
}

async function fetchUserInfo() {
  try {
    const data = await apiCall('/api/user', 'GET')
    if (data.username) {
      userName.value = data.username
    }
  } catch {
    userName.value = '旅行者'
  }
}

async function preloadAssets() {
  const images = Object.values(expressions).map(e => e.path).filter(Boolean)

  cloudAssets.forEach(c => {
    images.push(`/assets/clouds/${c.file}`)
  })

  const loadImg = (src: string) =>
    new Promise<void>((resolve) => {
      const img = new Image()
      img.onload = () => resolve()
      img.onerror = () => resolve()
      img.src = src
    })

  const batchSize = 4
  for (let i = 0; i < images.length; i += batchSize) {
    const batch = images.slice(i, i + batchSize)
    await Promise.all(batch.map(loadImg))
  }
}

function transitionTo(scene: SceneName) {
  const el = document.querySelector('.scene')
  if (el) {
    gsap.to(el, {
      x: -60,
      opacity: 0,
      duration: 0.3,
      ease: 'power2.in',
      onComplete: () => {
        currentScene.value = scene
        requestAnimationFrame(() => {
          gsap.fromTo('.scene',
            { x: 60, opacity: 0 },
            { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' },
          )
        })
      },
    })
  } else {
    currentScene.value = scene
  }
}

function startWelcome() {
  dialogueIndex.value = 0
  const dialogue = welcomeDialogues[0]
  let text = dialogue.text
  if (userName.value && dialogueIndex.value === 0) {
    text = text.replace('很高兴认识你', `很高兴认识你，${userName.value}`)
  }
  currentDialogue.value = text
  currentExpression.value = dialogue.expression
  currentImage.value = dialogue.image
  dialogueComplete.value = false

  currentScene.value = 'welcome'

  requestAnimationFrame(() => {
    if (!awakeOverlayRef.value) return
    const overlay = awakeOverlayRef.value
    gsap.set(overlay, { opacity: 1, pointerEvents: 'all' })

    const tl = gsap.timeline({
      onComplete: () => {
        gsap.set(overlay, { pointerEvents: 'none', opacity: 0 })
      },
    })

    tl.to(overlay, {
      opacity: 0,
      duration: 1.8,
      ease: 'power2.inOut',
      delay: 0.2,
    })
  })
}

function advanceDialogue() {
  if (dialogueIndex.value < welcomeDialogues.length - 1) {
    dialogueIndex.value++
    const dialogue = welcomeDialogues[dialogueIndex.value]
    currentDialogue.value = dialogue.text
    currentExpression.value = dialogue.expression
    currentImage.value = dialogue.image
    dialogueComplete.value = false
  } else {
    const charEl = document.querySelector('.character-sprite')
    if (charEl) {
      const rect = charEl.getBoundingClientRect()
      charOrigin.value = { x: rect.left + rect.width / 2, y: rect.top + rect.height * 0.3 }
    }
    currentDialogue.value = selectionHint.text
    currentExpression.value = selectionHint.expression
    currentImage.value = selectionHint.image
    currentScene.value = 'selection'
  }
}

function onDialogueComplete() {
  dialogueComplete.value = true
}

function onWelcomeSceneClick() {
  if (!dialogueComplete.value) {
    welcomeDialogueRef.value?.skipToEnd()
  } else {
    advanceDialogue()
  }
}

function onTagComment(_tagName: string, comment: string, expression: string) {
  currentDialogue.value = comment
  currentExpression.value = expression as Expression
  currentImage.value = undefined
  dialogueComplete.value = false
}

function onTagConfirm(tags: string[]) {
  selectedTags.value = tags
  channelsQueue.value = buildTourQueue(tags)
  transitionTo('tour')
  currentDialogue.value = tourStartDialogue.text
  currentExpression.value = tourStartDialogue.expression
  currentImage.value = tourStartDialogue.image
}

function onTourFinish() {
  finishChannels.value = channelsQueue.value.map(s => ({
    name: s.channelName,
    url: buildChannelUrl(GUILD_ID, s.channelId),
  }))

  transitionTo('finish')
  currentExpression.value = 'happy'

  setTimeout(() => {
    createPetals()
  }, 500)

  setTimeout(() => {
    animateFinishContent()
  }, 200)
}

function createPetals() {
  if (!petalContainer.value) return
  const container = petalContainer.value

  for (let i = 0; i < 24; i++) {
    const petal = document.createElement('div')
    petal.className = 'petal'
    petal.style.left = `${Math.random() * 100}%`
    container.appendChild(petal)

    gsap.to(petal, {
      y: window.innerHeight + 50,
      x: (Math.random() - 0.5) * 60,
      rotation: Math.random() * 720,
      duration: 3 + Math.random() * 3,
      delay: Math.random() * 2,
      ease: 'none',
      onComplete: () => petal.remove(),
    })
  }
}

function animateFinishContent() {
  const hash = document.querySelector('.finish-hash') as HTMLElement
  const title = document.querySelector('.finish-title') as HTMLElement
  const accentLine = document.querySelector('.finish-accent-line') as HTMLElement
  const subtitle = document.querySelector('.finish-subtitle') as HTMLElement
  const items = document.querySelectorAll('.finish-channel-item')

  const tl = gsap.timeline()

  if (hash) {
    tl.fromTo(hash,
      { x: 120, opacity: 0, scale: 0.5 },
      { x: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.8)' },
    )
  }

  if (title) {
    tl.fromTo(title,
      { x: 160, opacity: 0, skewX: -8 },
      { x: 0, opacity: 1, skewX: 0, duration: 0.6, ease: 'power3.out' },
      '-=0.3',
    )
  }

  if (accentLine) {
    tl.fromTo(accentLine,
      { scaleX: 0 },
      { scaleX: 1, duration: 0.4, ease: 'power2.out' },
      '-=0.2',
    )
  }

  if (subtitle) {
    tl.fromTo(subtitle,
      { x: 80, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' },
      '-=0.15',
    )
  }

  if (items.length) {
    tl.fromTo(
      items,
      { x: 100, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.4, stagger: 0.06, ease: 'power2.out' },
      '-=0.1',
    )
  }
}

async function main() {
  try {
    if (isEmbedded) {
      await setupDiscordSdk()
      await fetchUserInfo()
      await initBackgrounds()
      await preloadAssets()
    } else {
      await fetchUserInfo()
      await initBackgrounds()
      await preloadAssets()
    }

    setTimeout(() => {
      startWelcome()
    }, 300)
  } catch (e: unknown) {
    console.error('Init error:', e)
    setTimeout(() => {
      startWelcome()
    }, 1000)
  }
}

onMounted(main)
</script>

<template>
  <div class="app-root">
    <div ref="awakeOverlayRef" class="awake-overlay"></div>

    <div
      v-if="currentScene === 'loading'"
      class="scene scene-loading"
    >
      <div class="loading-content">
        <div class="loading-sunflower">
          <img
            :src="backgroundAssets.sunflower"
            alt=""
            class="loading-sunflower-img"
            @error="handleSunflowerError"
          />
          <div class="loading-sunflower-fallback">🌻</div>
        </div>
      </div>
    </div>

    <div
      v-else-if="currentScene === 'welcome'"
      class="scene scene-clickable"
      :class="skyBgLoaded ? 'bg-sky' : 'bg-sky-fallback'"
      :style="skyBgLoaded ? { '--bg-image': `url(${backgroundAssets.sky})` } : {}"
      @click="onWelcomeSceneClick"
    >
      <div
        v-for="(cloud, i) in cloudAssets"
        :key="i"
        class="cloud"
        :style="{
          width: (cloud.width * cloud.scale) + 'px',
          height: (cloud.height * cloud.scale) + 'px',
          top: cloud.top,
          animationDuration: cloud.duration + 's',
          animationDelay: cloud.delay + 's',
        }"
      >
        <img
          :src="'/assets/clouds/' + cloud.file"
          alt=""
          @error="handleCloudError"
        />
      </div>

      <CharacterSprite :expression="currentExpression" :custom-src="currentImage" position="right" :scale="1" />

      <DialogueBox
        ref="welcomeDialogueRef"
        :text="currentDialogue"
        :expression="currentExpression"
        @advance="advanceDialogue"
        @complete="onDialogueComplete"
      />
    </div>

    <div
      v-else-if="currentScene === 'selection'"
      class="scene"
      :class="skyBgLoaded ? 'bg-sky' : 'bg-sky-fallback'"
      :style="skyBgLoaded ? { '--bg-image': `url(${backgroundAssets.sky})` } : {}"
    >
      <div
        v-for="(cloud, i) in cloudAssets"
        :key="i"
        class="cloud"
        :style="{
          width: (cloud.width * cloud.scale) + 'px',
          height: (cloud.height * cloud.scale) + 'px',
          top: cloud.top,
          animationDuration: cloud.duration + 's',
          animationDelay: cloud.delay + 's',
        }"
      >
        <img
          :src="'/assets/clouds/' + cloud.file"
          alt=""
          @error="handleCloudError"
        />
      </div>

      <CharacterSprite :expression="currentExpression" :custom-src="currentImage" position="right" :scale="1" skip-entrance />

      <DialogueBox
        :text="currentDialogue"
        :expression="currentExpression"
        :clickable="false"
        speaker="类脑娘"
      />

      <CardSelect :fly-origin="charOrigin" @confirm="onTagConfirm" @tag-comment="onTagComment" />
    </div>

    <div v-else-if="currentScene === 'tour'" class="scene">
      <ChannelTour :slides="channelsQueue" @finish="onTourFinish" />
    </div>

    <div
      v-else-if="currentScene === 'finish'"
      class="scene"
      :class="finishBgLoaded ? 'bg-finish' : 'bg-finish-fallback'"
      :style="finishBgLoaded ? { '--bg-image': `url(${backgroundAssets.finish})` } : {}"
    >
      <div ref="petalContainer" class="petal-container"></div>

      <CharacterSprite :expression="finishExpression" position="right" :scale="1" />

      <div class="finish-content">
        <div class="finish-header">
          <span class="finish-hash">#</span>
          <h2 ref="finishTitleRef" class="finish-title">引导完成</h2>
        </div>
        <div class="finish-accent-line"></div>
        <p class="finish-subtitle">以下是为你推荐的频道</p>

        <div class="finish-channels">
          <a
            v-for="ch in finishChannels"
            :key="ch.url"
            :href="ch.url"
            class="finish-channel-item"
            target="_blank"
            rel="noopener"
          >
            <span class="finish-channel-hash">#</span>
            <span class="finish-channel-name">{{ ch.name }}</span>
            <span class="finish-channel-arrow">→</span>
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.scene-clickable {
  cursor: pointer;
}

.app-root {
  height: 100%;
  width: 100%;
  position: relative;
}

.awake-overlay {
  position: absolute;
  inset: 0;
  background: #000;
  z-index: 100;
  pointer-events: none;
  opacity: 0;
  will-change: opacity;
}

.scene-loading {
  background: #000 !important;
}

.loading-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

.loading-sunflower {
  width: 96px;
  height: 96px;
}

.loading-sunflower-img {
  width: 96px;
  height: 96px;
  object-fit: contain;
  animation: self-spin 8s linear infinite;
  transform-origin: center center;
  filter: drop-shadow(0 0 12px rgba(206, 66, 43, 0.3));
}

.loading-sunflower-fallback {
  display: none;
  width: 96px;
  height: 96px;
  align-items: center;
  justify-content: center;
  font-size: 72px;
  animation: self-spin 8s linear infinite;
  transform-origin: center center;
  filter: drop-shadow(0 0 12px rgba(206, 66, 43, 0.3));
}

@keyframes self-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.petal-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 1;
}

.petal {
  position: absolute;
  top: -30px;
  width: 16px;
  height: 22px;
  background: linear-gradient(135deg, #CE422B, #F07623);
  clip-path: ellipse(50% 40% at 50% 50%);
  opacity: 0.75;
  pointer-events: none;
}

.finish-content {
  position: absolute;
  top: 50%;
  left: 60px;
  right: 430px;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  z-index: 10;
  padding: 24px;
}

.finish-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}

.finish-hash {
  font-size: 32px;
  font-weight: 900;
  color: var(--accent-gold);
  line-height: 1;
  text-shadow: 0 2px 12px rgba(206, 66, 43, 0.3);
}

.finish-title {
  font-size: 38px;
  font-weight: 900;
  color: var(--text-primary);
  line-height: 1.1;
  letter-spacing: -1px;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.06);
}

.finish-accent-line {
  width: 80px;
  height: 3px;
  background: var(--accent-gold);
  transform-origin: left center;
  margin-bottom: 16px;
  border-radius: 2px;
}

.finish-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.finish-channels {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 45vh;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding-right: 4px;
}

.finish-channels::-webkit-scrollbar {
  display: none;
}

.finish-channel-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  text-decoration: none;
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.finish-channel-item:hover {
  border-color: var(--accent-gold);
  transform: translateX(6px);
  box-shadow: 0 4px 16px rgba(206, 66, 43, 0.12);
}

.finish-channel-hash {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-gold);
  font-size: 14px;
  font-weight: 900;
  color: var(--text-primary);
  flex-shrink: 0;
}

.finish-channel-name {
  flex: 1;
  font-size: 16px;
  font-weight: 700;
}

.finish-channel-arrow {
  color: var(--accent-gold);
  font-weight: 400;
  font-size: 16px;
  transition: transform 0.15s ease;
}

.finish-channel-item:hover .finish-channel-arrow {
  transform: translateX(4px);
}

@media (max-width: 768px) {
  .finish-content {
    left: 16px;
    right: 16px;
    padding: 16px;
  }

  .finish-hash {
    font-size: 22px;
  }

  .finish-title {
    font-size: 26px;
  }

  .finish-channel-name {
    font-size: 14px;
  }
}
</style>
