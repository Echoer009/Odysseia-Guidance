<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
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
    }
  }, props.typingSpeed || 65)
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
}

watch(
  () => props.text,
  (newText) => {
    if (newText) {
      startTypewriter(newText)
    } else {
      displayText.value = ''
      isTyping.value = false
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
    class="diary-text hand"
    :class="{ clickable: clickable !== false }"
    @click="handleClick"
  >
    <span class="dt-content">{{ displayText }}<span v-if="isTyping" class="typing-cursor">|</span></span>
  </div>
</template>

<style scoped>
/* 手写日记正文：直接写在纸上，无对话框 */
.diary-text {
  position: absolute;
  top: 96px;
  left: 60px;
  right: 44%;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.diary-text.clickable {
  cursor: pointer;
}

.dt-content {
  font-size: 25px;
  line-height: 1.95;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
  letter-spacing: 1px;
  text-shadow: 0 1px 0 rgba(255, 252, 244, 0.4);
}

.typing-cursor {
  animation: blink 0.8s step-end infinite;
  color: var(--accent);
  font-weight: 300;
  margin-left: 1px;
}



@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
