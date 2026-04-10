<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import gsap from 'gsap'
import type { Expression } from '../types'

const props = defineProps<{
  text: string
  expression: Expression
  speaker?: string
  typingSpeed?: number
  clickable?: boolean
}>()

const emit = defineEmits<{
  complete: []
  advance: []
}>()

const displayText = ref('')
const isTyping = ref(false)
const dialogueRef = ref<HTMLElement | null>(null)
let typewriterInterval: ReturnType<typeof setInterval> | null = null

function startTypewriter(fullText: string) {
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
    typewriterInterval = null
  }

  displayText.value = ''
  isTyping.value = true
  let i = 0

  typewriterInterval = setInterval(() => {
    if (i < fullText.length) {
      displayText.value += fullText.charAt(i)
      i++
    } else {
      if (typewriterInterval) {
        clearInterval(typewriterInterval)
        typewriterInterval = null
      }
      isTyping.value = false
      emit('complete')
      nudgeComplete()
    }
  }, props.typingSpeed || 50)
}

function skipToEnd() {
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
    typewriterInterval = null
  }
  displayText.value = props.text
  isTyping.value = false
  emit('complete')
}

function handleClick() {
  if (isTyping.value) {
    skipToEnd()
  } else {
    emit('advance')
  }
}

function animateIn() {
  if (!dialogueRef.value) return
  gsap.fromTo(
    dialogueRef.value,
    { y: 40, opacity: 0, scale: 0.96 },
    { y: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.4)' },
  )
}

function nudgeComplete() {
  if (!dialogueRef.value) return
  gsap.fromTo(
    dialogueRef.value,
    { x: 0 },
    { x: 4, duration: 0.06, repeat: 3, yoyo: true, ease: 'power2.inOut' },
  )
}

watch(
  () => props.text,
  (newText) => {
    if (newText) {
      startTypewriter(newText)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
  }
})

defineExpose({ animateIn, startTypewriter, skipToEnd })
</script>

<template>
  <div
    ref="dialogueRef"
    class="dialogue-box"
    :class="{ clickable: clickable !== false }"
    @click="handleClick"
  >
    <div class="dialogue-accent"></div>
    <div class="dialogue-body">
      <div class="dialogue-header">
        <span class="dialogue-speaker">{{ speaker || '类脑娘' }}</span>
        <span v-if="isTyping" class="dialogue-indicator">...</span>
      </div>
      <div class="dialogue-text">
        {{ displayText }}
        <span v-if="isTyping" class="typing-cursor">|</span>
      </div>
      <div v-if="!isTyping && text" class="dialogue-hint">点击继续</div>
    </div>
    <div class="dialogue-tail"></div>
  </div>
</template>

<style scoped>
.dialogue-box {
  position: absolute;
  bottom: 40px;
  left: 60px;
  right: 430px;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-dialog);
  box-shadow: var(--shadow-normal);
  overflow: visible;
  z-index: 20;
  min-height: 110px;
  max-height: 190px;
}

.dialogue-box.clickable {
  cursor: pointer;
}

.dialogue-box.clickable:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-float);
}

.dialogue-accent {
  width: 100%;
  height: 3px;
  background: var(--accent-gold);
  flex-shrink: 0;
}

.dialogue-body {
  flex: 1;
  padding: 20px 28px 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialogue-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.dialogue-speaker {
  font-size: 22px;
  font-weight: 900;
  color: var(--accent-gold);
  letter-spacing: -0.3px;
}

.dialogue-indicator {
  font-size: 13px;
  color: var(--accent-gold);
  font-weight: 700;
  letter-spacing: 2px;
}

.dialogue-text {
  font-size: 18px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
}

.typing-cursor {
  animation: blink 0.8s step-end infinite;
  color: var(--accent-gold);
  font-weight: 300;
}

.dialogue-hint {
  position: absolute;
  bottom: 12px;
  right: 20px;
  font-size: 13px;
  color: var(--text-muted);
  animation: hint-fade 2s ease-in-out infinite;
}

@keyframes hint-fade {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.dialogue-tail {
  position: absolute;
  bottom: -10px;
  right: 80px;
  width: 0;
  height: 0;
  border-left: 10px solid transparent;
  border-right: 10px solid transparent;
  border-top: 10px solid rgba(255, 255, 255, 0.92);
  filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.03));
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

@media (max-width: 768px) {
  .dialogue-box {
    left: 16px;
    right: 16px;
    bottom: 20px;
    min-height: 100px;
  }

  .dialogue-body {
    padding: 14px 18px 12px;
  }

  .dialogue-text {
    font-size: 15px;
  }

  .dialogue-tail {
    display: none;
  }
}
</style>
