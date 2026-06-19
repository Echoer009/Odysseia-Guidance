import type { Expression } from '../types'

const assetBase = import.meta.env.BASE_URL

export interface ExpressionMeta {
  path: string
  color: string
  label: string
}

export const backgroundAssets = {
  paper: `${assetBase}assets/backgrounds/bg_sky.webp`,
  finish: `${assetBase}assets/backgrounds/bg_finish.webp`,
}

const DEFAULT_META: ExpressionMeta = {
  path: '',
  color: '#b5462d',
  label: '???',
}

export const expressions: Record<string, ExpressionMeta> = {
  normal:    { path: `${assetBase}assets/characters/normal.webp`,    color: '#b5462d', label: 'NORMAL' },
  happy:     { path: `${assetBase}assets/characters/happy.webp`,     color: '#d98a4e', label: 'HAPPY' },
  wave:      { path: `${assetBase}assets/characters/wave.webp`,      color: '#c08a3e', label: 'WAVE' },
  shy:       { path: `${assetBase}assets/characters/shy.webp`,       color: '#d98a8a', label: 'SHY' },
  thinking:  { path: `${assetBase}assets/characters/thinking.webp`,  color: '#7a8fa6', label: 'THINK' },
  surprised: { path: `${assetBase}assets/characters/surprised.webp`, color: '#c8a13e', label: 'O_O' },
  sad:       { path: `${assetBase}assets/characters/sad.webp`,       color: '#8a857c', label: 'SAD' },
  excited:   { path: `${assetBase}assets/characters/excited.webp`,   color: '#c25a3a', label: 'EXCITED' },
  wink:      { path: `${assetBase}assets/characters/wink.webp`,      color: '#b5816e', label: 'WINK' },
  proud:     { path: `${assetBase}assets/characters/proud.webp`,     color: '#9aa15a', label: 'PROUD' },
  annoyed:   { path: `${assetBase}assets/characters/annoyed.webp`,   color: '#8a6f5a', label: 'ANNEX' },
  angry:     { path: `${assetBase}assets/characters/angry.webp`,     color: '#a83a2a', label: 'ANGRY' },
  furious:   { path: `${assetBase}assets/characters/furious.webp`,   color: '#7a1a1a', label: 'FURY' },
  bye_wave:  { path: `${assetBase}assets/characters/bye_wave.png`,   color: '#b5816e', label: 'BYE' },
}

export function getExpressionMeta(expr: Expression): ExpressionMeta {
  return expressions[expr] || DEFAULT_META
}

export function getExpressionPath(expr: Expression): string {
  return expressions[expr]?.path || ''
}

export function getExpressionColor(expr: Expression): string {
  return expressions[expr]?.color || DEFAULT_META.color
}

export function getExpressionLabel(expr: Expression): string {
  return expressions[expr]?.label || expr.toUpperCase()
}
