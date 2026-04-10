import type { TourSlide, ChannelInfo } from '../types'

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
