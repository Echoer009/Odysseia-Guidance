export interface EmbedMessage {
  title: string
  description: string
  footer: string
  thumbnailUrl?: string
  imageUrl?: string
}

export interface ChannelInfo {
  id: string
  name: string
  type: 'channel' | 'thread'
  permanentMessage: EmbedMessage
  temporaryMessages: EmbedMessage[]
}

export interface TagConfig {
  name: string
  description: string
  isDefault?: boolean
  channelIds: string[]
  cover: string
  comment?: string
  commentExpression?: Expression
}

export interface TourSlide {
  channelId: string
  channelName: string
  channelType: 'channel' | 'thread'
  title: string
  description: string
  footer: string
  slug: string
  thumbnailUrl?: string
  imageUrl?: string
  charImage?: string
}

export interface DialogueEntry {
  text: string
  expression: Expression
  image?: string
}

export type Expression = 'normal' | 'happy' | 'wave' | 'shy' | 'thinking' | 'surprised' | 'sad' | 'excited' | 'wink' | 'proud' | 'annoyed' | 'angry' | 'furious'
export type SceneName = 'loading' | 'welcome' | 'selection' | 'tour' | 'tutorial' | 'finish' | 'kickout'

export interface TutorialSlide {
  id: string
  title: string
  description: string
  tip?: string
  expression: Expression
  icon?: string
}

export interface GuidanceState {
  currentScene: SceneName
  selectedTags: string[]
  currentSlideIndex: number
  channelsQueue: TourSlide[]
  userName: string
  loadingProgress: number
  loadingMessage: string
}
