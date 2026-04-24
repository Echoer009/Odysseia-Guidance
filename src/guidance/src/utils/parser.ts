import type { TourSlide, ChannelInfo } from '../types'

export interface DescToken {
  type: 'text' | 'bold' | 'accent' | 'warning' | 'separator' | 'newline' | 'paragraph'
  text: string
}

export function parseDescription(raw: string): DescToken[] {
  const tokens: DescToken[] = []
  const regex = /(\*\*(.+?)\*\*)|(\{\{(.+?)\}\})|(!!(.+?)!!)|(---)|(\n\n)|(\n)/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(raw)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ type: 'text', text: raw.slice(lastIndex, match.index) })
    }
    if (match[1]) {
      tokens.push({ type: 'bold', text: match[2] })
    } else if (match[3]) {
      tokens.push({ type: 'accent', text: match[4] })
    } else if (match[5]) {
      tokens.push({ type: 'warning', text: match[6] })
    } else if (match[7]) {
      tokens.push({ type: 'separator', text: '' })
    } else if (match[8]) {
      tokens.push({ type: 'paragraph', text: '' })
    } else if (match[9]) {
      tokens.push({ type: 'newline', text: '' })
    }
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < raw.length) {
    tokens.push({ type: 'text', text: raw.slice(lastIndex) })
  }
  return tokens
}

export function tokenCharCount(tokens: DescToken[]): number {
  let n = 0
  for (const t of tokens) {
    if (t.type !== 'newline' && t.type !== 'paragraph') n += t.text.length
  }
  return n
}

export function renderTokens(tokens: DescToken[], revealed: number): string {
  let remaining = revealed
  let html = ''
  for (const token of tokens) {
    if (remaining <= 0 && token.type !== 'paragraph' && token.type !== 'newline' && token.type !== 'separator') break
    if (token.type === 'paragraph') { html += '<div class="desc-gap"></div>'; continue }
    if (token.type === 'newline') { html += '<br>'; continue }
    if (token.type === 'separator') { html += '<div class="desc-separator"></div>'; continue }
    const show = Math.min(remaining, token.text.length)
    const text = token.text.slice(0, show)
    remaining -= show
    if (token.type === 'bold') html += `<strong class="desc-bold">${text}</strong>`
    else if (token.type === 'accent') html += `<span class="desc-accent">${text}</span>`
    else if (token.type === 'warning') html += `<span class="desc-warning">${text}</span>`
    else html += text
  }
  return html
}

export function parseChannelData(rawData: ChannelInfo[]): TourSlide[] {
  const slides: TourSlide[] = []

  for (const channel of rawData) {
    slides.push({
      channelId: channel.id,
      channelName: channel.name,
      channelType: channel.type,
      title: channel.permanentMessage.title,
      description: channel.permanentMessage.description,
      footer: channel.permanentMessage.footer,
      slug: channel.id,
      thumbnailUrl: channel.permanentMessage.thumbnailUrl,
      imageUrl: channel.permanentMessage.imageUrl,
    })

    for (const msg of channel.temporaryMessages) {
      slides.push({
        channelId: channel.id,
        channelName: channel.name,
        channelType: channel.type,
        title: msg.title,
        description: msg.description,
        footer: msg.footer,
        slug: channel.id,
        thumbnailUrl: msg.thumbnailUrl,
        imageUrl: msg.imageUrl,
      })
    }
  }

  return slides
}

export function buildChannelUrl(guildId: string, channelId: string): string {
  return `https://discord.com/channels/${guildId}/${channelId}`
}
