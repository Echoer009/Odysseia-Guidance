export type Expression =
  | 'normal'
  | 'happy'
  | 'wave'
  | 'shy'
  | 'thinking'
  | 'surprised'
  | 'sad'
  | 'excited'
  | 'wink'
  | 'proud'
  | 'annoyed'
  | 'angry'
  | 'furious'
  | 'bye_wave'

export type ChapterMood = 'normal' | 'sad' | 'celebration'

export type EntryType = 'text' | 'stat' | 'gallery'

export interface DiaryEntry {
  type: EntryType
  date: string
  mood: ChapterMood
  expression: Expression
  text: string
  // stat 类型：边注数据（由后端注入真实数字）
  data_label?: string
  data_value?: string
  data_secondary?: string
  // gallery 类型：商品画廊（图+名）
  gallery_category?: 'food' | 'gift'
  gallery_items?: string[]
}

export interface Diary {
  bot_name: string
  currency_name: string
  birth_date: string
  days_alive: number
  entries: DiaryEntry[]
}
