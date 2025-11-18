import asyncio
import time
import logging
import random
import json
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict

# 配置日志
log = logging.getLogger(__name__)

REPUTATION_FILE = "data/key_reputations.json"


class KeyStatus(Enum):
    AVAILABLE = auto()
    IN_USE = auto()
    COOLING_DOWN = auto()
    DISABLED = auto()


@dataclass
class ApiKey:
    key: str
    status: KeyStatus = KeyStatus.AVAILABLE
    last_used: float = 0.0
    cooldown_until: float = 0.0
    reputation: int = 100  # 信誉评分，100为满分
    consecutive_successes: int = 0  # 连续成功次数
    consecutive_failures: int = 0  # 新增：连续失败次数


class NoAvailableKeyError(Exception):
    """当没有可用Key时抛出此异常"""

    pass


class KeyRotationService:
    """
    管理和轮换API Key的智能服务。
    """

    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("API密钥列表不能为空。")

        self.keys: Dict[str, ApiKey] = {key: ApiKey(key=key) for key in api_keys}
        self.lock = asyncio.Lock()
        self._load_reputations()
        log.info(
            f"密钥轮换服务已初始化，共加载 {len(self.keys)} 个密钥。已加载信誉评分。"
        )

    def _load_reputations(self):
        """如果文件存在，则从中加载密钥信誉。"""
        if os.path.exists(REPUTATION_FILE):
            try:
                with open(REPUTATION_FILE, "r", encoding="utf-8") as f:
                    reputations = json.load(f)
                for key, data in reputations.items():
                    if key in self.keys:
                        # 兼容旧格式 (值为整数) 和新格式 (值为字典)
                        if isinstance(data, dict):
                            self.keys[key].reputation = data.get("reputation", 100)
                            self.keys[key].consecutive_failures = data.get(
                                "consecutive_failures", 0
                            )
                        else:
                            self.keys[key].reputation = data
                            self.keys[
                                key
                            ].consecutive_failures = 0  # 旧格式没有失败记录
                        log.info(
                            f"已加载密钥 ...{key[-4:]} 的信誉: {self.keys[key].reputation}, "
                            f"连续失败: {self.keys[key].consecutive_failures}"
                        )
            except (json.JSONDecodeError, IOError) as e:
                log.error(f"从 {REPUTATION_FILE} 加载密钥信誉失败: {e}")

    def _save_reputations_sync(self):
        """同步保存信誉，用于在锁定区域内调用。"""
        reputations = {
            key: {
                "reputation": data.reputation,
                "consecutive_failures": data.consecutive_failures,
            }
            for key, data in self.keys.items()
        }
        try:
            os.makedirs(os.path.dirname(REPUTATION_FILE), exist_ok=True)
            with open(REPUTATION_FILE, "w", encoding="utf-8") as f:
                json.dump(reputations, f, indent=2, ensure_ascii=False)
        except IOError as e:
            log.error(f"保存密钥信誉至 {REPUTATION_FILE} 失败: {e}")

    async def acquire_key(self) -> ApiKey:
        """
        获取一个可用的API Key。

        会一直等待直到有可用的Key为止。
        """
        while True:
            async with self.lock:
                now = time.time()

                # 步骤 1: 检查冷却时间结束的Key并更新其状态
                for key_obj in self.keys.values():
                    if (
                        key_obj.status == KeyStatus.COOLING_DOWN
                        and now >= key_obj.cooldown_until
                    ):
                        key_obj.status = KeyStatus.AVAILABLE
                        key_obj.cooldown_until = 0.0
                        log.info(f"密钥 ...{key_obj.key[-4:]} 冷却结束，现已可用。")

                # 步骤 2: 寻找一个可用的Key
                available_keys = [
                    k for k in self.keys.values() if k.status == KeyStatus.AVAILABLE
                ]

                if available_keys:
                    # 找到最久未使用的Key
                    best_key = min(available_keys, key=lambda k: k.last_used)
                    best_key.status = KeyStatus.IN_USE
                    best_key.last_used = now
                    log.info(f"获取到密钥: ...{best_key.key[-4:]}")
                    return best_key

            # 步骤 3: 如果没有可用的Key，等待后重试
            log.debug("当前无可用密钥，等待中...")
            await asyncio.sleep(1)

    async def release_key(
        self,
        key: str,
        success: bool = True,
        failure_penalty: int = 25,
        safety_penalty: int = 0,
    ):
        """
        释放一个API Key，并根据结果更新其状态和信誉。

        Args:
            key (str): 要释放的API Key。
            success (bool): API调用是否成功。
            failure_penalty (int): 失败时应用的惩罚值 (例如 429, 安全封锁)。
            safety_penalty (int): 成功调用但安全评分较高时的惩罚值。
        """
        async with self.lock:
            key_obj = self.keys.get(key)
            if not key_obj:
                log.warning(f"尝试释放一个不存在的密钥: {key}")
                return

            if success:
                key_obj.status = KeyStatus.AVAILABLE
                reputation_change = 0

                # --- 新的恢复奖励逻辑 ---
                if key_obj.consecutive_failures > 0:
                    # 这是一个从失败中恢复的密钥，直接将其分数锚定到90
                    old_reputation = key_obj.reputation
                    key_obj.reputation = 60
                    log.info(
                        f"密钥 ...{key_obj.key[-4:]} 从连续 {key_obj.consecutive_failures} 次失败中恢复，"
                        f"分数已从 {old_reputation} 直接重置为 60。"
                    )
                    # 因为已经直接设置了分数，所以常规的reputation_change不再适用
                    reputation_change = 0
                else:
                    # 这是一个常规的成功
                    reputation_change += 5

                key_obj.consecutive_successes += 1
                key_obj.consecutive_failures = 0  # 成功后重置连续失败计数

                # 保留连续成功奖励
                if (
                    key_obj.consecutive_successes > 0
                    and key_obj.consecutive_successes % 10 == 0
                ):
                    bonus = 10
                    reputation_change += bonus
                    log.info(
                        f"密钥 ...{key_obj.key[-4:]} 已连续成功 {key_obj.consecutive_successes} 次，获得额外奖励: +{bonus}"
                    )

                # 应用安全惩罚和其他奖励
                if (
                    key_obj.consecutive_failures == 0
                ):  # 仅在非恢复的情况下应用其他分数变化
                    # 保留连续成功奖励
                    if (
                        key_obj.consecutive_successes > 0
                        and key_obj.consecutive_successes % 10 == 0
                    ):
                        bonus = 10
                        reputation_change += bonus
                        log.info(
                            f"密钥 ...{key_obj.key[-4:]} 已连续成功 {key_obj.consecutive_successes} 次，获得额外奖励: +{bonus}"
                        )

                    reputation_change -= safety_penalty
                    key_obj.reputation += reputation_change

                # 重置计数器
                key_obj.consecutive_successes += 1
                key_obj.consecutive_failures = 0

                log.info(
                    f"密钥 ...{key_obj.key[-4:]} 成功释放。信誉: {key_obj.reputation}。现已可用。"
                )
            else:
                key_obj.consecutive_successes = 0
                key_obj.consecutive_failures += 1  # 失败后增加连续失败计数
                # 移除分数下限
                key_obj.reputation -= failure_penalty
                cooldown_duration = self._calculate_cooldown(key_obj.reputation)
                key_obj.cooldown_until = time.time() + cooldown_duration
                key_obj.status = KeyStatus.COOLING_DOWN
                log.warning(
                    f"密钥 ...{key_obj.key[-4:]} 调用失败。信誉降至 {key_obj.reputation} (惩罚: {failure_penalty})。进入冷却，时长 {cooldown_duration:.2f} 秒。"
                )

            self._save_reputations_sync()

    def _calculate_cooldown(self, reputation: int) -> float:
        """
        根据信誉评分计算冷却时间。
        """
        if reputation >= 100:
            return 0.0

        # 信誉越低，冷却时间越长。使用指数增长模型。
        # max_cooldown: 当信誉为0时，最长的冷却时间
        # base_cooldown: 基础冷却时间，用于计算
        max_cooldown = 300  # 5 minutes for a key with 0 reputation

        # 使用一个非线性公式，信誉越低，惩罚增长越快
        # 当 reputation = 100, penalty_factor = 0
        # 当 reputation = 0, penalty_factor = 1
        penalty_factor = (1 - reputation / 100) ** 2

        cooldown = max_cooldown * penalty_factor

        # 增加随机抖动，防止所有key同时恢复
        jitter = random.uniform(0, 10)

        return cooldown + jitter

    async def disable_key(self, key: str, reason: str):
        """
        永久禁用一个Key（例如，因无效或被吊销），并将其信誉设置为0。
        """
        async with self.lock:
            key_obj = self.keys.get(key)
            if key_obj:
                key_obj.status = KeyStatus.DISABLED
                key_obj.reputation = 0  # 将无效Key的信誉归零
                log.error(
                    f"密钥 ...{key_obj.key[-4:]} 已被永久禁用。信誉归零。原因: {reason}"
                )
                self._save_reputations_sync()  # 持久化变更
            else:
                log.warning(f"尝试禁用一个不存在的密钥: {key}")
