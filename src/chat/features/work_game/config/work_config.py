import random


class WorkConfig:
    # --- 游戏核心参数 ---
    EVENT_CHANCE = 0.3  # 30%的概率触发事件
    GOOD_EVENT_CHANCE = 0.5  # 在触发事件的情况下，50%概率是好事件

    # --- 冷却和全勤奖励配置 ---
    COOLDOWN_HOURS = 2  # 工作冷却时间（小时）
    STREAK_DAYS = 3  # 达成全勤奖励所需连续天数
    STREAK_REWARD = 100  # 全勤奖励金额
    SELL_BODY_COOLDOWN_HOURS = 1  # 卖屁股冷却时间（小时）

    # --- 每日次数限制 ---
    MAX_WORK_PER_DAY = 3  # 每日最多打工次数
    MAX_SELL_BODY_PER_DAY = 3  # 每日最多卖屁股次数

    SELL_BODY_ACTIONS = [
        {
            "name": "跳钢管舞",
            "description": "你在舞台上伴随着迷离的音乐尽情舞动，台下的观众为你疯狂。",
            "reward_range": (150, 400),
            "good_event": {
                "description": "你的舞姿吸引了一位富豪的注意，他为你包下了全场。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "跳得太投入，不小心从钢管上滑了下来，扭伤了脚踝，不得不花钱治疗。",
                "modifier": -0.5,
            },
        },
        {
            "name": "进行私密摄影",
            "description": "在摄影师的指导下，你摆出各种撩人的姿势，镜头记录下了你最性感的一面。",
            "reward_range": (200, 500),
            "good_event": {
                "description": "你的照片被一家知名杂志看中，买下了版权，你小赚一笔。",
                "modifier": 1.8,
            },
            "bad_event": {
                "description": "摄影师是个骗子！他不仅没给你钱，还把你的照片泄露到了网上。",
                "modifier": -1.0,
            },
        },
        {
            "name": "参加富豪派对",
            "description": "你作为特邀嘉宾参加了一场奢华的私人派对，与名流们谈笑风生。",
            "reward_range": (300, 800),
            "good_event": {
                "description": "你风趣的谈吐和优雅的举止吸引了一位贵妇，她给了你一张不记名银行卡。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "你在派对上喝多了，不小心打碎了一个价值不菲的古董花瓶，不得不倾家荡产来赔偿。",
                "modifier": -2.0,
            },
        },
        {
            "name": "担任兔女郎",
            "description": "你穿上可爱的兔女郎装，在高级会所里为客人们端茶送水。",
            "reward_range": (100, 250),
            "good_event": {
                "description": "客人们被你的可爱模样迷住了，小费多得你口袋都装不下。",
                "modifier": 2.2,
            },
            "bad_event": {
                "description": "你被一个难缠的客人骚扰，不仅没拿到小费，还受了一肚子气。",
                "modifier": -0.2,
            },
        },
        {
            "name": "录制ASMR",
            "description": "你在麦克风前轻声细语，用各种声音为网络另一端的听众带去舒适和放松。",
            "reward_range": (80, 300),
            "good_event": {
                "description": "你的声音被一位大佬听到，他为你刷了价值连城的虚拟礼物！",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "你的邻居嫌你半夜太吵报了警，你被罚款并口头教育。",
                "modifier": -0.8,
            },
        },
        {
            "name": "在SM俱乐部兼职",
            "description": "你穿上紧身皮衣，挥舞着小皮鞭，满足了一些客人独特的癖好。",
            "reward_range": (250, 600),
            "good_event": {
                "description": "一位客人被你女王般的气场所征服，心甘情愿地成为了你的“奴隶”，并上交了所有财产。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "你玩得太过火，不小心把一位重要客人弄伤了，俱乐部让你承担全部的赔偿费用。",
                "modifier": -1.5,
            },
        },
        {
            "name": "担任足模",
            "description": "你精心保养的双脚吸引了恋足癖的目光，他们愿意为你的照片一掷千金。",
            "reward_range": (120, 350),
            "good_event": {
                "description": "一位富有的收藏家认为你的脚是“上帝的艺术品”，高价买断了你未来一年的所有照片版权。",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "你在拍摄时不小心崴了脚，导致数周无法工作，还错过了几个大单。",
                "modifier": -0.7,
            },
        },
        {
            "name": "提供“叫醒”服务",
            "description": "每天清晨，你用你甜美或性感的声音，通过电话唤醒一个个沉睡的灵魂。",
            "reward_range": (50, 150),
            "good_event": {
                "description": "你的一个客户是个声控大佬，他被你的声音深深吸引，为你开通了超级VIP包年服务。",
                "modifier": 2.8,
            },
            "bad_event": {
                "description": "你不小心睡过了头，忘记叫醒一位有重要会议的客户，导致他损失惨重，你需要全额赔偿。",
                "modifier": -2.0,
            },
        },
    ]

    JOBS = [
        {
            "name": "咖啡店店员",
            "description": "你在咖啡店辛勤工作，赚取了一些收入。",
            "reward_range": (10, 30),
            "good_event": {
                "description": "一位慷慨的顾客给了你一大笔小费！",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "你不小心打碎了一套昂贵的咖啡杯，工资被扣了一半。",
                "modifier": 0.5,
            },
        },
        {
            "name": "图书馆管理员",
            "description": "你整理了一天书籍，虽然有些枯燥，但也有所收获。",
            "reward_range": (15, 25),
            "good_event": {
                "description": "你在旧书里发现了一张被遗忘的藏宝图，卖了点钱。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "你因为工作失误被读者投诉，奖金被取消了。",
                "modifier": 0.2,
            },
        },
        {
            "name": "自由撰稿人",
            "description": "你完成了一篇稿件，获得了稿费。",
            "reward_range": (20, 50),
            "good_event": {
                "description": "你的文章大受欢迎，获得了额外的奖金！",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "甲方对你的稿件不满意，要求重写，稿费减半。",
                "modifier": 0.5,
            },
        },
        {
            "name": "快递员",
            "description": "你穿梭在城市的大街小巷，派送了许多包裹。",
            "reward_range": (25, 40),
            "good_event": {
                "description": "你帮助了一位遇到困难的老奶奶，她给了你一些感谢金。",
                "modifier": 1.8,
            },
            "bad_event": {
                "description": "你的电瓶车坏在了半路，修理花了不少钱。",
                "modifier": 0.6,
            },
        },
        {
            "name": "花店店员",
            "description": "你修剪花枝，包装花束，与美丽的花朵为伴。",
            "reward_range": (12, 28),
            "good_event": {
                "description": "一位客人为婚礼预订了大量鲜花，你拿到了一笔丰厚的提成。",
                "modifier": 2.2,
            },
            "bad_event": {
                "description": "由于天气原因，一批鲜花枯萎了，你承担了部分损失。",
                "modifier": 0.7,
            },
        },
        {
            "name": "宠物美容师",
            "description": "你为可爱的宠物们洗澡、修剪毛发，让它们焕然一新。",
            "reward_range": (30, 60),
            "good_event": {
                "description": "一位富有的宠物主人对你的服务非常满意，给了你很多小费。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "一只淘气的猫咪抓伤了你，你不得不去打疫苗。",
                "modifier": 0.4,
            },
        },
        {
            "name": "餐厅服务员",
            "description": "你在繁忙的餐厅里为客人点餐、上菜，获得了小费。",
            "reward_range": (18, 35),
            "good_event": {
                "description": "你遇到了一桌非常大方的客人，他们给了你相当于一天工资的小费。",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "你上错了菜，被经理狠狠地批评了一顿，还扣了钱。",
                "modifier": 0.3,
            },
        },
        {
            "name": "在线客服",
            "description": "你耐心解答了许多用户的问题，维护了公司的良好形象。",
            "reward_range": (20, 30),
            "good_event": {
                "description": "你解决了一个非常棘手的客户问题，获得了“服务之星”奖金。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "你被一个无理取闹的客户纠缠了很久，身心俱疲，还被投诉了。",
                "modifier": 0.8,
            },
        },
        {
            "name": "数据标注员",
            "description": "你为人工智能的发展做出了贡献，标注了大量数据。",
            "reward_range": (25, 45),
            "good_event": {
                "description": "你发现了一个数据标注的技巧，效率大增，获得了绩效奖金。",
                "modifier": 1.8,
            },
            "bad_event": {
                "description": "你因为注意力不集中，标错了一批重要数据，被罚款了。",
                "modifier": 0.5,
            },
        },
        {
            "name": "游戏代练",
            "description": "你凭借高超的游戏技巧，帮助客户提升了段位。",
            "reward_range": (40, 80),
            "good_event": {
                "description": "你打出了一波连胜，老板非常高兴，给了你一个大红包。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "网络突然中断，你输掉了一场关键的比赛，需要赔偿客户。",
                "modifier": 0.1,
            },
        },
        {
            "name": "网络主播",
            "description": "你进行了一场有趣的直播，收到了观众的打赏。",
            "reward_range": (10, 100),
            "good_event": {
                "description": "一位神秘的“神豪”进入你的直播间，送出了价值不菲的礼物！",
                "modifier": 5.0,
            },
            "bad_event": {
                "description": "直播时设备突然出现故障，人气大跌。",
                "modifier": 0.3,
            },
        },
        {
            "name": "家教",
            "description": "你帮助学生提高了成绩，得到了家长和学生的认可。",
            "reward_range": (50, 150),
            "good_event": {
                "description": "你的学生在考试中取得了巨大进步，家长高兴地给了你一个大红包。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "你被学生的问题难住了，场面一度十分尴尬，专业形象受损。",
                "modifier": 0.9,
            },
        },
        {
            "name": "程序员",
            "description": "你解决了一个棘手的bug，项目得以顺利进行。",
            "reward_range": (80, 200),
            "good_event": {
                "description": "你写出的代码性能卓越，获得了公司的技术创新奖。",
                "modifier": 1.5,
            },
            "bad_event": {
                "description": "你提交的代码引发了线上故障，整个周末都在加班修复。",
                "modifier": 0.7,
            },
        },
        {
            "name": "平面设计师",
            "description": "你设计了一款精美的海报，获得了客户的好评。",
            "reward_range": (60, 180),
            "good_event": {
                "description": "你的作品被一家大公司看中，买下了版权，你大赚一笔。",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "你的电脑突然崩溃，没来得及保存的设计稿全部丢失了。",
                "modifier": 0.1,
            },
        },
        {
            "name": "翻译",
            "description": "你翻译了一份重要文件，促进了跨文化交流。",
            "reward_range": (50, 120),
            "good_event": {
                "description": "你出色的翻译能力获得了一位重要人物的赏识，他为你介绍了一个大项目。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "你因为一个翻译错误，造成了不小的误会，不得不道歉并赔偿。",
                "modifier": 0.6,
            },
        },
        {
            "name": "市场调研员",
            "description": "你收集了大量市场数据，为公司的决策提供了支持。",
            "reward_range": (30, 70),
            "good_event": {
                "description": "你敏锐地发现了一个新的市场机会，公司采纳了你的建议并给予奖励。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "你辛苦收集的数据被证明是无效的，白忙活了一场。",
                "modifier": 0.5,
            },
        },
        {
            "name": "健身教练",
            "description": "你指导学员进行科学的锻炼，帮助他们塑造了理想的身材。",
            "reward_range": (70, 150),
            "good_event": {
                "description": "一位学员在健身比赛中获奖，你的知名度大大提升，吸引了更多客户。",
                "modifier": 1.8,
            },
            "bad_event": {
                "description": "你在指导时分心，导致学员受伤，你需要承担部分医药费。",
                "modifier": 0.4,
            },
        },
        {
            "name": "摄影师",
            "description": "你捕捉了许多精彩的瞬间，创作出令人惊艳的作品。",
            "reward_range": (50, 250),
            "good_event": {
                "description": "你的一幅作品在国际摄影大赛中获奖，名声大噪！",
                "modifier": 4.0,
            },
            "bad_event": {
                "description": "你的相机意外掉入水中，维修费用高昂。",
                "modifier": 0.2,
            },
        },
        {
            "name": "导游",
            "description": "你带领游客领略了当地的风土人情，分享了有趣的故事。",
            "reward_range": (40, 100),
            "good_event": {
                "description": "一个旅游团对你的服务赞不绝口，所有人都给了你丰厚的小费。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "你带错了路，耽误了游客的行程，被投诉并罚款。",
                "modifier": 0.5,
            },
        },
        {
            "name": "活动策划",
            "description": "你成功策划了一场大型活动，现场气氛热烈。",
            "reward_range": (60, 160),
            "good_event": {
                "description": "活动效果远超预期，赞助商非常满意，追加了奖金。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "活动现场出现了意外情况，你不得不花费额外资金来解决。",
                "modifier": 0.7,
            },
        },
        {
            "name": "面包师",
            "description": "你烘焙出香甜可口的面包，给人们带来了幸福感。",
            "reward_range": (25, 55),
            "good_event": {
                "description": "你研发的新口味面包大受欢迎，成为了店里的爆款。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "烤箱坏了，一整炉面包都烤糊了。",
                "modifier": 0.3,
            },
        },
        {
            "name": "调酒师",
            "description": "你调制出独具风味的鸡尾酒，赢得了顾客的赞赏。",
            "reward_range": (35, 75),
            "good_event": {
                "description": "你自创的一款鸡尾酒被评为“本月最佳”，酒吧给了你特别奖励。",
                "modifier": 2.2,
            },
            "bad_event": {
                "description": "你失手打翻了一瓶昂贵的酒，需要从工资里扣除。",
                "modifier": 0.4,
            },
        },
        {
            "name": "建筑工人",
            "description": "你挥洒汗水，为城市的建设添砖加瓦。",
            "reward_range": (45, 90),
            "good_event": {
                "description": "由于项目提前完工，你和工友们都拿到了一笔额外的奖金。",
                "modifier": 1.5,
            },
            "bad_event": {
                "description": "你不小心在工地上受了轻伤，需要休息几天，还花了医药费。",
                "modifier": 0.6,
            },
        },
        {
            "name": "汽车修理工",
            "description": "你修好了抛锚的汽车，让车主得以继续前行。",
            "reward_range": (55, 110),
            "good_event": {
                "description": "你解决了一个连老师傅都没搞定的难题，赢得了大家的尊重和一笔奖金。",
                "modifier": 1.8,
            },
            "bad_event": {
                "description": "你判断失误，换错了零件，不得不自己承担损失。",
                "modifier": 0.5,
            },
        },
        {
            "name": "农民",
            "description": "春种秋收，你收获了辛勤耕耘的果实。",
            "reward_range": (15, 60),
            "good_event": {
                "description": "今年风调雨顺，农作物大丰收，你的收入翻了一番。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "一场突如其来的冰雹毁掉了你大部分的庄稼。",
                "modifier": 0.1,
            },
        },
        {
            "name": "渔夫",
            "description": "你迎着朝阳出海，满载而归。",
            "reward_range": (20, 80),
            "good_event": {
                "description": "你捕获了一群稀有的鱼类，卖出了一个好价钱。",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "你的渔网被海底的杂物挂破了，损失惨重。",
                "modifier": 0.2,
            },
        },
        {
            "name": "护士",
            "description": "你悉心照料病人，守护着他们的健康。",
            "reward_range": (60, 130),
            "good_event": {
                "description": "你及时发现了一位病人的危急情况，挽救了他的生命，获得了医院的表彰。",
                "modifier": 1.5,
            },
            "bad_event": {
                "description": "你因为太过劳累，给病人发错了药，幸好及时发现，但还是被扣了奖金。",
                "modifier": 0.8,
            },
        },
        {
            "name": "保安",
            "description": "你维护了一方平安，让人们感到安心。",
            "reward_range": (20, 40),
            "good_event": {
                "description": "你抓到了一个小偷，受到了嘉奖。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "你因为打瞌睡被主管发现，被罚站了半天，还扣了工资。",
                "modifier": 0.7,
            },
        },
        {
            "name": "清洁工",
            "description": "你用辛勤的劳动，换来了城市的整洁。",
            "reward_range": (15, 30),
            "good_event": {
                "description": "你在打扫时捡到了一个贵重物品并上交，失主给了你一些感谢费。",
                "modifier": 2.5,
            },
            "bad_event": {
                "description": "你不小心把污水溅到了一个路人身上，不得不道歉并赔偿洗衣费。",
                "modifier": 0.5,
            },
        },
        {
            "name": "艺术家",
            "description": "灵感迸发，你创作出了一件杰作，但市场反响未知。",
            "reward_range": (5, 300),
            "good_event": {
                "description": "你的作品突然被一位收藏家高价买走，你一夜成名！",
                "modifier": 10.0,
            },
            "bad_event": {
                "description": "你的作品无人问津，你甚至需要倒贴钱来支付展览场地的费用。",
                "modifier": 0.01,
            },
        },
        {
            "name": "科学家",
            "description": "你在实验室里取得了重大突破，为科学进步做出了贡献。",
            "reward_range": (100, 500),
            "good_event": {
                "description": "你的研究成果获得了诺贝尔奖提名！获得了巨额奖金。",
                "modifier": 5.0,
            },
            "bad_event": {
                "description": "实验发生了意外，毁坏了昂贵的仪器，你的研究经费被削减了。",
                "modifier": 0.3,
            },
        },
        {
            "name": "考古学家",
            "description": "你发现了一处古代遗迹，揭开了历史的神秘面纱。",
            "reward_range": (80, 400),
            "good_event": {
                "description": "你在遗迹中发现了一件国宝级的文物，获得了国家级的奖励！",
                "modifier": 3.0,
            },
            "bad_event": {
                "description": "你被遗迹里的机关困住了，好不容易才逃出来，还弄坏了探测设备。",
                "modifier": 0.4,
            },
        },
        {
            "name": "洗碗工",
            "description": "你在后厨洗了一天的碗，腰酸背痛，手指发白。",
            "reward_range": (5, 15),
            "good_event": {
                "description": "老板今天心情好，多给了你一点小费。",
                "modifier": 1.5,
            },
            "bad_event": {
                "description": "你不小心打碎了一个盘子，今天的工钱全被扣光了。",
                "modifier": 0.0,
            },
        },
        {
            "name": "传单派发员",
            "description": "你顶着烈日或寒风在街头发了一天传单，口干舌燥。",
            "reward_range": (8, 20),
            "good_event": {
                "description": "你派发传单时，遇到了一位正在招聘的公司老板，他给了你一个面试机会和一些车马费。",
                "modifier": 2.0,
            },
            "bad_event": {
                "description": "你发的传单被人随手扔进了垃圾桶，还被城管罚了款。",
                "modifier": 0.2,
            },
        },
        {
            "name": "工地搬砖",
            "description": "你在尘土飞扬的工地上搬了一天砖，汗水浸透了衣衫。",
            "reward_range": (10, 25),
            "good_event": {
                "description": "你干活又快又好，工头把你推荐给了另一个薪水更高的工地。",
                "modifier": 1.5,
            },
            "bad_event": {
                "description": "今天天气太热，你不幸中暑了，还得花钱看病。",
                "modifier": 0.1,
            },
        },
        {
            "name": "流水线工人",
            "description": "你重复着同一个动作一整天，感觉自己像个机器人。",
            "reward_range": (12, 22),
            "good_event": {
                "description": "你因为表现出色，被调到了一个更轻松的岗位，工资还涨了。",
                "modifier": 1.8,
            },
            "bad_event": {
                "description": "你操作的机器突然坏了，你被认定为责任人，需要承担维修费用。",
                "modifier": 0.3,
            },
        },
    ]

    @staticmethod
    def get_random_job():
        return random.choice(WorkConfig.JOBS)

    @staticmethod
    def get_job_reward(job):
        base_reward = random.randint(job["reward_range"][0], job["reward_range"][1])

        event_description = None

        if random.random() < WorkConfig.EVENT_CHANCE:
            if random.random() < WorkConfig.GOOD_EVENT_CHANCE:
                event = job.get("good_event")
                if event:
                    base_reward *= event["modifier"]
                    event_description = event["description"]
            else:
                event = job.get("bad_event")
                if event:
                    base_reward *= event["modifier"]
                    event_description = event["description"]

        return int(base_reward), event_description

    @staticmethod
    def get_random_sell_body_action():
        return random.choice(WorkConfig.SELL_BODY_ACTIONS)

    @staticmethod
    def get_sell_body_action_reward(job):
        base_reward = random.randint(job["reward_range"][0], job["reward_range"][1])
        event_description = None

        if random.random() < WorkConfig.EVENT_CHANCE:
            if random.random() < WorkConfig.GOOD_EVENT_CHANCE:
                event = job.get("good_event")
                if event:
                    base_reward *= event["modifier"]
                    event_description = event["description"]
            else:
                event = job.get("bad_event")
                if event:
                    # 负向的 modifier 直接作用于基础奖励
                    reward_change = base_reward * abs(event["modifier"])
                    if event["modifier"] < 0:
                        base_reward -= reward_change
                    else:
                        base_reward *= event["modifier"]  # 兼容旧的乘法模式
                    event_description = event["description"]

        return int(base_reward), event_description
