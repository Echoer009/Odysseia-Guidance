import { ref, watch, nextTick } from 'vue'
import gsap from 'gsap'
import type { Expression, SceneName } from '../types'
import { usePoke } from './usePoke'
import { getPokeDialogue } from '../data/pokeDialogues'
import { getDragDialogue } from '../data/easterEggDialogues'
import type DialogueBox from '../components/DialogueBox.vue'

const FEEDBACK_DURATION = 1500

export function useSceneFeedback(
  currentScene: { value: SceneName },
  currentExpression: { value: Expression },
  currentImage: { value: string | undefined },
  currentDialogue: { value: string },
  getDialogueRef: () => InstanceType<typeof DialogueBox> | null,
  onExpressionChange?: (expr: Expression) => void,
) {
  const {
    poke: doPoke,
    isKickedOut,
  } = usePoke()

  let feedbackTimer: ReturnType<typeof setTimeout> | null = null
  let savedDialogueState: { text: string; expression: Expression; image: string | undefined } | null = null
  let reactionBubbleTimer: ReturnType<typeof setTimeout> | null = null
  let pendingKickout = false

  const isShowingFeedback = ref(false)
  const reactionBubbleText = ref('')
  const reactionBubbleVisible = ref(false)

  function showReactionDialogue(text: string, expression: Expression, shakeInt: number, _shakeDur: number) {
    const hasDialogueBox = currentScene.value === 'welcome' || currentScene.value === 'selection' || currentScene.value === 'tour' || currentScene.value === 'finish'

    if (!savedDialogueState) {
      savedDialogueState = {
        text: currentDialogue.value,
        expression: currentExpression.value,
        image: currentImage.value,
      }
    }

    isShowingFeedback.value = true
    currentExpression.value = expression
    if (onExpressionChange) onExpressionChange(expression)
    currentImage.value = undefined

    if (hasDialogueBox) {
      const applyFeedback = () => {
        const dialogueBox = getDialogueRef()
        if (dialogueBox) dialogueBox.showFeedback(text)
      }
      if (currentScene.value === 'tour' || currentScene.value === 'finish') {
        nextTick(applyFeedback)
      } else {
        applyFeedback()
      }
    } else {
      reactionBubbleText.value = text
      reactionBubbleVisible.value = true
      if (reactionBubbleTimer) { clearTimeout(reactionBubbleTimer); reactionBubbleTimer = null }
      reactionBubbleTimer = setTimeout(() => { reactionBubbleVisible.value = false; reactionBubbleTimer = null }, FEEDBACK_DURATION)
    }

    if (shakeInt > 0) {
      const sceneEl = document.querySelector('.scene') as HTMLElement
      if (sceneEl) {
        const px = shakeInt * 2
        const tl = gsap.timeline({ onComplete: () => { gsap.set(sceneEl, { x: 0, y: 0 }); return null } })
        for (let i = 0; i < 4; i++) {
          tl.to(sceneEl, {
            x: (Math.random() - 0.5) * px,
            y: (Math.random() - 0.5) * px * 0.5,
            duration: 0.04,
            ease: 'none',
          })
        }
        tl.to(sceneEl, { x: 0, y: 0, duration: 0.04, ease: 'none' })
      }
    }

    if (feedbackTimer) clearTimeout(feedbackTimer)
    feedbackTimer = setTimeout(() => {
      if (pendingKickout) {
        pendingKickout = false
        triggerKickOut()
      } else if (savedDialogueState) {
        currentExpression.value = savedDialogueState.expression
        if (onExpressionChange) onExpressionChange(savedDialogueState.expression)
        currentImage.value = savedDialogueState.image
        savedDialogueState = null
      }
      isShowingFeedback.value = false
      feedbackTimer = null
    }, FEEDBACK_DURATION)
  }

  function handleInteraction(type: 'poke' | 'drag') {
    if (isKickedOut.value) return
    const result = doPoke()
    if (!result) return
    const dialogue = type === 'poke'
      ? getPokeDialogue((currentScene.value === 'tour' ? 'tour' : currentScene.value) as any, result.phase)
      : getDragDialogue(result.phase)
    showReactionDialogue(dialogue, result.expression, result.shakeIntensity, result.shakeDuration)
    if (result.isKicked) pendingKickout = true
  }

  function triggerKickOut() {
    currentScene.value = 'kickout'
  }

  function cleanup() {
    if (feedbackTimer) { clearTimeout(feedbackTimer); feedbackTimer = null; savedDialogueState = null }
    if (reactionBubbleTimer) { clearTimeout(reactionBubbleTimer); reactionBubbleTimer = null }
    reactionBubbleVisible.value = false
  }

  watch(currentScene, cleanup)

  return {
    isKickedOut,
    isShowingFeedback,
    reactionBubbleText,
    reactionBubbleVisible,
    handleInteraction,
    triggerKickOut,
  }
}
