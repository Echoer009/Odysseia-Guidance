<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import gsap from 'gsap'
import type { SceneName, Expression, TourSlide } from './types'
import { welcomeDialogues, selectionHint, tourStartDialogue, tutorialStartDialogue } from './data/dialogues'
import { buildTourQueue } from './data/channelData'
import { tutorialSlides } from './data/tutorialConfig'
import { parseDescription, renderTokens } from './utils/parser'
import { cloudAssets, backgroundAssets, expressions } from './data/assetsConfig'
import { useSceneFeedback } from './composables/useSceneFeedback'
import { getKickoutLine, getKickoutMutter } from './data/pokeDialogues'
import { setupChildBridge } from './child-bridge'
import CharacterSprite from './components/CharacterSprite.vue'
import DialogueBox from './components/DialogueBox.vue'
import CardSelect from './components/CardSelect.vue'
import ChannelTour from './components/ChannelTour.vue'
import TutorialTour from './components/TutorialTour.vue'

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

const finishChannels = ref<{ name: string; channelId: string; description: string }[]>([])
const expandedChannelId = ref<string | null>(null)
const petalContainer = ref<HTMLElement | null>(null)
const awakeOverlayRef = ref<HTMLElement | null>(null)
const welcomeDialogueRef = ref<InstanceType<typeof DialogueBox> | null>(null)
const cardSelectRef = ref<InstanceType<typeof CardSelect> | null>(null)
const selectionDialogueRef = ref<InstanceType<typeof DialogueBox> | null>(null)
const channelTourRef = ref<InstanceType<typeof ChannelTour> | null>(null)
const tutorialTourRef = ref<InstanceType<typeof TutorialTour> | null>(null)
const finishDialogueRef = ref<InstanceType<typeof DialogueBox> | null>(null)

const queryParams = new URLSearchParams(window.location.search)
const isEmbedded = queryParams.get('frame_id') != null

let accessToken: string | null = null

const baseUrl = import.meta.env.BASE_URL

const skyBgLoaded = ref(false)
const finishBgLoaded = ref(false)
const finishBgReady = ref(false)

function getDialogueRef() {
  if (currentScene.value === 'welcome') return welcomeDialogueRef.value
  if (currentScene.value === 'selection') return selectionDialogueRef.value
  if (currentScene.value === 'tour') return channelTourRef.value?.dialogueBoxRef ?? null
  if (currentScene.value === 'tutorial') return tutorialTourRef.value?.dialogueBoxRef ?? null
  if (currentScene.value === 'finish') return finishDialogueRef.value
  return null
}

const {
  isShowingFeedback,
  reactionBubbleText,
  reactionBubbleVisible,
  handleInteraction,
  showReactionDialogue,
} = useSceneFeedback(
  currentScene,
  currentExpression,
  currentImage,
  currentDialogue,
  getDialogueRef,
)

const kickoutLine = ref('')
const kickoutMutter = ref('')
const kickoutRef = ref<HTMLElement | null>(null)

  function tryLoadBg(url: string): Promise<boolean> {
    return new Promise((resolve) => {
      const img = new Image()
      img.onload = () => resolve(true)
      img.onerror = () => { console.warn('[BG] Failed to load:', url); resolve(false) }
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
  if (finishOk) finishBgReady.value = true
}

function handleCloudError(event: Event) {
  const el = event.target as HTMLElement
  if (el.parentElement) el.parentElement.style.display = 'none'
}

async function apiCall(endpoint: string, method: 'GET' | 'POST', body?: object, retries = 2) {
  if (!accessToken && isEmbedded) {
    throw new Error('Access Token is not available in embedded mode.')
  }

  for (let i = 0; i <= retries; i++) {
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      }
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`
      }

      const response = await fetch(baseUrl + endpoint.replace(/^\//, ''), {
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
  console.log('[SDK] Importing Discord SDK...')
  const { DiscordSDK } = await import('@discord/embedded-app-sdk')
  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID
  if (!clientId) {
    console.error('[SDK] VITE_DISCORD_CLIENT_ID is not set')
    throw new Error('VITE_DISCORD_CLIENT_ID is not set.')
  }
  console.log('[SDK] Client ID:', clientId)

  const discordSdk = new DiscordSDK(clientId)
  console.log('[SDK] Waiting for ready...')
  await discordSdk.ready()
  console.log('[SDK] Ready.')

  console.log('[SDK] Authorizing...')
  const { code } = await discordSdk.commands.authorize({
    client_id: discordSdk.clientId,
    response_type: 'code',
    state: '',
    prompt: 'none',
    scope: ['identify', 'guilds'],
  })
  console.log('[SDK] Authorized, exchanging token...')

  const response = await fetch(baseUrl + 'api/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  if (!response.ok) {
    const text = await response.text()
    console.error('[SDK] Token exchange failed:', response.status, text)
    throw new Error(`Token exchange failed: ${response.status}`)
  }
  const { access_token } = await response.json()
  console.log('[SDK] Token obtained, authenticating...')

  const auth = await discordSdk.commands.authenticate({ access_token })
  if (!auth) {
    console.error('[SDK] Authenticate returned null')
    throw new Error('Authenticate command failed')
  }

  accessToken = access_token
  if (auth.user?.username) {
    userName.value = auth.user.username
  }
  console.log('[SDK] Fully initialized. User:', auth.user?.username)
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

  images.push(`${baseUrl}assets/characters/annoyed.webp`)
  images.push(`${baseUrl}assets/characters/angry.webp`)
  images.push(`${baseUrl}assets/characters/furious.webp`)
  images.push(`${baseUrl}assets/characters/ignore.webp`)

  cloudAssets.forEach(c => {
    images.push(`${baseUrl}assets/clouds/${c.file}`)
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

function onPoke() {
  handleInteraction('poke')
}

function onDragStart() {
  handleInteraction('drag')
}

watch(currentScene, (scene) => {
  if (scene === 'kickout') {
    kickoutLine.value = getKickoutLine()
    kickoutMutter.value = getKickoutMutter()
  }
})

function onWelcomeSceneClick() {
  if (isShowingFeedback.value) return
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

function onSelectionDialogueAdvance() {
  if (!dialogueComplete.value) {
    selectionDialogueRef.value?.skipToEnd()
  } else {
    onTagConfirm(Array.from((cardSelectRef.value as any)?.selectedTags?.value ?? ['默认']))
  }
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
  transitionTo('tutorial')
  currentDialogue.value = tutorialStartDialogue.text
  currentExpression.value = tutorialStartDialogue.expression
  currentImage.value = tutorialStartDialogue.image
}

const SKIP_BLOCK_MESSAGES: { text: string; expression: Expression }[] = [
  { text: '诶！不要跳过教程啦！很重要的！', expression: 'surprised' },
  { text: '你真的要跳过吗……？我花了好久准备的……', expression: 'sad' },
  { text: '好吧好吧……随你便吧……哼！', expression: 'annoyed' },
]

function onSkipAttempt(attempt: number) {
  const block = SKIP_BLOCK_MESSAGES[attempt]
  if (block) {
    showReactionDialogue(block.text, block.expression, 0, 0)
  }
}

function onTutorialFinish() {
  finishChannels.value = channelsQueue.value.map(s => ({
    name: s.channelName,
    channelId: s.channelId,
    description: s.description,
  }))

  currentExpression.value = 'happy'
  currentDialogue.value = ''
  currentImage.value = undefined
  dialogueComplete.value = true

  transitionTo('finish')

  setTimeout(() => {
    createPetals()
  }, 500)

  setTimeout(() => {
    animateFinishContent()
  }, 200)
}

function toggleChannelExpand(ch: { channelId: string }) {
  if (expandedChannelId.value === ch.channelId) {
    expandedChannelId.value = null
  } else {
    expandedChannelId.value = ch.channelId
  }
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
      const bridgeData = await setupChildBridge()
      if (bridgeData) {
        accessToken = bridgeData.accessToken
        if (bridgeData.user?.username) userName.value = bridgeData.user.username
      } else if (isEmbedded) {
        await setupDiscordSdk()
      }
      await fetchUserInfo()
    } catch (e: unknown) {
      console.error('Init error:', e)
    }

    await initBackgrounds()
    await preloadAssets()

    setTimeout(() => {
      startWelcome()
    }, 300)
  }

onMounted(main)
</script>

<template>
  <div class="app-root">
    <div ref="awakeOverlayRef" class="awake-overlay"></div>

    <div
      v-if="finishBgReady"
      class="persistent-bg-finish"
      :class="{ 'persistent-bg-finish--active': currentScene === 'finish' }"
      :style="{ '--bg-image': `url(${backgroundAssets.finish})` }"
    ></div>

    <div
      v-if="currentScene === 'loading'"
      class="scene scene-loading"
    >
        <div class="loading-content">
          <div class="loading-sunflower">☀️</div>
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
          :src="baseUrl + 'assets/clouds/' + cloud.file"
          alt=""
          @error="handleCloudError"
        />
      </div>

      <CharacterSprite :expression="currentExpression" :custom-src="currentImage" position="right" :scale="1" interactive @poke="onPoke" @drag-start="onDragStart" />

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
      class="scene scene-clickable"
      :class="skyBgLoaded ? 'bg-sky' : 'bg-sky-fallback'"
      :style="skyBgLoaded ? { '--bg-image': `url(${backgroundAssets.sky})` } : {}"
      @click="onSelectionDialogueAdvance"
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
          :src="baseUrl + 'assets/clouds/' + cloud.file"
          alt=""
          @error="handleCloudError"
        />
      </div>

      <CharacterSprite :expression="currentExpression" :custom-src="currentImage" position="right" :scale="1" skip-entrance interactive @poke="onPoke" @drag-start="onDragStart" />

      <DialogueBox
        ref="selectionDialogueRef"
        :text="currentDialogue"
        :expression="currentExpression"
        :clickable="true"
        speaker="类脑娘"
        @advance="onSelectionDialogueAdvance"
        @complete="onDialogueComplete"
      />

      <CardSelect ref="cardSelectRef" :fly-origin="charOrigin" @tag-comment="onTagComment" />
    </div>

    <div v-else-if="currentScene === 'tour'" class="scene">
      <ChannelTour ref="channelTourRef" :slides="channelsQueue" :feedback-expression="currentExpression" :is-showing-feedback="isShowingFeedback" @finish="onTourFinish" @poke="onPoke" @drag-start="onDragStart" />
    </div>

    <div v-else-if="currentScene === 'tutorial'" class="scene">
      <TutorialTour ref="tutorialTourRef" :slides="tutorialSlides" :feedback-expression="currentExpression" :is-showing-feedback="isShowingFeedback" @finish="onTutorialFinish" @poke="onPoke" @drag-start="onDragStart" @skip-attempt="onSkipAttempt" @skip-request="onTutorialFinish" />
    </div>

    <div
      v-else-if="currentScene === 'finish'"
      class="scene scene-transparent"
    >
      <div ref="petalContainer" class="petal-container"></div>

      <CharacterSprite :expression="currentExpression" position="right" :scale="1" interactive @poke="onPoke" @drag-start="onDragStart" />

      <DialogueBox
        v-if="isShowingFeedback"
        ref="finishDialogueRef"
        text=""
        :expression="currentExpression"
      />

      <div class="finish-content">
        <div class="finish-header">
          <span class="finish-hash">#</span>
          <h2 ref="finishTitleRef" class="finish-title">引导完成</h2>
        </div>
        <div class="finish-accent-line"></div>
        <p class="finish-subtitle">以下是为你推荐的频道</p>

        <div class="finish-channels">
          <div
            v-for="ch in finishChannels"
            :key="ch.channelId"
            :data-channel-id="ch.channelId"
            class="finish-channel-item"
            :class="{ expanded: expandedChannelId === ch.channelId }"
            @click="toggleChannelExpand(ch)"
          >
            <div class="finish-channel-header">
              <span class="finish-channel-hash">#</span>
              <span class="finish-channel-name">{{ ch.name }}</span>
              <span class="finish-channel-arrow" :class="{ rotated: expandedChannelId === ch.channelId }">▾</span>
            </div>
            <div class="finish-channel-desc" :class="{ open: expandedChannelId === ch.channelId }" v-html="renderTokens(parseDescription(ch.description), Infinity)" />
          </div>
        </div>
      </div>
    </div>

    <div
      v-else-if="currentScene === 'kickout'"
      ref="kickoutRef"
      class="scene scene-kickout"
    >
      <CharacterSprite expression="angry" position="right" :scale="1" :custom-src="`${baseUrl}assets/characters/ignore.webp`" />

      <div class="kickout-content">
        <div class="kickout-stamp">你已被踢出引导</div>
        <div class="kickout-divider"></div>
        <p class="kickout-mutter">「{{ kickoutMutter }}」</p>
      </div>
    </div>

    <div
      v-if="reactionBubbleVisible"
      class="reaction-bubble"
    >
      {{ reactionBubbleText }}
    </div>
  </div>
</template>

<style>
.scene-clickable {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
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

.persistent-bg-finish {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-image: var(--bg-image);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  opacity: 0;
  transition: opacity 0.4s ease;
}

.persistent-bg-finish--active {
  opacity: 1;
}

.scene-transparent {
  background: transparent !important;
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
  display: flex;
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
  flex-direction: column;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  color: var(--text-primary);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.finish-channel-item:hover {
  border-color: var(--accent-gold);
  box-shadow: 0 4px 16px rgba(206, 66, 43, 0.12);
}

.finish-channel-item.expanded {
  border-color: var(--accent-gold);
}

.finish-channel-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
}

.finish-channel-item:hover .finish-channel-header {
  transform: translateX(4px);
  transition: transform 0.2s ease;
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.finish-channel-arrow {
  color: var(--accent-gold);
  font-size: 14px;
  transition: transform 0.25s ease;
  flex-shrink: 0;
}

.finish-channel-arrow.rotated {
  transform: rotate(180deg);
}

.finish-channel-desc {
  max-height: 0;
  overflow: hidden;
  padding: 0 18px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  transition: max-height 0.3s ease, padding 0.3s ease;
}

.finish-channel-desc.open {
  max-height: 500px;
  padding: 0 18px 16px 18px;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.finish-channel-desc.open::-webkit-scrollbar {
  display: none;
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

  .finish-channel-desc.open {
    max-height: 400px;
  }
}

.reaction-bubble {
  position: absolute;
  bottom: 260px;
  right: 80px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  padding: 12px 20px;
  font-size: 15px;
  color: var(--text-primary);
  z-index: 30;
  box-shadow: var(--shadow-float);
  animation: bubble-in 0.3s ease-out;
  pointer-events: none;
  max-width: 280px;
  text-align: center;
}

@keyframes bubble-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.scene-kickout {
  background: #0A0A0A;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kickout-content {
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

.kickout-stamp {
  font-size: 40px;
  font-weight: 900;
  color: #FF4444;
  letter-spacing: -1px;
  text-shadow: 0 0 40px rgba(255, 68, 68, 0.4), 0 2px 4px rgba(0, 0, 0, 0.8);
  line-height: 1.2;
}

.kickout-divider {
  width: 60px;
  height: 3px;
  background: #FF4444;
  margin: 20px 0;
  border-radius: 2px;
  opacity: 0.6;
}

.kickout-mutter {
  font-size: 15px;
  color: #666;
  line-height: 1.8;
  max-width: 400px;
  font-style: italic;
}

@media (max-width: 768px) {
  .reaction-bubble {
    bottom: 200px;
    right: 40px;
    font-size: 13px;
    max-width: 200px;
  }

  .kickout-content {
    left: 16px;
    right: 16px;
    padding: 16px;
    top: auto;
    bottom: 200px;
    transform: none;
    align-items: center;
    text-align: center;
  }

  .kickout-stamp {
    font-size: 28px;
  }

  .kickout-mutter {
    font-size: 13px;
    text-align: center;
  }
}
</style>
