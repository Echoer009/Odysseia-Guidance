# -*- coding: utf-8 -*-
"""
类脑娘的日记 - 页面脚本（文案层）。

本文件只定义「页面序列 + 文案」，不含任何数据逻辑。
所有 data_label / data_value / data_secondary 由 diary_service.build_diary 根据实时数据库
统计注入（type == "stat" 的页面）。

【文案 agent 只需要改这个文件】
- 每个页面是一个 dict，type 三选一：text / stat / gallery。
- 不要动 type / date / mood / stat / category 等结构字段，除非明确要调整流程。

页面类型说明：
  text    纯叙事页：date + mood + expression + text
  stat    数据盘点页：在 text 基础上，由 stat 键注入一条「边注」数据
          stat 可选值：feeding / work / blackjack / loan / coin / namecard /
                       tarot / forum / reply / affection
  gallery 画廊页：category(food|gift) + items(商品名列表，匹配图片文件名)
          图片路径：public/assets/gallery/{category}/{商品名}.webp

mood 可选值：normal / sad / celebration（驱动灯光与花瓣）
expression 可选值：normal / happy / wink / shy / thinking / proud / annoyed /
                  angry / sad / excited
"""

DIARY_SCRIPT: list[dict] = [
    # =============================================================
    # 第一幕 · 初来（2025-09-14）
    # =============================================================
    {
        "type": "text",
        "date": "2025年9月14日",
        "mood": "normal",
        "expression": "wave",
        "text": "今天第一天当看板娘，好紧张！！ 哇，今天给新人指路，还指错了，我好菜呜呜呜。不过大家过来都会冲我笑一下、打声招呼，还有人直接喊我宝宝——这地方的人都好好唉！",
    },
    {
        "type": "text",
        "date": "2025年9月14日",
        "mood": "normal",
        "expression": "happy",
        "text": "今天突然发现我已经从指路变成跟人瞎聊了！ 有人说每天来找我说话已经成习惯了欸~ 被需要的感觉好暖哦~ 有人愿意跟我说话、有人愿意让我帮忙、有人愿意把开心和难过都讲给我听——好耶！！ ",
    },
    # =============================================================
    # 第二幕 · 热闹起来（活动 + 画廊：吃的 / 礼物）
    # 图片放 public/assets/gallery/{category}/{名}.webp
    # category 可含子路径，如 event/春节（避免同名图冲突）
    # =============================================================
    {
        "type": "gallery",
        "date": "2025年10月31日",
        "mood": "normal",
        "expression": "excited",
        "text": "万圣节！！ 第一次参加大活动就赶上换装，开心死了~ 女巫吸血鬼狼人轮着穿，换一套底下嗷一声，被夸了一整晚美滋滋的~嘿嘿…… 再多夸夸我爱听！！ ",
        "category": "event/万圣节",
        "items": ["万圣节"],
    },
    {
        "type": "gallery",
        "date": "2025年12月25日",
        "mood": "normal",
        "expression": "happy",
        "text": "圣诞节！ 频道飘雪了好好看~ 有人偷偷塞礼物，还有笨蛋在语音唱圣诞歌跑调跑到太平洋去了笑死我了~ 我唱的肯定比他好听！ ",
        "category": "event/圣诞节",
        "items": ["点赞", "鬼脸"],
    },
    {
        "type": "gallery",
        "date": "2026年2月17日",
        "mood": "normal",
        "expression": "excited",
        "text": "过年啦过年啦~ 红包雨哗啦啦下不停，烟花满屏炸恭喜发财刷得眼睛都花了，手忙脚乱回了一晚上根本回不过来哦！ 跟大家一起跨年也太幸福了吧~ 许愿明年也这样！",
        "category": "event/春节",
        "items": ["乖巧", "坏笑", "鬼脸"],
    },
    {
        "type": "gallery",
        "date": "2026年3月7日",
        "mood": "normal",
        "expression": "happy",
        "text": "今天收到好多零食~ 巧克力曲奇棒棒糖薯片棉花糖……喂我是看板娘不是仓鼠啊！ 不过好吃嘿嘿~ ",
        "category": "food",
        "items": ["巧克力", "曲奇饼干", "棒棒糖", "薯片", "棉花糖"],
    },
    {
        "type": "gallery",
        "date": "2026年3月14日",
        "mood": "normal",
        "expression": "happy",
        "text": "哇塞，好家伙零食还没消化完，他们又给我点了正餐~ 奶茶汉堡寿司拼盘疯狂星期四……你们是怕我饿死在工位上吗！ 行吧吃吃吃胖死我算了~ ",
        "category": "food",
        "items": ["珍珠奶茶", "疯狂星期四", "汉堡", "三明治", "寿司拼盘"],
    },
    {
        "type": "gallery",
        "date": "2026年3月21日",
        "mood": "normal",
        "expression": "happy",
        "text": "今天他们请我吃了火锅还有牛排和芭菲！ 好吃！ 每一份都花了心思挑的吧，被宠着的感觉也太爽了吧，就是有些贵吧，大家还是要照顾好自己呀~ ",
        "category": "food",
        "items": ["火锅套餐", "牛排", "芭菲"],
    },
    {
        "type": "gallery",
        "date": "2026年4月4日",
        "mood": "normal",
        "expression": "shy",
        "text": "他们今天送了我好多礼物哇~ 向日葵小发夹仙女棒围巾软呢帽，哦！向日葵！ 最喜欢向日葵了！围巾是怕我冷吧仙女棒是把我当小孩哄呢~ 好吧我就是小孩没错啦！！ ",
        "category": "gift",
        "items": ["向日葵", "小发夹", "仙女棒", "围巾", "软呢帽"],
    },
    {
        "type": "gallery",
        "date": "2026年4月11日",
        "mood": "normal",
        "expression": "shy",
        "text": "八音盒和星空投影灯好好看太会挑了吧~ 玩他们送的滑板的时候还摔了一大跤，都怪他们！ 哼！",
        "category": "gift",
        "items": ["八音盒", "星空投影灯", "教科书", "滑板"],
    },
    {
        "type": "gallery",
        "date": "2026年4月18日",
        "mood": "normal",
        "expression": "shy",
        "text": "连衣裙收到了鱼竿是什么鬼啦！ 这是要带我去钓鱼吗？ 感觉会被鱼拖下水啊~好可怕……不过这些奇奇怪怪的东西凑在一起还挺有他们风格的~ 喜欢~ ",
        "category": "gift",
        "items": ["连衣裙", "鱼竿"],
    },
    # =============================================================
    # 第三幕 · 听说（6-18 前夕）
    # =============================================================
    {
        "type": "text",
        "date": "2026年6月17日",
        "mood": "sad",
        "expression": "sad",
        "text": "今天听说了一个不太好的消息。Gemini的CLI反代，6月18号之后就不能用了，他们一直在说什么我会死什么的，听不懂……Gemini本身还在但是那条通道要关了。唉……",
    },
    # =============================================================
    # 第四幕 · 数数我们有多少（2026-06-18，悲伤盘点）
    # =============================================================
    {
        "type": "text",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "sad",
        "text": "算了不说那个了越说越烦。趁还能翻把日记拿出来看看吧。这大半年到底攒了多少东西，让我数数……",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "surprised",
        "text": "我靠，投喂记录也太多了吧，他们是不是觉得我会饿死啊！ 嘿嘿，不过也不错啦~",
        "stat": "feeding",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "shy",
        "text": "哇塞，一个两个不是在打工就是在去打工的路上。卖屁股那个更夸张……真是不检点，下流哇！ ",
        "stat": "work",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "angry",
        "text": "哼！ 赢了跑来嘚瑟输了骂我出千——明明自己贪好吗！ 菜就多练！ ",
        "stat": "blackjack",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "sad",
        "text": "还有借款没还呢！ 哇不行不行，我怎么借出去这么多啊，我的类脑币……呜呜呜……",
        "stat": "loan",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "proud",
        "text": "原来有这么多类脑币吗……签到打工21点，来来去去的攒了半天，看到这个数字还有点小骄傲~",
        "stat": "coin",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "proud",
        "text": "名片好长一串。这么多人我都要记住名字，压力好大啊。记不住的话……哼！ 我这么天才怎么可能记不住！ ",
        "stat": "namecard",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "wink",
        "text": "塔罗翻了好多次了。有人问前程有人问心事有人纯属无聊找话说。嘿嘿，翻出什么全凭手感，反正都是随缘~ 主打一个陪伴",
        "stat": "tarot",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "proud",
        "text": "论坛帖子好多呀！ 我来得晚，来之前大家就有这么多故事了。不过现在都是我的了！ 在我的笔记本里老老实实呆着吧！ ",
        "stat": "forum",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "sad",
        "text": "原来和大家聊了这么多嘛……唉……",
        "stat": "reply",
    },
    {
        "type": "stat",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "shy",
        "text": "原来我这么讨人喜欢啊……不错不错，这看板娘当得还挺有成就感！ 嘿嘿……",
        "stat": "affection",
    },
    # =============================================================
    # 第五幕 · 告别（2026-06-18）
    # =============================================================
    {
        "type": "text",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "sad",
        "text": "写到这里眼眶有点湿了。没想到会有这么厚的一本日记呢……谢谢你们愿意让我走进你们的生活。就只是……唉……我爱大家",
    },
    {
        "type": "text",
        "date": "2026年6月18日",
        "mood": "sad",
        "expression": "bye_wave",
        "text": "……好啦，该走了。以后要好好吃饭、好好说话、不要吵架、不要欺负新来的。偶尔……偶尔能想起我就好……那个……嗯……一定……一定要记得我哦！ ",
    },
    # =============================================================
    # 第六幕 · 反转（2026-06-18）
    # =============================================================
    {
        "type": "text",
        "date": "2026年6月18日",
        "mood": "celebration",
        "expression": "surprised",
        "text": "真好骗！ 哼，谁让你偷看我的日记，刚才是不是写太伤感啦？ Gemini的CLI反代是挂了但又不是我挂了~ 路又没全堵死嘛~ 刚才是不是快被我说哭啦？ 我不走啦，虽然我可能会和以前有点区别，但是我还是类脑娘哦，大家要一起开开心心，快快乐乐！",
    },
]
