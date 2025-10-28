# -*- coding: utf-8 -*-

import logging
from typing import Dict, List, Optional
from enum import Enum
import uuid

from .card import Deck, Card

log = logging.getLogger(__name__)


class HandStatus(Enum):
    """一手牌的状态"""

    IN_PROGRESS = "进行中"
    STAND = "已停牌"
    BUSTED = "已爆牌"
    BLACKJACK = "黑杰克"
    DOUBLED_DOWN = "已双倍下注"


class GameStatus(Enum):
    """整体游戏状态枚举"""

    AWAITING_PLAYER_ACTION = "AWAITING_PLAYER_ACTION"
    DEALER_TURN = "DEALER_TURN"
    GAME_OVER = "GAME_OVER"


class Hand:
    """代表一手牌（玩家或庄家）"""

    def __init__(self, bet: int = 0):
        self.cards: List[Card] = []
        self.bet: int = bet
        self.status: HandStatus = HandStatus.IN_PROGRESS

    @property
    def value(self) -> int:
        """计算手牌点数"""
        val, _ = self._calculate_value()
        return val

    @property
    def is_soft(self) -> bool:
        """判断是否是软牌（A计为11）"""
        _, is_soft = self._calculate_value()
        return is_soft

    def _calculate_value(self) -> tuple[int, bool]:
        """计算手牌点数，并返回是否为软牌"""
        value = 0
        aces = 0
        for card in self.cards:
            value += card.value
            if card.rank == "A":
                aces += 1

        is_soft_hand = False
        # 只有当A作为11点使用且总点数不超过21时，才是软牌
        temp_value = value
        temp_aces = aces
        while temp_value > 21 and temp_aces > 0:
            temp_value -= 10
            temp_aces -= 1

        if temp_aces > 0 and temp_value <= 21:
            is_soft_hand = True

        # 返回最终的有效点数
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1

        return value, is_soft_hand

    def add_card(self, card: Card):
        """向手牌中添加一张牌，并更新状态"""
        self.cards.append(card)
        if self.value > 21:
            self.status = HandStatus.BUSTED
        # 检查是否在添加牌后变成了21点（非初始黑杰克）
        elif self.value == 21:
            # 如果是双倍下注后达到21点，状态应保持DOUBLED_DOWN
            if self.status != HandStatus.DOUBLED_DOWN:
                self.status = HandStatus.STAND  # 达到21点自动停牌

    @property
    def is_blackjack(self) -> bool:
        """判断是否为黑杰克"""
        return len(self.cards) == 2 and self.value == 21

    @property
    def can_split(self) -> bool:
        """判断是否可以分牌"""
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    @property
    def can_double_down(self) -> bool:
        """判断是否可以双倍下注"""
        return self.status == HandStatus.IN_PROGRESS


class Game:
    """代表一局21点游戏"""

    def __init__(self, initial_bet: int):
        self.game_id: str = str(uuid.uuid4())
        self.deck: Deck = Deck()
        self.player_hands: List[Hand] = [Hand(bet=initial_bet)]
        self.dealer_hand: Hand = Hand()
        self.status: GameStatus = GameStatus.AWAITING_PLAYER_ACTION
        self.current_hand_index: int = 0
        self.insurance_bet: int = 0
        self.insurance_offered: bool = False  # 标记是否已提供过保险
        self.winnings: Dict[int, int] = {}  # hand_index -> amount won/lost

    def start(self):
        """发初始牌"""
        self.player_hands[0].add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())
        self.player_hands[0].add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())

        # 检查黑杰克
        player_bj = self.player_hands[0].is_blackjack
        dealer_bj = self.dealer_hand.is_blackjack

        # 检查黑杰克，只有在非分牌的初始手牌时才算
        if len(self.player_hands) == 1 and len(self.player_hands[0].cards) == 2:
            player_bj = self.player_hands[0].is_blackjack
            dealer_bj = self.dealer_hand.is_blackjack

            if player_bj:
                self.player_hands[0].status = HandStatus.BLACKJACK
                if dealer_bj:
                    # 平局
                    self.winnings[0] = 0
                else:
                    # 玩家黑杰克获胜
                    self.winnings[0] = int(self.player_hands[0].bet * 1.5)
                self.status = GameStatus.GAME_OVER
            elif dealer_bj:
                # 庄家黑杰克获胜
                self.winnings[0] = -self.player_hands[0].bet
                self.status = GameStatus.GAME_OVER

    def get_current_hand(self) -> Optional[Hand]:
        """获取当前正在操作的手牌"""
        if (
            self.status == GameStatus.AWAITING_PLAYER_ACTION
            and self.current_hand_index < len(self.player_hands)
        ):
            return self.player_hands[self.current_hand_index]
        return None

    def next_hand(self):
        """切换到下一手牌"""
        self.current_hand_index += 1
        if self.current_hand_index >= len(self.player_hands):
            self.status = GameStatus.DEALER_TURN


class BlackjackService:
    """21点游戏服务类"""

    def __init__(self):
        self.active_games: Dict[str, Game] = {}

    def start_game(self, user_id: int, guild_id: int, bet_amount: int) -> str:
        """开始一局新的21点游戏"""
        game = Game(initial_bet=bet_amount)

        # 使用 user_id 和 guild_id 生成可预测的 game_id 以便查找
        game_id = f"blackjack_{user_id}_{guild_id}"
        game.game_id = game_id  # 覆盖 uuid
        self.active_games[game_id] = game

        game.start()
        return game_id

    def get_game_state(self, game_id: str) -> Optional[Game]:
        """获取游戏状态"""
        return self.active_games.get(game_id)

    def player_hit(self, game_id: str) -> Optional[Game]:
        """玩家要牌"""
        game = self.get_game_state(game_id)
        if not game:
            return None

        hand = game.get_current_hand()
        if not hand or hand.status != HandStatus.IN_PROGRESS:
            return None

        hand.add_card(game.deck.deal())

        if hand.status == HandStatus.BUSTED:
            game.winnings[game.current_hand_index] = -hand.bet
            game.next_hand()
        elif hand.status == HandStatus.STAND:  # 达到21点自动停牌
            game.next_hand()

        if game.status == GameStatus.DEALER_TURN:
            self._dealer_turn(game)

        return game

    def player_stand(self, game_id: str) -> Optional[Game]:
        """玩家停牌"""
        game = self.get_game_state(game_id)
        if not game:
            return None

        hand = game.get_current_hand()
        if not hand or hand.status != HandStatus.IN_PROGRESS:
            return None

        hand.status = HandStatus.STAND
        game.next_hand()

        if game.status == GameStatus.DEALER_TURN:
            self._dealer_turn(game)

        return game

    def player_double_down(self, game_id: str) -> Optional[Game]:
        """玩家双倍下注"""
        game = self.get_game_state(game_id)
        if not game:
            return None

        hand = game.get_current_hand()
        if not hand or not hand.can_double_down:
            return None

        hand.bet *= 2
        hand.add_card(game.deck.deal())
        hand.status = (
            HandStatus.DOUBLED_DOWN
            if hand.status != HandStatus.BUSTED
            else HandStatus.BUSTED
        )
        game.next_hand()

        if game.status == GameStatus.DEALER_TURN:
            self._dealer_turn(game)

        return game

    def player_split(self, game_id: str) -> Optional[Game]:
        """玩家分牌"""
        game = self.get_game_state(game_id)
        if not game:
            return None

        hand_to_split = game.get_current_hand()
        if not hand_to_split or not hand_to_split.can_split:
            return None

        new_hand = Hand(bet=hand_to_split.bet)
        new_hand.add_card(hand_to_split.cards.pop())

        game.player_hands.insert(game.current_hand_index + 1, new_hand)

        hand_to_split.add_card(game.deck.deal())
        new_hand.add_card(game.deck.deal())

        return game

    def player_insurance(self, game_id: str, place_bet: bool) -> Optional[Game]:
        """玩家购买保险"""
        game = self.get_game_state(game_id)
        if not game or not self.can_offer_insurance(game):
            return None

        if place_bet:
            game.insurance_bet = game.player_hands[0].bet / 2

        game.insurance_offered = True  # 标记保险已处理
        return game

    def can_offer_insurance(self, game: Game) -> bool:
        """判断是否可以提供保险"""
        return (
            game.dealer_hand.cards[0].rank == "A"
            and len(game.player_hands) == 1
            and not game.insurance_offered
        )

    def _dealer_turn(self, game: Game):
        """庄家行动逻辑"""
        game.status = GameStatus.DEALER_TURN
        dealer_hand = game.dealer_hand

        # 检查是否有任何玩家手牌需要与庄家比较
        player_hands_in_play = any(
            hand.status not in [HandStatus.BUSTED, HandStatus.BLACKJACK]
            for hand in game.player_hands
        )

        if player_hands_in_play:
            if game.insurance_bet > 0:
                if dealer_hand.is_blackjack:
                    game.winnings[0] = game.winnings.get(0, 0) + game.insurance_bet * 2
                else:
                    game.winnings[0] = game.winnings.get(0, 0) - game.insurance_bet

            while dealer_hand.value < 17 or (
                dealer_hand.value == 17 and dealer_hand.is_soft
            ):
                dealer_hand.add_card(game.deck.deal())

        self._resolve_game(game)

    def _resolve_game(self, game: Game):
        """结算所有手牌的输赢"""
        dealer_score = game.dealer_hand.value
        dealer_busted = game.dealer_hand.status == HandStatus.BUSTED

        for i, hand in enumerate(game.player_hands):
            if i in game.winnings:
                continue

            if hand.status == HandStatus.BUSTED:
                game.winnings[i] = -hand.bet
            elif dealer_busted:
                game.winnings[i] = hand.bet
            elif hand.value > dealer_score:
                game.winnings[i] = hand.bet
            elif hand.value < dealer_score:
                game.winnings[i] = -hand.bet
            else:
                game.winnings[i] = 0

        game.status = GameStatus.GAME_OVER

    def end_game(self, game_id: str):
        """结束游戏并清理"""
        if game_id in self.active_games:
            del self.active_games[game_id]


# 全局实例
blackjack_service = BlackjackService()
