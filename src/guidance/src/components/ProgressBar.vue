<script setup lang="ts">
import { ref, watch } from 'vue'
import gsap from 'gsap'

const props = defineProps<{
  current: number
  total: number
}>()

const barRef = ref<HTMLElement | null>(null)
const labelRef = ref<HTMLElement | null>(null)

watch(
  () => props.current,
  () => {
    if (!barRef.value) return
    const pct = props.total > 0 ? (props.current / props.total) * 100 : 0
    gsap.to(barRef.value, {
      width: `${pct}%`,
      duration: 0.5,
      ease: 'power2.out',
    })
    if (labelRef.value) {
      gsap.fromTo(
        labelRef.value,
        { scale: 1.1 },
        { scale: 1, duration: 0.3, ease: 'back.out(2)' },
      )
    }
  },
)
</script>

<template>
  <div class="progress-wrapper">
    <div class="progress-track">
      <div ref="barRef" class="progress-bar" :style="{ width: total > 0 ? `${(current / total) * 100}%` : '0%' }"></div>
    </div>
    <span ref="labelRef" class="progress-label">{{ current }} / {{ total }}</span>
  </div>
</template>

<style scoped>
.progress-wrapper {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 30;
}

.progress-track {
  width: 200px;
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent-gold);
  border-radius: 2px;
  transition: none;
}

.progress-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
