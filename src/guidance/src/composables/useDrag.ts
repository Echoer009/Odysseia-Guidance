import { ref, computed } from 'vue'

const dragCount = ref(0)
const isKickedOut = ref(false)

const DRAG_PHASE_THRESHOLDS: { min: number; phase: number }[] = [
  { min: 13, phase: 5 },
  { min: 10, phase: 4 },
  { min: 7, phase: 3 },
  { min: 4, phase: 2 },
  { min: 2, phase: 1 },
  { min: 1, phase: 0 },
]

export function useDrag() {
  const currentPhase = computed(() => {
    for (const { min, phase } of DRAG_PHASE_THRESHOLDS) {
      if (dragCount.value >= min) return phase
    }
    return 0
  })

  function drag(): { phase: number; isKicked: boolean } | null {
    if (isKickedOut.value) return null

    dragCount.value++

    const phase = currentPhase.value
    const kicked = phase === 5

    if (kicked) {
      isKickedOut.value = true
    }

    return { phase, isKicked: kicked }
  }

  function reset() {
    dragCount.value = 0
    isKickedOut.value = false
  }

  return {
    dragCount,
    currentPhase,
    isKickedOut,
    drag,
    reset,
  }
}
