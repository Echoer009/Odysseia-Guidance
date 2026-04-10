import type { DialogueEntry } from '../../types'

export const tourStartDialogue: DialogueEntry = {
  text: '好嘞！让我带你逛逛这些地方吧～',
  expression: 'happy',
}

export const tourEndDialogue: DialogueEntry = {
  text: '好啦，导览结束！希望你在类脑社区玩得开心～',
  expression: 'happy',
}

export const channelExpressionMap: Record<string, string> = {
  '新手答疑': 'normal',
  '羁绊的开始': 'happy',
  'AI杂谈': 'normal',
  '男NSFW聊天区': 'shy',
  '女NSFW聊天区': 'shy',
  '每日新卡': 'happy',
  '搜索频道': 'normal',
  '角色卡分区：男性向': 'normal',
  '角色卡分区：女性向': 'normal',
  '角色卡分区：纯净向': 'happy',
  '角色卡分区：全性向': 'normal',
  '角色卡分区：世界书': 'thinking',
  '角色卡分区：其他区': 'thinking',
  '角色卡分区：工具区': 'thinking',
  '角色卡分区：深渊区': 'shy',
  '档案馆': 'normal',
  '预设破限区': 'thinking',
  '酒馆美化区': 'happy',
  'NSFW绘图': 'shy',
  'SFW绘图': 'happy',
  '类脑竞技场': 'excited',
  '卡区Bot功能介绍': 'normal',
  '回顶区': 'normal',
}
