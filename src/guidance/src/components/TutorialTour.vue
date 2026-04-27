<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import gsap from 'gsap'
import type { TutorialSlide, Expression } from '../types'
import { parseDescription, tokenCharCount, renderTokens } from '../utils/parser'
import ProgressBar from './ProgressBar.vue'
import CharacterSprite from './CharacterSprite.vue'
import DialogueBox from './DialogueBox.vue'

const props = defineProps<{
  slides: TutorialSlide[]
  feedbackExpression?: Expression
  isShowingFeedback?: boolean
}>()

const emit = defineEmits<{
  finish: []
  poke: []
  dragStart: []
  skipAttempt: [attempt: number]
  skipRequest: []
}>()

const currentIndex = ref(0)
const isAnimating = ref(false)
const titleRef = ref<HTMLElement | null>(null)
const descRef = ref<HTMLElement | null>(null)
const hashRef = ref<HTMLElement | null>(null)
const footerRef = ref<HTMLElement | null>(null)
const contentRef = ref<HTMLElement | null>(null)
const sceneRef = ref<HTMLElement | null>(null)
const currentSlide = ref<TutorialSlide | null>(null)
const currentExpression = ref<Expression>('normal')
const swipeHintOpacity = ref(1)
const revealedChars = ref(0)
const tutorialDialogueRef = ref<InstanceType<typeof DialogueBox> | null>(null)
const skipAttempt = ref(0)
const skipBtnRef = ref<HTMLElement | null>(null)
let typewriterInterval: ReturnType<typeof setInterval> | null = null

function onSkipAttempt() {
  if (skipAttempt.value < 3) {
    emit('skipAttempt', skipAttempt.value)

    if (skipBtnRef.value) {
      gsap.fromTo(skipBtnRef.value,
        { x: 0 },
        { x: 8, duration: 0.08, ease: 'none', yoyo: true, repeat: 5 },
      )
    }

    skipAttempt.value++
  } else {
    emit('skipRequest')
  }
}

const skipBtnLabel = computed(() => {
  if (skipAttempt.value === 0) return '跳过教程'
  if (skipAttempt.value === 1) return '真的要跳过吗？'
  if (skipAttempt.value === 2) return '最后一次机会……'
  return '跳过教程'
})

const displayExpression = computed<Expression>(() => {
  if (props.isShowingFeedback && props.feedbackExpression) {
    return props.feedbackExpression
  }
  return currentExpression.value
})

const currentTokens = computed(() => parseDescription(currentSlide.value?.description || ''))
const totalChars = computed(() => tokenCharCount(currentTokens.value))
const isTyping = computed(() => revealedChars.value < totalChars.value)
const renderedDesc = computed(() => {
  const html = renderTokens(currentTokens.value, revealedChars.value)
  return isTyping.value ? html + '<span class="typing-cursor">|</span>' : html
})

const SWIPE_THRESHOLD = 50

let touchStartX = 0
let touchStartY = 0
let isTrackingSwipe = false

function onTouchStart(e: TouchEvent) {
  if (isAnimating.value) return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
  isTrackingSwipe = true
}

function onTouchEnd(e: TouchEvent) {
  if (!isTrackingSwipe || isAnimating.value) return
  isTrackingSwipe = false
  const dx = e.changedTouches[0].clientX - touchStartX
  const dy = e.changedTouches[0].clientY - touchStartY
  if (Math.abs(dy) > Math.abs(dx)) return
  if (Math.abs(dx) < SWIPE_THRESHOLD) {
    if (isTyping.value) skipTypewriter()
    return
  }
  if (dx < 0) next()
  else prev()
  hideSwipeHint()
}

let mouseStartX = 0
let isTrackingMouse = false

function onMouseDown(e: MouseEvent) {
  if (isAnimating.value) return
  mouseStartX = e.clientX
  isTrackingMouse = true
}

function onMouseUp(e: MouseEvent) {
  if (!isTrackingMouse || isAnimating.value) return
  isTrackingMouse = false
  const dx = e.clientX - mouseStartX
  if (Math.abs(dx) < SWIPE_THRESHOLD) {
    if (isTyping.value) skipTypewriter()
    return
  }
  if (dx < 0) next()
  else prev()
  hideSwipeHint()
}

let descTouchStartX = 0
let descTouchStartY = 0
let descIsTracking = false

function onDescTouchStart(e: TouchEvent) {
  if (isAnimating.value) return
  descTouchStartX = e.touches[0].clientX
  descTouchStartY = e.touches[0].clientY
  descIsTracking = true
}

function onDescTouchEnd(e: TouchEvent) {
  if (!descIsTracking || isAnimating.value) return
  descIsTracking = false
  const dx = e.changedTouches[0].clientX - descTouchStartX
  const dy = e.changedTouches[0].clientY - descTouchStartY
  if (Math.abs(dy) > Math.abs(dx)) return
  if (Math.abs(dx) < SWIPE_THRESHOLD) {
    if (isTyping.value) skipTypewriter()
    return
  }
  if (dx < 0) next()
  else prev()
  hideSwipeHint()
}

let descMouseStartX = 0
let descIsTrackingMouse = false

function onDescMouseDown(e: MouseEvent) {
  if (isAnimating.value) return
  descMouseStartX = e.clientX
  descIsTrackingMouse = true
}

function onDescMouseUp(e: MouseEvent) {
  if (!descIsTrackingMouse || isAnimating.value) return
  descIsTrackingMouse = false
  const dx = e.clientX - descMouseStartX
  if (Math.abs(dx) < SWIPE_THRESHOLD) {
    if (isTyping.value) skipTypewriter()
    return
  }
  if (dx < 0) next()
  else prev()
  hideSwipeHint()
}

function hideSwipeHint() {
  if (swipeHintOpacity.value > 0) {
    gsap.to(swipeHintOpacity, { value: 0, duration: 0.3 })
  }
}

function startTypewriter(_text: string) {
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
    typewriterInterval = null
  }
  revealedChars.value = 0
  typewriterInterval = setInterval(() => {
    if (revealedChars.value < totalChars.value) {
      revealedChars.value++
    } else {
      if (typewriterInterval) {
        clearInterval(typewriterInterval)
        typewriterInterval = null
      }
    }
  }, 30)
}

function skipTypewriter() {
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
    typewriterInterval = null
  }
  revealedChars.value = totalChars.value
}

function animateContentIn() {
  const tl = gsap.timeline()

  if (hashRef.value) {
    tl.to(hashRef.value,
      { x: 0, opacity: 1, duration: 0.5, ease: 'back.out(1.8)' },
    )
  }

  if (titleRef.value) {
    tl.to(titleRef.value,
      { x: 0, opacity: 1, duration: 0.5, ease: 'power3.out' },
      '-=0.35',
    )
  }

  const accent = contentRef.value?.querySelector('.tutorial-accent-line') as HTMLElement
  if (accent) {
    tl.to(accent,
      { scaleX: 1, duration: 0.4, ease: 'power2.out' },
      '-=0.2',
    )
  }

  if (descRef.value) {
    tl.to(descRef.value,
      { x: 0, opacity: 1, duration: 0.5, ease: 'power2.out' },
      '-=0.2',
    )
  }

  if (footerRef.value) {
    tl.to(footerRef.value,
      { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' },
      '-=0.15',
    )
  }
}

function animateContentOut(direction: 'left' | 'right'): Promise<void> {
  const elements = [hashRef.value, titleRef.value, contentRef.value?.querySelector('.tutorial-accent-line'), descRef.value, footerRef.value].filter(Boolean) as HTMLElement[]
  if (elements.length === 0) return Promise.resolve()

  return new Promise((resolve) => {
    gsap.to(elements, {
      x: direction === 'left' ? -100 : 100,
      opacity: 0,
      duration: 0.3,
      ease: 'power2.in',
      stagger: 0.02,
      onComplete: resolve,
    })
  })
}

function setContentStartState(direction: 'left' | 'right') {
  const xVal = direction === 'left' ? 100 : -100
  const elements = [hashRef.value, titleRef.value, descRef.value, footerRef.value].filter(Boolean) as HTMLElement[]
  const accent = contentRef.value?.querySelector('.tutorial-accent-line') as HTMLElement
  if (accent) elements.push(accent)

  gsap.set(elements, { x: xVal, opacity: 0 })
}

async function showSlide(index: number) {
  if (index < 0 || index >= props.slides.length) return
  isAnimating.value = true

  const direction = index > currentIndex.value ? 'left' : 'right'

  if (typewriterInterval) {
    clearInterval(typewriterInterval)
    typewriterInterval = null
  }

  await animateContentOut(direction)

  currentIndex.value = index
  const slide = props.slides[index]
  currentSlide.value = slide
  currentExpression.value = slide.expression

  startTypewriter(slide.description)

  setContentStartState(direction)

  await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))

  animateContentIn()

  setTimeout(() => {
    isAnimating.value = false
  }, 900)
}

function next() {
  if (isAnimating.value) return
  if (currentIndex.value < props.slides.length - 1) {
    showSlide(currentIndex.value + 1)
  } else {
    emit('finish')
  }
}

function prev() {
  if (isAnimating.value) return
  if (currentIndex.value > 0) {
    showSlide(currentIndex.value - 1)
  }
}

onMounted(() => {
  if (props.slides.length > 0) {
    const slide = props.slides[0]
    currentSlide.value = slide
    currentExpression.value = slide.expression
    startTypewriter(slide.description)

    setContentStartState('left')
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        animateContentIn()
      })
    })
  }

  const el = sceneRef.value
  if (el) {
    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchend', onTouchEnd, { passive: true })
    el.addEventListener('mousedown', onMouseDown)
    el.addEventListener('mouseup', onMouseUp)
  }
})

onUnmounted(() => {
  const el = sceneRef.value
  if (el) {
    el.removeEventListener('touchstart', onTouchStart)
    el.removeEventListener('touchend', onTouchEnd)
    el.removeEventListener('mousedown', onMouseDown)
    el.removeEventListener('mouseup', onMouseUp)
  }
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
  }
})

defineExpose({ dialogueBoxRef: tutorialDialogueRef })
</script>

<template>
  <div ref="sceneRef" class="tutorial-scene" style="user-select: none; -webkit-user-select: none; cursor: grab;">
    <div class="tutorial-bg-fallback"></div>

    <CharacterSprite
      v-if="currentSlide"
      :expression="displayExpression"
      position="right"
      :scale="1"
      interactive
      @poke="emit('poke')"
      @drag-start="emit('dragStart')"
    />

    <ProgressBar :current="currentIndex + 1" :total="slides.length" />

    <div v-if="currentSlide" ref="contentRef" class="tutorial-content">
      <div class="tutorial-header">
        <span ref="hashRef" class="tutorial-hash">{{ currentSlide.icon || '#' }}</span>
        <h2 ref="titleRef" class="tutorial-title">{{ currentSlide.title }}</h2>
      </div>
      <div class="tutorial-accent-line"></div>
      <div ref="descRef" class="tutorial-description" v-html="renderedDesc" @touchstart.stop="onDescTouchStart" @touchend.stop="onDescTouchEnd" @mousedown.stop="onDescMouseDown" @mouseup.stop="onDescMouseUp"></div>
      <span ref="footerRef" class="tutorial-footer">{{ currentSlide.tip || '' }}</span>
    </div>

    <DialogueBox
      v-if="isShowingFeedback"
      ref="tutorialDialogueRef"
      text=""
      :expression="feedbackExpression || 'normal'"
      class="tutorial-feedback-dialogue"
    />

    <div class="tutorial-bottom">
      <span class="swipe-hint" :style="{ opacity: swipeHintOpacity }">
        ← 左右滑动切换 · 到最后一张继续滑动完成 →
      </span>
    </div>

    <button ref="skipBtnRef" class="tutorial-skip-btn" @click.stop="onSkipAttempt">{{ skipBtnLabel }}</button>
  </div>
</template>

<style scoped>
.tutorial-scene {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 30px 60px 40px;
  position: relative;
  overflow: hidden;
}

.tutorial-bg-fallback {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, #FFF8F0, #FFEDE0);
  z-index: 0;
}

.tutorial-content {
  position: relative;
  z-index: 5;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding-top: 20px;
  max-width: 680px;
  padding-left: 20px;
  min-height: 0;
}

.tutorial-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}

.tutorial-hash {
  font-size: 36px;
  font-weight: 900;
  color: var(--accent-gold);
  line-height: 1;
  text-shadow: 0 2px 12px rgba(206, 66, 43, 0.3);
  will-change: transform, opacity;
  backface-visibility: hidden;
}

.tutorial-title {
  font-size: 42px;
  font-weight: 900;
  color: var(--text-primary);
  line-height: 1.1;
  letter-spacing: -1px;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.06);
  will-change: transform, opacity;
  backface-visibility: hidden;
}

.tutorial-accent-line {
  width: 80px;
  height: 3px;
  background: var(--accent-gold);
  transform-origin: left center;
  margin-bottom: 14px;
  border-radius: 2px;
  will-change: transform;
}

.tutorial-description {
  font-size: 18px;
  line-height: 1.8;
  color: var(--text-primary);
  max-width: 560px;
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  min-height: 0;
  will-change: transform, opacity;
  backface-visibility: hidden;
}

.tutorial-description::-webkit-scrollbar {
  display: none;
}

.tutorial-description :deep(.desc-bold) {
  font-weight: 700;
  color: var(--text-primary);
}

.tutorial-description :deep(.desc-accent) {
  color: var(--accent-gold);
  font-weight: 600;
}

.tutorial-description :deep(.desc-gap) {
  display: block;
  height: 12px;
}

.tutorial-description :deep(.desc-separator) {
  display: block;
  height: 1px;
  background: linear-gradient(90deg, var(--accent-gold), transparent);
  margin: 10px 0;
  opacity: 0.4;
}

.tutorial-description :deep(.desc-warning) {
  display: inline;
  background: rgba(206, 66, 43, 0.08);
  color: var(--accent-gold);
  font-weight: 600;
  padding: 1px 6px;
  border-left: 3px solid var(--accent-gold);
  margin-left: 4px;
  border-radius: 0 3px 3px 0;
}

.typing-cursor {
  animation: blink 0.8s step-end infinite;
  color: var(--accent-gold);
  font-weight: 300;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.tutorial-footer {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  margin-top: 12px;
  flex-shrink: 0;
  will-change: transform, opacity;
  backface-visibility: hidden;
}

.tutorial-bottom {
  display: flex;
  justify-content: center;
  z-index: 5;
  padding-bottom: 10px;
  pointer-events: none;
}

.tutorial-skip-btn {
  position: absolute;
  top: 34px;
  right: 60px;
  z-index: 15;
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: 12px;
  padding: 6px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  letter-spacing: 0.5px;
  border-radius: 0;
  white-space: nowrap;
}

.tutorial-skip-btn:hover {
  border-color: var(--accent-gold);
  color: var(--accent-gold);
}

.swipe-hint {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  transition: opacity 0.3s;
}

.tutorial-feedback-dialogue {
  pointer-events: none;
}

@media (max-width: 768px) {
  .tutorial-scene {
    padding: 50px 20px 20px;
  }

  .tutorial-content {
    padding-left: 0;
  }

  .tutorial-hash {
    font-size: 24px;
  }

  .tutorial-title {
    font-size: 28px;
  }

  .tutorial-description {
    font-size: 15px;
  }

  .tutorial-bottom {
    position: absolute;
    bottom: 170px;
    left: 0;
    right: 0;
    padding-bottom: 0;
  }

  .tutorial-skip-btn {
    top: 52px;
    right: 16px;
    font-size: 11px;
    padding: 4px 10px;
  }
}
</style>
