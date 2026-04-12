import type { Expression } from '../types'

export interface CloudConfig {
  file: string
  width: number
  height: number
  top: string
  duration: number
  delay: number
  scale: number
}

export interface ExpressionMeta {
  path: string
  color: string
  label: string
}

export const cloudAssets: CloudConfig[] = [
  { file: 'cloud_1.webp', width: 180, height: 60, top: '12%', duration: 30, delay: 0, scale: 1 },
  { file: 'cloud_2.webp', width: 120, height: 40, top: '22%', duration: 40, delay: -15, scale: 0.8 },
  { file: 'cloud_3.webp', width: 200, height: 70, top: '8%', duration: 35, delay: -8, scale: 1.1 },
]

export const backgroundAssets = {
  sky: '/assets/backgrounds/bg_sky.webp',
  finish: '/assets/backgrounds/bg_finish.webp',
  sunflower: '/assets/backgrounds/sunflower_loading.webp',
}

const DEFAULT_META: ExpressionMeta = {
  path: '',
  color: '#CE422B',
  label: '???',
}

export const expressions: Record<string, ExpressionMeta> = {
  normal:   { path: '/assets/characters/normal.webp',   color: '#CE422B', label: 'NORMAL' },
  happy:    { path: '/assets/characters/happy.webp',    color: '#FF6B6B', label: 'HAPPY' },
  wave:     { path: '/assets/characters/wave.webp',     color: '#4FC3F7', label: 'WAVE' },
  shy:      { path: '/assets/characters/shy.webp',      color: '#F48FB1', label: 'SHY' },
  thinking: { path: '/assets/characters/thinking.webp', color: '#90CAF9', label: 'THINK' },
  surprised:{ path: '/assets/characters/surprised.webp', color: '#FFD54F', label: 'O_O' },
  sad:      { path: '/assets/characters/sad.webp',      color: '#B0BEC5', label: 'SAD' },
  excited:  { path: '/assets/characters/excited.webp',  color: '#FF7043', label: 'EXCITED' },
  wink:     { path: '/assets/characters/wink.webp',     color: '#CE93D8', label: 'WINK' },
  proud:    { path: '/assets/characters/proud.webp',    color: '#AED581', label: 'PROUD' },
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

export function getChannelBgPath(slug: string): string {
  return `/assets/channels/${slug}.webp`
}

export function getChannelCharPath(slug: string): string {
  return `/assets/channels/${slug}_char.webp`
}
