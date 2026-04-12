import type { TagConfig } from '../types'

const b = import.meta.env.BASE_URL

export const tagsConfig: TagConfig[] = [
  {
    name: '默认',
    description: '服务器的核心区域，都是些不能错过的地方哦！',
    isDefault: true,
    channelIds: [
      '1393179379126767686',
      '1337107956499615744',
      '1307242450300964986',
      '1234431470773338143',
      '1402121015911518379',
      '1365567153390227508',
      '1431907913055600731',
      '1431906908478115891',
    ],
    cover: `${b}assets/tags/tag_default.webp`,
    comment: '这里就是我们的家啦！核心频道都给你准备好了～',
    commentExpression: 'happy',
  },
  {
    name: '男性向',
    description: '嘿，这里有好玩的男性向内容，快来看看吧！',
    channelIds: [
      '1378738606335594667',
      '1434215095860203550',
    ],
    cover: `${b}assets/tags/tag_male.webp`,
    comment: '嘿嘿，这里有你喜欢的～欢迎来到男性向分区！',
    commentExpression: 'excited',
  },
  {
    name: '女性向',
    description: '各种女性向的好东西都在这儿~',
    channelIds: [
      '1378738701919850546',
      '1374630459828469853',
    ],
    cover: `${b}assets/tags/tag_female.webp`,
    comment: '好眼光！女性向分区有很多精彩的内容等着你哦～',
    commentExpression: 'happy',
  },
  {
    name: '纯净向',
    description: '想体验纯粹美好的情感？来这里就对啦，完全纯净，没有涩涩！',
    channelIds: [
      '1399006747733266452',
    ],
    cover: `${b}assets/tags/tag_pure.webp`,
    comment: '纯净的世界最美好啦！这里一定不会让你失望的～',
    commentExpression: 'happy',
  },
  {
    name: '深渊',
    description: '如果你喜欢探讨人性的复杂和深邃，那就来深渊看看吧，很有深度的！',
    channelIds: [
      '1337561613821022248',
    ],
    cover: `${b}assets/tags/tag_abyss.webp`,
    comment: '哦？你对深渊感兴趣...很勇敢嘛，欢迎探索！',
    commentExpression: 'thinking',
  },
  {
    name: '聊聊天',
    description: '对AI技术感兴趣？或者想看大家斗图斗模型？来这里和大家一起聊聊天吧！',
    channelIds: [
      '1378734700318822400',
      '1408471251260932146',
    ],
    cover: `${b}assets/tags/tag_chat.webp`,
    comment: '来聊天区一起玩吧！大家都超有趣的～',
    commentExpression: 'wave',
  },
  {
    name: '其他分区',
    description: '这里是创意无限的宝库！各种脑洞大开的卡片，总有一款适合你！',
    channelIds: [
      '1399003980805181521',
      '1399004359731314698',
      '1376210194887082034',
    ],
    cover: `${b}assets/tags/tag_other.webp`,
    comment: '探索精神满分！这里有很多有趣的分区等你发现～',
    commentExpression: 'excited',
  },
  {
    name: 'AI绘图',
    description: '喜欢AI画画？无论是技术交流还是作品分享，这里都能满足你！',
    channelIds: [
      '1378743070203576432',
      '1378742997885390973',
    ],
    cover: `${b}assets/tags/tag_aiart.webp`,
    comment: 'AI画师集结！期待你的作品哦～',
    commentExpression: 'excited',
  },
  {
    name: '酒馆美化',
    description: '想让你的酒馆界面更漂亮吗？来这里寻找或分享美化方案吧！',
    channelIds: [
      '1431911482727207002',
    ],
    cover: `${b}assets/tags/tag_beauty.webp`,
    comment: '美化大师就是你！期待看到你的作品～',
    commentExpression: 'happy',
  },
  {
    name: '档案馆',
    description: '想回顾服务器的经典作品吗？档案馆里收藏了过去的作品！',
    channelIds: [
      '1432661851644100679',
    ],
    cover: `${b}assets/tags/tag_archive.webp`,
    comment: '档案馆里有很多珍贵的回忆，慢慢翻阅吧～',
    commentExpression: 'thinking',
  },
]
