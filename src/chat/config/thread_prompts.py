# -*- coding: utf-8 -*-
import random
from src.chat.config.chat_config import WARMUP_MESSAGES


def get_random_praise_prompt():
    """从列表中随机选择一个暖贴提示词"""
    return random.choice(WARMUP_MESSAGES["consent_prompts"])
