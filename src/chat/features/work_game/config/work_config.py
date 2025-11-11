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
