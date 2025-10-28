# -*- coding: utf-8 -*-

import unittest
from unittest.mock import patch, MagicMock

# 将项目根目录添加到Python路径中
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.features.games.services.blackjack_service import (
    BlackjackService,
    Card,
    GameStatus,
    HandStatus,
)


class TestBlackjackService(unittest.TestCase):
    def setUp(self):
        """在每个测试前初始化BlackjackService实例"""
        self.service = BlackjackService()
        self.user_id = 123
        self.guild_id = 456
        self.bet = 10
        self.game_id = f"blackjack_{self.user_id}_{self.guild_id}"

    def _setup_game_with_mocked_deck(self, card_sequence):
        """使用模拟的Deck来初始化和开始一个游戏"""
        mock_deck = MagicMock()
        mock_deck.deal.side_effect = card_sequence

        with patch(
            "src.chat.features.games.services.blackjack_service.Deck",
            return_value=mock_deck,
        ):
            game_id = self.service.start_game(self.user_id, self.guild_id, self.bet)
            return self.service.get_game_state(game_id)

    def test_start_game_player_blackjack(self):
        """测试开局玩家黑杰克"""
        # 玩家: A, K. 庄家: 5, Q
        initial_cards = [
            Card("Spades", "A"),
            Card("Hearts", "5"),
            Card("Spades", "K"),
            Card("Hearts", "Q"),
        ]
        game = self._setup_game_with_mocked_deck(initial_cards)

        self.assertEqual(game.status, GameStatus.GAME_OVER)
        self.assertEqual(game.player_hands[0].status, HandStatus.BLACKJACK)
        self.assertEqual(game.winnings[0], self.bet * 1.5)

    def test_start_game_push_blackjack(self):
        """测试开局双方黑杰克平局"""
        # 玩家: A, K. 庄家: A, Q
        initial_cards = [
            Card("Spades", "A"),
            Card("Hearts", "A"),
            Card("Spades", "K"),
            Card("Hearts", "Q"),
        ]
        game = self._setup_game_with_mocked_deck(initial_cards)

        self.assertEqual(game.status, GameStatus.GAME_OVER)
        self.assertEqual(game.winnings.get(0), 0)

    def test_player_hit_and_bust(self):
        """测试玩家要牌后爆牌"""
        # 玩家: 10, 7. 庄家: 5, 6. 玩家要牌: 8
        initial_cards = [
            Card("Spades", "10"),
            Card("Hearts", "5"),
            Card("Spades", "7"),
            Card("Hearts", "6"),
            Card("Clubs", "8"),
            Card("Diamonds", "2"),  # Extra card
        ]
        game = self._setup_game_with_mocked_deck(initial_cards)

        self.service.player_hit(self.game_id)

        self.assertEqual(game.player_hands[0].status, HandStatus.BUSTED)
        self.assertEqual(
            game.status, GameStatus.GAME_OVER
        )  # 玩家单手牌爆牌后，游戏直接结束
        self.assertEqual(game.winnings[0], -self.bet)

    def test_dealer_soft_17_rule(self):
        """测试庄家在软17点时必须叫牌"""
        # 玩家: 10, 8 (18). 庄家: A, 6 (软17). 庄家要牌: 5 (爆牌)
        initial_cards = [
            Card("Spades", "10"),
            Card("Clubs", "A"),
            Card("Spades", "8"),
            Card("Diamonds", "6"),
            Card("Clubs", "5"),
            Card("Hearts", "K"),  # Extra card
        ]
        game = self._setup_game_with_mocked_deck(initial_cards)

        self.service.player_stand(self.game_id)

        self.assertTrue(len(game.dealer_hand.cards) > 2)
        self.assertEqual(game.dealer_hand.status, HandStatus.BUSTED)
        self.assertEqual(game.winnings[0], self.bet)

    def test_player_split(self):
        """测试玩家分牌"""
        # 玩家: 8, 8. 庄家: 5, 6. 分牌后玩家1拿到A, 玩家2拿到K
        initial_cards = [
            Card("Spades", "8"),
            Card("Hearts", "5"),
            Card("Hearts", "8"),
            Card("Hearts", "6"),
            Card("Clubs", "A"),
            Card("Diamonds", "K"),
            Card("Diamonds", "2"),  # Extra card
        ]
        game = self._setup_game_with_mocked_deck(initial_cards)

        self.service.player_split(self.game_id)

        self.assertEqual(len(game.player_hands), 2)
        self.assertEqual(game.player_hands[0].cards[0].rank, "8")
        self.assertEqual(game.player_hands[1].cards[0].rank, "8")
        self.assertEqual(game.player_hands[0].value, 19)  # 8 + A
        self.assertEqual(game.player_hands[1].value, 18)  # 8 + K
        self.assertEqual(game.current_hand_index, 0)

    def test_player_double_down_and_win(self):
        """测试玩家双倍下注并获胜"""
        # 玩家: 6, 5 (11). 庄家: 2, 4 (6). 玩家拿到K (21). 庄家拿到10 (16)
        initial_cards = [
            Card("Spades", "6"),
            Card("Clubs", "2"),
            Card("Hearts", "5"),
            Card("Diamonds", "4"),
            Card("Clubs", "K"),
            Card("Hearts", "10"),
            Card("Diamonds", "2"),  # Extra card
        ]
        game = self._setup_game_with_mocked_deck(initial_cards)

        self.service.player_double_down(self.game_id)

        self.assertEqual(game.player_hands[0].bet, self.bet * 2)
        self.assertEqual(game.player_hands[0].value, 21)
        self.assertEqual(game.player_hands[0].status, HandStatus.DOUBLED_DOWN)
        self.assertEqual(game.status, GameStatus.GAME_OVER)
        self.assertEqual(game.winnings[0], self.bet * 2)


if __name__ == "__main__":
    unittest.main()
