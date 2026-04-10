<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import gsap from 'gsap'
import type { TagConfig } from '../types'
import { tagsConfig } from '../data/tagsConfig'

const props = defineProps<{
  flyOrigin?: { x: number; y: number } | null
}>()

const emit = defineEmits<{
  confirm: [tags: string[]]
  tagComment: [tagName: string, comment: string, expression: string]
}>()

const selectedTags = ref<Set<string>>(new Set(['默认']))
const cardsRef = ref<HTMLElement | null>(null)
const confirmBtnRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const tags = tagsConfig.filter(t => !t.isDefault)
const flippingCards = ref<Set<string>>(new Set())
const isAnimatingIn = ref(true)

const rotations = tags.map(() => (Math.random() - 0.5) * 6)

const tagColors: Record<string, string> = {
  '默认': '#CE422B',
  '男性向': '#B7410E',
  '女性向': '#E25822',
  '纯净向': '#D4652F',
  '深渊': '#A0340F',
  '聊聊天': '#E8751A',
  '其他分区': '#C2452D',
  'AI绘图': '#F07623',
  '酒馆美化': '#9E3A22',
  '档案馆': '#8B3A1A',
}

const tagLabels: Record<string, string> = {
  '默认': 'HOME',
  '男性向': 'M',
  '女性向': 'F',
  '纯净向': 'P',
  '深渊': 'A',
  '聊聊天': 'T',
  '其他分区': '+',
  'AI绘图': 'AI',
  '酒馆美化': 'UI',
  '档案馆': 'ARC',
}

const orangePalette = ['#FFB347', '#FF8C42', '#E25822', '#CE422B', '#A0340F', '#8B1A1A']
const orangePaletteRGB = orangePalette.map(hex => {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return { r, g, b }
})

interface CanvasParticle {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  color: { r: number; g: number; b: number }
  opacity: number
  rotation: number
  rotationSpeed: number
  life: number
  maxLife: number
  gravity: number
  scale: number
}

let particles: CanvasParticle[] = []
let animFrameId: number | null = null

const STAR_PATH = [
  [0.5, 0], [0.61, 0.35], [0.98, 0.35], [0.68, 0.57],
  [0.79, 0.91], [0.5, 0.7], [0.21, 0.91], [0.32, 0.57],
  [0.02, 0.35], [0.39, 0.35],
]

function drawStar(ctx: CanvasRenderingContext2D, p: CanvasParticle) {
  const s = p.size * p.scale
  if (s < 0.5) return
  ctx.save()
  ctx.translate(p.x, p.y)
  ctx.rotate(p.rotation)
  ctx.globalAlpha = Math.max(0, Math.min(1, p.opacity))
  ctx.fillStyle = `rgb(${p.color.r},${p.color.g},${p.color.b})`
  ctx.shadowColor = `rgba(${p.color.r},${p.color.g},${p.color.b},0.6)`
  ctx.shadowBlur = s * 0.8
  ctx.beginPath()
  for (let i = 0; i < STAR_PATH.length; i++) {
    const px = (STAR_PATH[i][0] - 0.5) * s
    const py = (STAR_PATH[i][1] - 0.5) * s
    if (i === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  }
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}

function spawnFireEdge(ox: number, oy: number, cw: number, ch: number) {
  const count = 20
  const perimeter = 2 * (cw + ch)
  for (let i = 0; i < count; i++) {
    const t = i / count
    const pos = t * perimeter
    let px: number, py: number
    if (pos < cw) { px = ox - cw / 2 + pos; py = oy - ch / 2 }
    else if (pos < cw + ch) { px = ox + cw / 2; py = oy - ch / 2 + (pos - cw) }
    else if (pos < 2 * cw + ch) { px = ox + cw / 2 - (pos - cw - ch); py = oy + ch / 2 }
    else { px = ox - cw / 2; py = oy + ch / 2 - (pos - 2 * cw - ch) }

    const life = 0.4 + Math.random() * 0.2
    particles.push({
      x: px, y: py,
      vx: (Math.random() - 0.5) * 10,
      vy: -(15 + Math.random() * 25),
      size: 5 + Math.random() * 6,
      color: orangePaletteRGB[Math.floor(Math.random() * orangePaletteRGB.length)],
      opacity: 1,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 8,
      life, maxLife: life,
      gravity: 10,
      scale: 0.3,
    })
  }
}

function spawnBurst(ox: number, oy: number) {
  const count = 28
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.6
    const speed = 120 + Math.random() * 160
    const life = 1.0 + Math.random() * 0.6
    particles.push({
      x: ox, y: oy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: 6 + Math.random() * 10,
      color: orangePaletteRGB[Math.floor(Math.random() * orangePaletteRGB.length)],
      opacity: 1,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 12,
      life, maxLife: life,
      gravity: 60,
      scale: 0.2,
    })
  }
}

function spawnEmbers(ox: number, oy: number) {
  const count = 14
  for (let i = 0; i < count; i++) {
    const life = 1.4 + Math.random() * 0.8
    particles.push({
      x: ox + (Math.random() - 0.5) * 40,
      y: oy + (Math.random() - 0.5) * 20,
      vx: (Math.random() - 0.5) * 30,
      vy: -(80 + Math.random() * 120),
      size: 3 + Math.random() * 5,
      color: orangePaletteRGB[Math.floor(Math.random() * orangePaletteRGB.length)],
      opacity: 0.8,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 4,
      life, maxLife: life,
      gravity: -10,
      scale: 1,
    })
  }
}

function updateAndDraw(ctx: CanvasRenderingContext2D, dt: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  let alive = 0
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.life -= dt
    if (p.life <= 0) {
      particles[i] = particles[particles.length - 1]
      particles.pop()
      continue
    }
    alive++
    const t = 1 - p.life / p.maxLife
    p.vy += p.gravity * dt
    p.x += p.vx * dt
    p.y += p.vy * dt
    p.rotation += p.rotationSpeed * dt
    p.vx *= 0.98
    p.opacity = t < 0.15 ? t / 0.15 : Math.max(0, 1 - (t - 0.15) / 0.85)
    p.scale = t < 0.15 ? 0.3 + (t / 0.15) * 1.2 : 1.5 * (1 - (t - 0.15) / 0.85) + 0.1
    drawStar(ctx, p)
  }

  if (alive === 0) {
    if (animFrameId !== null) {
      cancelAnimationFrame(animFrameId)
      animFrameId = null
    }
  }
}

let lastFrameTime = 0

function animationLoop(timestamp: number) {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  if (lastFrameTime === 0) lastFrameTime = timestamp
  const dt = Math.min((timestamp - lastFrameTime) / 1000, 0.05)
  lastFrameTime = timestamp

  updateAndDraw(ctx, dt)

  if (particles.length > 0) {
    animFrameId = requestAnimationFrame(animationLoop)
  } else {
    animFrameId = null
    lastFrameTime = 0
  }
}

function ensureLoop() {
  if (animFrameId === null) {
    lastFrameTime = 0
    animFrameId = requestAnimationFrame(animationLoop)
  }
}

function spawnParticles(_tagName: string, originX: number, originY: number, cardW: number, cardH: number) {
  const maxParticles = 150
  if (particles.length > maxParticles) {
    particles.splice(0, particles.length - 60)
  }

  spawnFireEdge(originX, originY, cardW, cardH)
  setTimeout(() => { spawnBurst(originX, originY); ensureLoop() }, 350)
  setTimeout(() => { spawnEmbers(originX, originY); ensureLoop() }, 800)
  ensureLoop()
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const parent = canvas.parentElement
  if (!parent) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = parent.clientWidth * dpr
  canvas.height = parent.clientHeight * dpr
  canvas.style.width = parent.clientWidth + 'px'
  canvas.style.height = parent.clientHeight + 'px'
  const ctx = canvas.getContext('2d')
  if (ctx) ctx.scale(dpr, dpr)
}

function toggleTag(tag: TagConfig, event: MouseEvent) {
  if (tag.isDefault) return

  if (flippingCards.value.has(tag.name)) return

  const cardEl = (event.currentTarget as HTMLElement).closest('.tag-card') as HTMLElement
  if (!cardEl) return

  const wasSelected = selectedTags.value.has(tag.name)
  const isSelecting = !wasSelected

  flippingCards.value.add(tag.name)

  const rect = cardEl.getBoundingClientRect()
  const canvas = canvasRef.value
  if (canvas) {
    const canvasRect = canvas.getBoundingClientRect()
    const cx = rect.left + rect.width / 2 - canvasRect.left
    const cy = rect.top + rect.height / 2 - canvasRect.top
    spawnParticles(tag.name, cx, cy, rect.width, rect.height)
  }

  const inner = cardEl.querySelector('.card-inner') as HTMLElement
  if (inner) {
    gsap.to(inner, {
      rotateY: isSelecting ? 180 : 0,
      duration: 0.6,
      ease: 'back.out(1.4)',
      onComplete: () => {
        flippingCards.value.delete(tag.name)
      },
    })
  }

  if (isSelecting) {
    selectedTags.value.add(tag.name)
    if (tag.comment) {
      emit('tagComment', tag.name, tag.comment, tag.commentExpression || 'happy')
    }
  } else {
    selectedTags.value.delete(tag.name)
  }
}

function isSelected(tag: TagConfig): boolean {
  return selectedTags.value.has(tag.name)
}

function handleConfirm() {
  emit('confirm', Array.from(selectedTags.value))
}

function animateCardsIn() {
  if (!cardsRef.value) return
  const cards = Array.from(cardsRef.value.querySelectorAll('.tag-card'))

  if (props.flyOrigin) {
    const containerRect = cardsRef.value.getBoundingClientRect()
    const ox = props.flyOrigin.x - containerRect.left
    const oy = props.flyOrigin.y - containerRect.top

    cards.forEach((card, i) => {
      const el = card as HTMLElement
      const cardRect = el.getBoundingClientRect()
      const finalCX = cardRect.left + cardRect.width / 2 - containerRect.left
      const finalCY = cardRect.top + cardRect.height / 2 - containerRect.top

      gsap.set(el, {
        x: ox - finalCX,
        y: oy - finalCY,
        opacity: 0,
        scale: 0.2,
        rotation: (Math.random() - 0.5) * 60,
        visibility: 'visible',
      })

      gsap.to(el, {
        x: 0,
        y: 0,
        opacity: 1,
        scale: 1,
        rotation: 0,
        duration: 0.7,
        delay: i * 0.05,
        ease: 'back.out(1.2)',
      })
    })

    const totalDuration = 0.7 + (cards.length - 1) * 0.05 + 0.1
    setTimeout(() => {
      isAnimatingIn.value = false
    }, totalDuration * 1000)
  } else {
    gsap.set(cards, {
      y: -80,
      opacity: 0,
      scale: 0.8,
      visibility: 'visible',
    })
    gsap.to(cards, {
      y: 0,
      opacity: 1,
      scale: 1,
      duration: 0.6,
      stagger: 0.04,
      ease: 'bounce.out',
      onComplete: () => {
        isAnimatingIn.value = false
      },
    })
  }
}

function startButtonGlow() {
  if (!confirmBtnRef.value) return
  gsap.to(confirmBtnRef.value, {
    boxShadow: '0 0 0 3px rgba(206, 66, 43, 0.35), 0 4px 16px rgba(206, 66, 43, 0.15)',
    duration: 1.2,
    yoyo: true,
    repeat: -1,
    ease: 'sine.inOut',
  })
}

function handleCardMouseEnter(event: MouseEvent) {
  if (isAnimatingIn.value) return
  const card = (event.currentTarget as HTMLElement)
  const rect = card.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const centerX = rect.width / 2
  const centerY = rect.height / 2
  const rotateX = ((y - centerY) / centerY) * -8
  const rotateY = ((x - centerX) / centerX) * 8

  gsap.to(card, {
    rotateX,
    rotateY,
    y: -24,
    zIndex: 10,
    boxShadow: '0 20px 40px rgba(0,0,0,0.12)',
    duration: 0.3,
    ease: 'power2.out',
  })

  const shine = card.querySelector('.card-shine') as HTMLElement
  if (shine) {
    gsap.fromTo(shine,
      { x: '-100%', opacity: 0.6 },
      { x: '200%', opacity: 0, duration: 0.6, ease: 'power2.out' },
    )
  }
}

function handleCardMouseMove(event: MouseEvent) {
  if (isAnimatingIn.value) return
  const card = (event.currentTarget as HTMLElement)
  const rect = card.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const centerX = rect.width / 2
  const centerY = rect.height / 2
  const rotateX = ((y - centerY) / centerY) * -8
  const rotateY = ((x - centerX) / centerX) * 8

  gsap.to(card, {
    rotateX,
    rotateY,
    y: -24,
    zIndex: 10,
    duration: 0.15,
    ease: 'power1.out',
    overwrite: true,
  })
}

function handleCardMouseLeave(event: MouseEvent) {
  if (isAnimatingIn.value) return
  const card = (event.currentTarget as HTMLElement)
  gsap.to(card, {
    rotateX: 0,
    rotateY: 0,
    y: 0,
    zIndex: 0,
    boxShadow: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
    duration: 0.4,
    ease: 'power2.out',
  })
}

onMounted(() => {
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)
  setTimeout(() => {
    animateCardsIn()
    startButtonGlow()
  }, 100)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId)
    animFrameId = null
  }
  particles = []
})
</script>

<template>
  <div class="card-select-scene">
    <div class="card-select-header">
      <h2 class="card-select-title">选择你感兴趣的方向</h2>
      <p class="card-select-subtitle">点击卡片选择，可多选</p>
    </div>

    <div ref="cardsRef" class="card-grid">
      <div
        v-for="(tag, index) in tags"
        :key="tag.name"
        class="tag-card"
        :class="{
          selected: isSelected(tag),
          'is-default': tag.isDefault,
        }"
        :style="{ '--card-rotation': rotations[index] + 'deg' }"
        @mouseenter="handleCardMouseEnter"
        @mousemove="handleCardMouseMove"
        @mouseleave="handleCardMouseLeave"
      >
        <div class="card-inner">
          <div class="card-front" @click="toggleTag(tag, $event)">
            <div class="card-border" :style="{ borderColor: tagColors[tag.name] || '#999' }">
              <div class="card-ornament-top" :style="{ color: tagColors[tag.name] || '#999' }">✦</div>
              <div class="card-symbol">{{ tagLabels[tag.name] || '?' }}</div>
              <div class="card-accent-line" :style="{ background: tagColors[tag.name] || '#999' }"></div>
              <span class="card-name">{{ tag.name }}</span>
              <p class="card-desc">{{ tag.description }}</p>
              <div class="card-ornament-bottom" :style="{ color: tagColors[tag.name] || '#999' }">✦</div>
              <div v-if="tag.isDefault" class="card-badge">必选</div>
            </div>
            <div class="card-shine"></div>
          </div>
          <div class="card-back" @click="toggleTag(tag, $event)">
            <div class="card-back-inner" :style="{ borderColor: tagColors[tag.name] || '#999' }">
              <div class="card-back-ornament" :style="{ color: tagColors[tag.name] || '#999' }">✦</div>
              <div class="card-back-check" :style="{ background: tagColors[tag.name] || '#999' }">&#10003;</div>
              <span class="card-back-name">{{ tag.name }}</span>
              <span class="card-back-status">已选择</span>
              <div class="card-back-ornament" :style="{ color: tagColors[tag.name] || '#999' }">✦</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <canvas ref="canvasRef" class="particle-canvas"></canvas>

    <div class="card-select-footer">
      <button
        ref="confirmBtnRef"
        class="confirm-btn"
        :disabled="selectedTags.size === 0"
        @click="handleConfirm"
      >
        确认选择 ({{ selectedTags.size }})
      </button>
    </div>
  </div>
</template>

<style scoped>
.card-select-scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  padding: 16px 40px;
  overflow: hidden;
  position: relative;
}

.card-select-header {
  margin-bottom: 12px;
  z-index: 5;
  text-align: center;
}

.card-select-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.card-select-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.card-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px 8px;
  max-width: 780px;
  width: 100%;
  z-index: 5;
  perspective: 1000px;
}

.tag-card {
  width: 140px;
  height: 220px;
  cursor: pointer;
  will-change: transform;
  transform-style: preserve-3d;
  opacity: 0;
  visibility: hidden;
  transform: rotate(var(--card-rotation, 0deg));
}

.card-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
}

.card-front,
.card-back {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  background: var(--card-bg-solid);
  overflow: hidden;
}

.card-back {
  transform: rotateY(180deg);
}

.card-front {
  border: 1px solid var(--border-color);
  transition: border-color 0.2s ease;
}

.card-front:hover {
  border-color: #CE422B;
}

.tag-card.selected .card-front {
  border-color: #CE422B;
  box-shadow: 0 0 0 1px #CE422B, 0 0 20px rgba(206, 66, 43, 0.2);
}

.tag-card.is-default {
  cursor: default;
}

.card-border {
  width: 100%;
  height: 100%;
  border: 2px solid;
  margin: -1px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 8px;
  gap: 4px;
  position: relative;
}

.card-ornament-top,
.card-ornament-bottom {
  font-size: 10px;
  opacity: 0.6;
  line-height: 1;
}

.card-symbol {
  font-size: 40px;
  font-weight: 900;
  color: var(--text-primary);
  letter-spacing: 1px;
  margin-bottom: 2px;
}

.card-accent-line {
  width: 30px;
  height: 2px;
  margin-bottom: 4px;
}

.card-name {
  font-size: 16px;
  font-weight: 900;
  color: var(--text-primary);
  letter-spacing: -0.3px;
  text-align: center;
  line-height: 1.2;
}

.card-desc {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.4;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 8px;
  font-weight: 600;
  color: white;
  background: rgba(206, 66, 43, 0.8);
  padding: 1px 4px;
}

.card-shine {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    105deg,
    transparent 40%,
    rgba(255, 255, 255, 0.4) 45%,
    rgba(255, 255, 255, 0.1) 50%,
    transparent 55%
  );
  transform: translateX(-100%);
  pointer-events: none;
}

.card-back-inner {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: var(--card-bg-solid);
  border: 2px solid;
}

.card-back-ornament {
  font-size: 10px;
  opacity: 0.5;
}

.card-back-check {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: white;
}

.card-back-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.card-back-status {
  font-size: 9px;
  color: var(--text-secondary);
}

.particle-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 50;
}

.card-select-footer {
  margin-top: 12px;
  z-index: 5;
}

.confirm-btn {
  padding: 10px 36px;
  font-size: 14px;
  font-weight: 700;
  color: white;
  background: #CE422B;
  border-radius: var(--radius-button);
  box-shadow: var(--shadow-normal);
  transition: all 0.15s ease;
  letter-spacing: 0.3px;
}

.confirm-btn:hover:not(:disabled) {
  background: #B7410E;
}

@media (max-width: 1024px) {
  .card-grid {
    max-width: 600px;
  }
}

@media (max-width: 768px) {
  .card-grid {
    gap: 8px 6px;
  }

  .tag-card {
    width: 110px;
    height: 175px;
  }

  .card-symbol {
    font-size: 30px;
  }

  .card-name {
    font-size: 13px;
  }

  .card-desc {
    font-size: 10px;
    -webkit-line-clamp: 2;
  }

  .card-select-scene {
    padding: 16px;
  }
}
</style>
