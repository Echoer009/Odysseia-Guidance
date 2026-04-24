import { ref, computed } from 'vue'
import type { Expression } from '../types'

export type PokePhase = 0 | 1 | 2 | 3 | 4 | 5
export type PokeScene = 'welcome' | 'selection' | 'tour' | 'tutorial' | 'finish'

const pokeCount = ref(0)
const isPoking = ref(false)
const isKickedOut = ref(false)

const PHASE_THRESHOLDS: { min: number; phase: PokePhase }[] = [
  { min: 13, phase: 5 },
  { min: 10, phase: 4 },
  { min: 7, phase: 3 },
  { min: 4, phase: 2 },
  { min: 2, phase: 1 },
  { min: 1, phase: 0 },
]

export function usePoke() {
  const currentPhase = computed<PokePhase>(() => {
    for (const { min, phase } of PHASE_THRESHOLDS) {
      if (pokeCount.value >= min) return phase
    }
    return 0
  })

  const phaseExpression = computed<Expression>(() => {
    switch (currentPhase.value) {
      case 0: return 'surprised'
      case 1: return 'happy'
      case 2: return 'thinking'
      case 3: return 'annoyed'
      case 4: return 'angry'
      case 5: return 'furious'
    }
  })

  const shakeIntensity = computed(() => {
    switch (currentPhase.value) {
      case 0: case 1: return 0
      case 2: return 2
      case 3: return 5
      case 4: return 9
      case 5: return 14
    }
  })

  const shakeDuration = computed(() => {
    switch (currentPhase.value) {
      case 0: case 1: return 0
      case 2: return 0.1
      case 3: return 0.2
      case 4: return 0.3
      case 5: return 0.5
    }
  })

  function poke(): {
    phase: PokePhase
    expression: Expression
    isKicked: boolean
    shakeIntensity: number
    shakeDuration: number
  } | null {
    if (isKickedOut.value) return null

    pokeCount.value++
    isPoking.value = true

    const phase = currentPhase.value
    const kicked = phase === 5

    if (kicked) {
      isKickedOut.value = true
    }

    return {
      phase,
      expression: phaseExpression.value,
      isKicked: kicked,
      shakeIntensity: shakeIntensity.value,
      shakeDuration: shakeDuration.value,
    }
  }

  function clearPoking() {
    isPoking.value = false
  }

  function reset() {
    pokeCount.value = 0
    isPoking.value = false
    isKickedOut.value = false
  }

  return {
    pokeCount,
    currentPhase,
    phaseExpression,
    shakeIntensity,
    shakeDuration,
    isPoking,
    isKickedOut,
    poke,
    clearPoking,
    reset,
  }
}
