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
  stopIdle()
  idleTween = gsap.fromTo(spriteRef.value,
    { y: 0 },
    {
      y: 2,
      duration: 1.2,
      yoyo: true,
      repeat: -1,
      ease: 'sine.inOut',
    },
  )
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
  gsap.set(spriteRef.value, { x: 200, opacity: 0, scale: props.scale || 1 })
  gsap.to(spriteRef.value, {
    x: 0,
    opacity: 1,
    scale: props.scale || 1,
    duration: 0.6,
    ease: 'back.out(1.4)',
    onComplete: startIdle,
  })
}

function animateExpressionChange(onSwitch?: () => void) {
  if (!innerRef.value) return
  isChanging.value = true
  const el = innerRef.value
  let switched = false
  const doSwitch = () => {
    if (!switched) {
      switched = true
      onSwitch?.()
    }
  }
  gsap.timeline()
    .to(el, { scaleX: 0, duration: 0.12, ease: 'power2.in', onComplete: doSwitch })
    .to(el, { scaleX: 1.08, scaleY: 0.94, duration: 0.1, ease: 'power2.out' })
    .to(el, { scaleX: 0.98, scaleY: 1.02, duration: 0.1, ease: 'power2.inOut' })
    .to(el, { scaleX: 1, scaleY: 1, duration: 0.15, ease: 'elastic.out(1, 0.5)' })
    .then(() => { isChanging.value = false })
}

function switchToImage(src: string) {
  imgFailed.value = false
  imgSrc.value = src
}

function handleImgError() {
  imgFailed.value = true
  imgSrc.value = ''
}

function changeExpression(newSrc: string) {
  if (newSrc === imgSrc.value) {
    animateExpressionChange()
    return
  }

  const probe = new Image()
  probe.onload = () => {
    if (isChanging.value) {
      return
    }
    animateExpressionChange(() => switchToImage(newSrc))
  }
  probe.onerror = () => {}
  probe.src = newSrc
}

function updateImage() {
  if (props.customSrc) {
    changeExpression(props.customSrc)
  } else {
    changeExpression(getImgPath(props.expression))
  }
}

let isDragging = false
let isPointerDown = false
let dragStartPos = { x: 0, y: 0 }
const DRAG_THRESHOLD = 10

function onPointerDown(e: PointerEvent) {
  if (!props.interactive) return
  isPointerDown = true
  isDragging = false
  dragStartPos = { x: e.clientX, y: e.clientY }
  stopIdle()
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!props.interactive || !isPointerDown) return
  const dx = e.clientX - dragStartPos.x
  const dy = e.clientY - dragStartPos.y
  if (!isDragging && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
    isDragging = true
    emit('dragStart')
  }
  if (!isDragging) return
  const el = spriteRef.value
  if (!el) return
  gsap.set(el, {
    x: dx * 0.5,
    y: dy * 0.5,
  })
}

function onPointerUp(_e: PointerEvent) {
  if (!props.interactive || !isPointerDown) return
  isPointerDown = false
  const el = spriteRef.value

  if (isDragging) {
    if (el) {
      gsap.to(el, { x: 0, y: 0, duration: 0.4, ease: 'elastic.out(1, 0.5)', onComplete: startIdle })
    } else {
      startIdle()
    }
    emit('dragEnd')
  } else {
    startIdle()
    emit('poke')
  }

  isDragging = false
}

watch(() => props.expression, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    updateImage()
  }
})
watch(() => props.customSrc, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    updateImage()
  }
})

onMounted(() => {
  if (spriteRef.value) {
    gsap.set(spriteRef.value, { scale: props.scale || 1 })
  }
  const src = props.customSrc || getImgPath(props.expression)
  imgSrc.value = src
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
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @dragstart.prevent
    @click.stop
  >
    <div ref="innerRef" class="sprite-inner">
      <div v-if="!imgSrc || imgFailed" class="sprite-placeholder" :style="{ borderColor }">
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
  -webkit-tap-highlight-color: transparent;
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
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
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
    width: 140px;
    height: 140px;
  }

  .sprite-icon {
    font-size: 28px;
  }

  .sprite-image {
    height: 140px;
    width: 140px;
  }
}
</style>
