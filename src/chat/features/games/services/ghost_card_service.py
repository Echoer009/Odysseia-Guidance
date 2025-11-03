# -*- coding: utf-8 -*-

import random
import logging
import re
from typing import Dict, List, Tuple, Optional
from enum import Enum
from src.chat.features.games.config.text_config import text_config

log = logging.getLogger(__name__)


class AIStrategy(Enum):
    """AI策略等级"""

    LOW = "低级"  # 30%概率
    MEDIUM = "中级"  # 50%概率
    HIGH = "高级"  # 20%概率
    SUPER = "超级"  # 1%概率特殊模式


PAYOUT_RATIOS = {
    AIStrategy.LOW: 1,
    AIStrategy.MEDIUM: 2,
    AIStrategy.HIGH: 5,
    AIStrategy.SUPER: 10,
}


class GhostCardService:
    """抽鬼牌游戏服务类"""

    def __init__(self):
        self.active_games: Dict[str, Dict] = {}  # 游戏ID -> 游戏数据
        self.strategy_weights = {
            AIStrategy.LOW: 25,
            AIStrategy.MEDIUM: 50,
            AIStrategy.HIGH: 25,
        }

    def generate_deck(self) -> List[str]:
        """生成一副牌（两套花色）"""
        deck = []
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

        # 使用用户提供的表情符号，并为缺失的牌张提供备用
        hearts_emojis = {
            "A": "<:A_of_hearts:1412061688638869676>",
            "2": "<:2_of_hearts:1412060610035716288>",
            "3": "<:3_of_hearts:1412060621578567871>",
            "5": "<:5_of_hearts:1412061525828702230>",
            "6": "<:6_of_hearts:1412061544056881172>",
            "7": "<:7_of_hearts:1412061560033247434>",
            "8": "<:8_of_hearts:1412061575744852150>",
            "9": "<:9_of_hearts:1412061596142014494>",
            "10": "<:10_of_hearts:1412061609752527009>",
            "J": "<:J_of_hearts:1412061633479446548>",
            "Q": "<:Q_of_hearts:1412061650185355307>",
            "K": "<:K_of_hearts:1412061671958249653>",
            "4": "<:4_of_hearts:1412060665404985496>",
        }

        spades_emojis = {
            "A": "<:A_of_spades:1412060596936904764>",
            # 其他黑桃牌使用梅花代替
            "2": "<:2_of_clover:1412060184058269736>",
            "3": "<:3_of_clover:1412060215511224360>",
            "4": "<:4_of_clover:1412060245932376147>",
            "5": "<:5_of_clover:1412060266153246811>",
            "6": "<:6_of_clover:1412060317093203988>",
            "7": "<:7_of_clover:1412060336118304858>",
            "8": "<:8_of_clover:1412060357010264185>",
            "9": "<:9_of_clover:1412060372931707030>",
            "10": "<:10_of_clover:1412060393139998770>",
            "J": "<:J_of_clover:1412060420398907463>",
            "Q": "<:Q_of_clover:1412060476967354398>",
            "K": "<:K_of_clover:1412060525193330718>",
        }

        for rank in ranks:
            if rank in hearts_emojis and rank in spades_emojis:
                deck.append(hearts_emojis[rank])
                deck.append(spades_emojis[rank])

        deck.append("🃏")  # 鬼牌

        return deck

    def determine_ai_strategy(self) -> AIStrategy:
        """随机确定AI策略"""
        # 1%概率出现超级模式
        if random.random() < 0.01:
            return AIStrategy.SUPER

        # 正常策略分布
        strategies = list(self.strategy_weights.keys())
        weights = list(self.strategy_weights.values())
        return random.choices(strategies, weights=weights, k=1)[0]

    def _get_bot_reaction(
        self,
        situation: str,
        is_ghost: bool,
        strategy: AIStrategy,
        ai_has_ghost: bool,
        deception_failed: bool = False,
    ) -> Tuple[str, str, Optional[str]]:
        """
        根据情况和策略决定机器人的反应
        返回: (text, image_url, deception_type)
        deception_type: 'deceive_ghost' 或 'deceive_safe', 如果没有欺骗则为 None
        """
        deception_type = None

        # 定义不同策略下欺骗的概率
        deception_chance = {
            AIStrategy.LOW: 0.05,
            AIStrategy.MEDIUM: 0.25,
            AIStrategy.HIGH: 0.50,
            AIStrategy.SUPER: 0.80,
        }

        # 只有在AI手上有鬼牌时才能进行欺骗
        use_deception = ai_has_ghost and random.random() < deception_chance.get(
            strategy, 0.25
        )

        reaction_map = text_config.ai_reactions.reactions_map
        reaction_key = ""

        if situation == "drawn":
            if deception_failed:
                reaction_key = (
                    "drawn_ghost_deception_failed"
                    if is_ghost
                    else "drawn_safe_deception_failed"
                )
            else:
                reaction_key = "drawn_ghost_real" if is_ghost else "drawn_safe_real"
        elif situation == "selected":
            if use_deception:
                reaction_key = (
                    "selected_ghost_fake" if is_ghost else "selected_safe_fake"
                )
                deception_type = "deceive_ghost" if is_ghost else "deceive_safe"
            else:
                reaction_key = (
                    "selected_ghost_real" if is_ghost else "selected_safe_real"
                )
        elif situation == "cancelled":
            if use_deception:
                reaction_key = (
                    "cancelled_ghost_fake" if is_ghost else "cancelled_safe_fake"
                )
            else:
                reaction_key = (
                    "cancelled_ghost_real" if is_ghost else "cancelled_safe_real"
                )

        reactions = reaction_map.get(reaction_key)
        if not reactions:
            return "...", "", None

        text = random.choice(reactions.texts)
        image_url = reactions.image_url

        return text, image_url, deception_type

    def _get_rank(self, card: str) -> str:
        """从表情符号中提取卡牌的点数"""
        if card == "🃏":
            return "Joker"
        # 正则表达式匹配 <:rank_of_suit:id> 格式
        match = re.search(r"<:(\w+)_of_\w+:\d+>", card)
        if match:
            return match.group(1).upper()
        return card

    def _match_and_discard(self, hand: List[str]) -> List[str]:
        """匹配并弃置手牌中的对子（不同花色相同点数）。"""
        if not hand:
            return []

        ranks_in_hand: Dict[str, List[str]] = {}
        for card in hand:
            if card != "🃏":
                rank = self._get_rank(card)
                if rank not in ranks_in_hand:
                    ranks_in_hand[rank] = []
                ranks_in_hand[rank].append(card)

        new_hand = []
        for rank, cards in ranks_in_hand.items():
            # 消除成对的牌
            while len(cards) >= 2:
                cards.pop()
                cards.pop()
            # 如果剩下牌，加回手牌
            if cards:
                new_hand.extend(cards)

        if "🃏" in hand:
            new_hand.append("🃏")

        # 保持手牌顺序随机
        random.shuffle(new_hand)
        return new_hand

    def ai_make_decision(
        self, strategy: AIStrategy, player_hand: List[str], ai_hand: List[str]
    ) -> int:
        """
        AI做出抽牌决策。
        新策略：在避开鬼牌的基础上，优先抽取能与自己手牌配对的牌。
        """
        target_hand = player_hand

        # 定义不同策略的触发概率
        strategy_chances = {
            AIStrategy.SUPER: 0.99,
            AIStrategy.HIGH: 0.65,
            AIStrategy.MEDIUM: 0.35,
            AIStrategy.LOW: 0.0,
        }

        # 检查是否触发策略
        use_strategy = random.random() < strategy_chances.get(strategy, 0.0)

        if use_strategy:
            # 1. 找出玩家手中所有非鬼牌的牌及其索引
            safe_indices = [i for i, card in enumerate(target_hand) if card != "🃏"]

            if safe_indices:
                # 2. 在安全牌中，寻找能与AI手牌配对的牌
                ai_hand_set = set(ai_hand)
                matching_indices = [
                    i for i in safe_indices if target_hand[i] in ai_hand_set
                ]

                if matching_indices:
                    # 3. 如果找到能配对的牌，优先从中选择
                    return random.choice(matching_indices)
                else:
                    # 4. 如果没有能配对的牌，则在所有安全牌中随机选择
                    return random.choice(safe_indices)

        # 如果不使用策略或没有安全牌可选，则完全随机选择
        if not target_hand:
            return 0
        return random.randint(0, len(target_hand) - 1)

    def start_new_game(
        self, user_id: int, guild_id: int, bet_amount: int, ai_strategy: AIStrategy
    ) -> str:
        """开始新游戏（经典抽鬼牌规则）"""
        game_id = f"{user_id}_{guild_id}"

        deck = self.generate_deck()
        random.shuffle(deck)

        # 随机发牌
        player_hand = deck[::2]
        ai_hand = deck[1::2]

        # log.info(f"Game {game_id}: Player hand before discard: {player_hand}")
        # log.info(f"Game {game_id}: AI hand before discard: {ai_hand}")

        # 初始配对消除
        player_hand = self._match_and_discard(player_hand)
        ai_hand = self._match_and_discard(ai_hand)

        # log.info(f"Game {game_id}: Player hand after discard: {player_hand} (count: {len(player_hand)})")
        # log.info(f"Game {game_id}: AI hand after discard: {ai_hand} (count: {len(ai_hand)})")

        # 决定谁先手
        first_turn = random.choice(["player", "ai"])
        # log.info(f"Game {game_id}: First turn: {first_turn}")

        # 存储游戏状态
        self.active_games[game_id] = {
            "player_hand": player_hand,
            "ai_hand": ai_hand,
            "ai_strategy": ai_strategy,  # 保留用于AI决策和可能的未来扩展
            "current_turn": first_turn,
            "game_over": False,
            "winner": None,
            "bet_amount": bet_amount,
            "payout_ratio": PAYOUT_RATIOS.get(ai_strategy, 1),
            "winnings": 0,
            "last_deception_type": None,
        }

        return game_id

    def get_game_state(self, game_id: str) -> Optional[Dict]:
        """获取游戏状态"""
        return self.active_games.get(game_id)

    def get_reaction_for_selection(
        self, game_id: str, card_index: int, situation: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        获取玩家选择/取消选择卡片时的反应，并记录欺骗状态
        返回 (reaction_text, reaction_image_url)
        """
        game = self.active_games.get(game_id)
        if not game or game["game_over"]:
            return None, None

        if card_index < 0 or card_index >= len(game["ai_hand"]):
            return None, None

        selected_card = game["ai_hand"][card_index]
        is_ghost = selected_card == "🃏"

        # 检查AI手上是否有鬼牌
        ai_has_ghost = "🃏" in game["ai_hand"]

        reaction_text, reaction_image_url, deception_type = self._get_bot_reaction(
            situation, is_ghost, game["ai_strategy"], ai_has_ghost
        )

        # 记录欺骗状态
        if situation == "selected":
            game["last_deception_type"] = deception_type
        elif situation == "cancelled" and game.get("last_deception_type"):
            # 如果玩家取消了并且AI正在欺骗，触发特殊反应
            reactions = text_config.ai_reactions.reactions_map.get(
                "cancelled_deception"
            )
            if reactions:
                reaction_text = random.choice(reactions.texts)
                reaction_image_url = reactions.image_url
            game["last_deception_type"] = None  # 重置欺骗状态
            return reaction_text, reaction_image_url

        return reaction_text, reaction_image_url

    def player_draw_card(
        self, game_id: str, card_index: int
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        玩家抽牌
        返回: (success, message, reaction_text, reaction_image_url)
        """
        game = self.active_games.get(game_id)
        if not game or game["game_over"]:
            return False, text_config.errors.game_ended, None, None

        if game["current_turn"] != "player":
            return False, text_config.errors.not_your_turn, None, None

        if card_index < 0 or card_index >= len(game["ai_hand"]):
            return False, text_config.errors.invalid_card_index, None, None

        drawn_card = game["ai_hand"].pop(card_index)
        game["player_hand"].append(drawn_card)

        is_ghost = drawn_card == "🃏"

        # 抽牌后的反应（保留欺骗逻辑）
        last_deception = game.get("last_deception_type")
        reaction_key = ""

        if last_deception == "deceive_ghost":  # AI假装这张是鬼牌
            if is_ghost:  # 玩家还是抽了，AI反向激将法成功
                reaction_key = "drawn_ghost_real"  # 高兴的反应
            else:  # 玩家识破了，抽到安全牌
                reaction_key = "drawn_safe_deception_failed"  # 计谋被识破的反应

        elif last_deception == "deceive_safe":  # AI假装这张是安全牌
            if is_ghost:  # 玩家上当了，抽到鬼牌，AI欺骗成功
                reaction_key = "drawn_ghost_real"  # 高兴的反应
            else:  # 玩家抽到安全牌，AI没能骗到
                reaction_key = "drawn_safe_real"  # 失望的反应

        else:  # 没有欺骗
            reaction_key = "drawn_ghost_real" if is_ghost else "drawn_safe_real"

        reactions = text_config.ai_reactions.reactions_map.get(reaction_key)
        if reactions:
            reaction_text = random.choice(reactions.texts)
            reaction_image_url = reactions.image_url
        else:
            reaction_text, reaction_image_url = "...", ""

        game["last_deception_type"] = None

        # 抽牌后弃牌
        game["player_hand"] = self._match_and_discard(game["player_hand"])

        # 检查游戏是否结束
        winner = self._check_game_winner(game)
        if winner:
            game["game_over"] = True
            game["winner"] = winner
            if winner == "player":
                game["winnings"] = game["bet_amount"] * game["payout_ratio"]
                message = f"你抽到了 {drawn_card}！你的手牌已全部出完，恭喜获胜！"
            else:  # winner == "ai"
                game["winnings"] = 0
                message = f"你抽到了 {drawn_card}！类脑娘的手牌已全部出完，你输了！"
            return True, message, reaction_text, reaction_image_url

        game["current_turn"] = "ai"
        message = f"你抽到了 {drawn_card}"
        return True, message, reaction_text, reaction_image_url

    def ai_draw_card(
        self, game_id: str
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        AI抽牌
        返回: (success, message, reaction_text, reaction_image_url)
        """
        game = self.active_games.get(game_id)
        if not game or game["game_over"]:
            return False, text_config.errors.game_ended, None, None

        if game["current_turn"] != "ai":
            return False, "现在不是AI的回合", None, None

        card_index = self.ai_make_decision(
            game["ai_strategy"], game["player_hand"], game["ai_hand"]
        )

        drawn_card = game["player_hand"].pop(card_index)
        game["ai_hand"].append(drawn_card)
        game["ai_hand"] = self._match_and_discard(game["ai_hand"])

        is_ghost = drawn_card == "🃏"

        # 检查游戏是否结束
        winner = self._check_game_winner(game)
        if winner:
            game["game_over"] = True
            game["winner"] = winner
            reaction_text, reaction_image_url = "", ""
            if winner == "ai":
                game["winnings"] = 0
                message = f"类脑娘抽到了 {drawn_card}！她的手牌已全部出完，你输了！"
                reactions = text_config.ai_reactions.reactions_map.get(
                    "player_lost_win"
                )
                if reactions:
                    reaction_text = random.choice(reactions.texts)
                    reaction_image_url = reactions.image_url
            else:  # winner == "player"
                game["winnings"] = game["bet_amount"] * game["payout_ratio"]
                message = f"类脑娘抽到了 {drawn_card}！你的手牌已全部出完，恭喜获胜！"
                # 玩家胜利时的反应 (AI抽到鬼牌)
                reactions = text_config.ai_reactions.reactions_map.get("ai_drawn_ghost")
                if reactions:
                    reaction_text = random.choice(reactions.texts)
                    reaction_image_url = reactions.image_url
            return True, message, reaction_text, reaction_image_url

        # 普通抽牌反应
        reaction_key = "ai_drawn_ghost" if is_ghost else "ai_drawn_safe"
        reactions = text_config.ai_reactions.reactions_map.get(reaction_key)
        reaction_text, reaction_image_url = "", ""
        if reactions:
            reaction_text = random.choice(reactions.texts)
            reaction_image_url = reactions.image_url

        game["current_turn"] = "player"
        message = f"类脑娘抽到了 {drawn_card}"
        return True, message, reaction_text, reaction_image_url

    def _check_game_winner(self, game: Dict) -> Optional[str]:
        """检查游戏胜利者。如果游戏未结束，返回None。"""
        player_hand_empty = not game["player_hand"]
        ai_hand_empty = not game["ai_hand"]

        if player_hand_empty:
            return "player"
        if ai_hand_empty:
            return "ai"

        # 当总牌数只剩一张时（必然是鬼牌），持有鬼牌的人输
        if len(game["player_hand"]) + len(game["ai_hand"]) == 1:
            if "🃏" in game["player_hand"]:
                return "ai"  # 玩家持有鬼牌，AI赢
            else:
                return "player"  # AI持有鬼牌，玩家赢

        return None

    def end_game(self, game_id: str):
        """结束游戏"""
        if game_id in self.active_games:
            del self.active_games[game_id]


# 全局实例
ghost_card_service = GhostCardService()
