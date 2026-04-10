<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import gsap from 'gsap'
import type { Expression } from '../types'
import { getExpressionPath, getExpressionColor, getExpressionLabel } from '../data/assetsConfig'

const props = defineProps<{
  expression: Expression
  scale?: number
  position?: 'right' | 'center' | 'right-small'
  customSrc?: string
  skipEntrance?: boolean
  interactive?: boolean
}>()

const emit = defineEmits<{
  poke: []
  dragStart: []
  dragEnd: []
}>()

const spriteRef = ref<HTMLElement | null>(null)
const innerRef = ref<HTMLElement | null>(null)
const imgSrc = ref('')
const imgFailed = ref(false)
let idleTween: gsap.core.Tween | null = null
let isChanging = ref(false)

const borderColor = computed(() => getExpressionColor(props.expression))
const exprLabel = computed(() => getExpressionLabel(props.expression))

function getImgPath(expr: Expression): string {
  return getExpressionPath(expr) || `/assets/characters/${expr}.webp`
}

function startIdle() {
  if (!spriteRef.value) return
  idleTween = gsap.to(spriteRef.value, {
    y: '+=2',
    duration: 1.2,
    yoyo: true,
    repeat: -1,
    ease: 'sine.inOut',
  })
}

function stopIdle() {
  if (idleTween) {
    idleTween.kill()
    idleTween = null
  }
}

function animateEntrance() {
  if (!spriteRef.value) return
  stopIdle()
  gsap.set(spriteRef.value, { x: 200, opacity: 0, scale: 0.9 })
  gsap.to(spriteRef.value, {
    x: 0,
    opacity: 1,
    scale: 1,
    duration: 0.6,
    ease: 'back.out(1.4)',
    onComplete: startIdle,
  })
}

function animateExpressionChange() {
  if (!innerRef.value) return
  isChanging.value = true
  const el = innerRef.value
  gsap.timeline()
    .to(el, { scaleX: 0.92, scaleY: 1.06, duration: 0.12, ease: 'power2.in' })
    .to(el, { scaleX: 1.08, scaleY: 0.94, duration: 0.1, ease: 'power2.out' })
    .to(el, { scaleX: 0.98, scaleY: 1.02, duration: 0.1, ease: 'power2.inOut' })
    .to(el, { scaleX: 1, scaleY: 1, duration: 0.15, ease: 'elastic.out(1, 0.5)' })
    .then(() => { isChanging.value = false })
}

function tryLoadImage(src: string) {
  if (imgSrc.value === src) return
  imgFailed.value = false
  imgSrc.value = src
}

function handleImgError() {
  imgFailed.value = true
  imgSrc.value = ''
}

function updateImage() {
  if (props.customSrc) {
    tryLoadImage(props.customSrc)
  } else {
    tryLoadImage(getImgPath(props.expression))
  }
}

let isDragging = false
let dragStartPos = { x: 0, y: 0 }
const DRAG_THRESHOLD = 10

function onPointerDown(e: PointerEvent) {
  if (!props.interactive) return
  isDragging = false
  dragStartPos = { x: e.clientX, y: e.clientY }
  emit('dragStart')
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!props.interactive || !isDragging) return
  const el = spriteRef.value
  if (!el) return
  gsap.to(el, {
    x: (e.clientX - dragStartPos.x) * 0.5,
    y: (e.clientY - dragStartPos.y) * 0.5,
    duration: 0.1,
    ease: 'power1.out',
    overwrite: true,
  })
}

function onPointerUp(e: PointerEvent) {
  if (!props.interactive) return
  const el = spriteRef.value
  if (el) {
    gsap.to(el, { x: 0, y: 0, duration: 0.4, ease: 'elastic.out(1, 0.5)' })
  }
  emit('dragEnd')
  const dx = e.clientX - dragStartPos.x
  const dy = e.clientY - dragStartPos.y
  if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) {
    isDragging = true
  }
  if (!isDragging) {
    emit('poke')
  }
  isDragging = false
}

watch(() => props.expression, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    animateExpressionChange()
  }
  updateImage()
})
watch(() => props.customSrc, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    animateExpressionChange()
  }
  updateImage()
})

onMounted(() => {
  updateImage()
  if (props.skipEntrance) {
    startIdle()
  } else {
    animateEntrance()
  }
})

onUnmounted(() => {
  stopIdle()
})

defineExpose({ animateEntrance })
</script>

<template>
  <div
    ref="spriteRef"
    class="character-sprite"
    :class="[position || 'right', { interactive }]"
    :style="{ transform: `scale(${scale || 1})` }"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
  >
    <div ref="innerRef" class="sprite-inner">
      <div v-if="!imgSrc" class="sprite-placeholder" :style="{ borderColor }">
        <span class="sprite-icon">🌻</span>
        <span class="sprite-expr">{{ exprLabel }}</span>
      </div>
      <img
        v-else
        :src="imgSrc"
        :alt="expression"
        class="sprite-image"
        @error="handleImgError"
      />
    </div>
  </div>
</template>

<style scoped>
.character-sprite {
  position: absolute;
  z-index: 10;
  pointer-events: none;
  will-change: transform;
}

.character-sprite.interactive {
  pointer-events: auto;
  cursor: pointer;
  touch-action: none;
}

.character-sprite.right {
  right: 30px;
  bottom: 0;
}

.character-sprite.right-small {
  right: 10px;
  bottom: 0;
}

.character-sprite.center {
  left: 50%;
  bottom: 0;
  transform-origin: bottom center;
  margin-left: -130px;
}

.sprite-inner {
  will-change: transform;
  transform-origin: center bottom;
}

.sprite-placeholder {
  width: 380px;
  height: 380px;
  border: 2px solid;
  background: var(--card-bg-solid);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  box-shadow: var(--shadow-normal);
}

.sprite-icon {
  font-size: 72px;
}

.sprite-expr {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 1px;
}

.sprite-image {
  height: 380px;
  width: 380px;
  object-fit: contain;
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.1));
}

@media (max-width: 768px) {
  .character-sprite.right {
    right: 5px;
    bottom: 0;
  }

  .character-sprite.right-small {
    right: 0;
    bottom: 0;
  }

  .sprite-placeholder {
    width: 180px;
    height: 180px;
  }

  .sprite-icon {
    font-size: 36px;
  }

  .sprite-image {
    height: 180px;
    width: 180px;
  }
}
</style>
