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

    pass


SELL_BODY_EVENTS = [
    {
        "event_type": "sell_body",
        "name": "担任足模",
        "description": "你精心保养的双脚吸引了恋足癖的目光，他们愿意为你的照片一掷千金。",
        "reward_range_min": 300,
        "reward_range_max": 500,
        "good_event_description": "一位富有的收藏家认为你的脚是“上帝的艺术品”，高价买断了你未来一年的所有照片版权。",
        "good_event_modifier": 2.0,
        "bad_event_description": "一位客户抱怨你的脚趾不够圆润，要求退款。",
        "bad_event_modifier": 0.4,
    },
    {
        "event_type": "sell_body",
        "name": "鼓励程序员",
        "description": "你穿着可爱的女仆装，为一群疲惫的程序员加油打气，并为他们喂食。",
        "reward_range_min": 250,
        "reward_range_max": 400,
        "good_event_description": "你的鼓励激发了一位程序员的灵感，他解决了困扰已久的BUG，并分给你项目奖金。",
        "good_event_modifier": 1.6,
        "bad_event_description": "你不小心把咖啡洒在了服务器上，造成了小小的混乱。",
        "bad_event_modifier": 0.2,
    },
    {
        "event_type": "sell_body",
        "name": "游戏陪玩",
        "description": "你陪一位老板打游戏，用你甜美的声音喊着“老板666”。",
        "reward_range_min": 220,
        "reward_range_max": 380,
        "good_event_description": "你带老板连续吃鸡，他一高兴，给你发了个大红包。",
        "good_event_modifier": 1.7,
        "bad_event_description": "你的网络突然卡顿，导致老板落地成盒，他气得一分钱都没给。",
        "bad_event_modifier": 0.1,
    },
    {
        "event_type": "sell_body",
        "name": "私人导游",
        "description": "你带领一位神秘的游客参观城市，并应他的要求进行角色扮演。",
        "reward_range_min": 280,
        "reward_range_max": 450,
        "good_event_description": "游客其实是一位微服私访的王子，他对你的服务非常满意，并赠予你皇家珠宝。",
        "good_event_modifier": 2.2,
        "bad_event_description": "你迷路了，把游客带到了一个废弃的工厂，他吓得报了警。",
        "bad_event_modifier": -0.5,
    },
    {
        "event_type": "sell_body",
        "name": "猫咖服务员",
        "description": "你在一家猫咖扮演成猫娘，为客人们提供服务，还要学猫叫。",
        "reward_range_min": 200,
        "reward_range_max": 320,
        "good_event_description": "你的猫娘扮相太可爱了，一位客人忍不住给你打赏了很多小费。",
        "good_event_modifier": 1.5,
        "bad_event_description": "你对猫毛过敏，不停地打喷嚏，吓跑了客人和猫。",
        "bad_event_modifier": 0.3,
    },
    {
        "event_type": "sell_body",
        "name": "人体彩绘模特",
        "description": "你作为模特，让一位艺术家在你的背上进行创作。",
        "reward_range_min": 350,
        "reward_range_max": 500,
        "good_event_description": "艺术家的作品大获成功，在拍卖会上卖出了高价，你因此获得了一大笔分红。",
        "good_event_modifier": 1.9,
        "bad_event_description": "颜料质量不好，导致你皮肤过敏，不得不去看医生。",
        "bad_event_modifier": -0.2,
    },
    {
        "event_type": "sell_body",
        "name": "提供叫醒服务",
        "description": "每天清晨，你用你甜美或性感的声音，通过电话唤醒一个个沉睡的灵魂。",
        "reward_range_min": 210,
        "reward_range_max": 360,
        "good_event_description": "一位客户因为你的叫醒服务从未迟到，拿到了全勤奖，他分了一半给你。",
        "good_event_modifier": 1.6,
        "bad_event_description": "你睡过头了，忘记给客户打电话，导致他错过了重要的会议。",
        "bad_event_modifier": -1.0,
    },
    {
        "event_type": "sell_body",
        "name": "担任私人健身教练",
        "description": "你指导一位身材走样的富豪进行一对一的私密健身训练。",
        "reward_range_min": 300,
        "reward_range_max": 480,
        "good_event_description": "在你的指导下，富豪成功减重20斤，他激动地给了你一张不限额度的信用卡。",
        "good_event_modifier": 2.5,
        "bad_event_description": "你不小心把杠铃片掉在了富豪的脚上，他疼得嗷嗷叫。",
        "bad_event_modifier": 0.1,
    },
    {
        "event_type": "sell_body",
        "name": "在线情感咨询",
        "description": "你在网上倾听他人的情感烦恼，并用温柔的话语给予安慰。",
        "reward_range_min": 240,
        "reward_range_max": 420,
        "good_event_description": "你成功挽救了一对濒临分手的情侣，他们为了感谢你，给你送了一份大礼。",
        "good_event_modifier": 1.7,
        "bad_event_description": "你的建议适得其反，导致客户和他的伴侣大吵一架，你被拉黑了。",
        "bad_event_modifier": 0.2,
    },
    {
        "event_type": "sell_body",
        "name": "ASMR主播",
        "description": "你为深夜失眠的听众录制ASMR，用各种声音抚慰他们躁动的心。",
        "reward_range_min": 200,
        "reward_range_max": 350,
        "good_event_description": "一位富豪被你的声音深深吸引，为你刷了超级火箭。",
        "good_event_modifier": 1.8,
        "bad_event_description": "你不小心在录音时打了个嗝，被听众投诉了。",
        "bad_event_modifier": 0.5,
    },
]
