import logging
import json
import random
from typing import Optional, List, Dict, Any

from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)

# --- Constants ---
SUITS = ["Club", "Diamond", "Heart", "Spade"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


class BlackjackGame:
    """Represents the full state of a single blackjack game."""

    def __init__(
        self,
        user_id: int,
        bet_amount: int,
        game_state: str,
        deck: List[str],
        player_hand: List[str],
        dealer_hand: List[str],
    ):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.game_state = game_state
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the game state to a dictionary for API responses."""
        is_player_turn = self.game_state == "player_turn"

        # Correctly prepare dealer's hand for the UI
        if is_player_turn:
            # Show only the first card and a hidden card
            ui_dealer_hand = [self.dealer_hand[0], "Hidden"]
            # Calculate score based only on the visible card
            ui_dealer_score = BlackjackService._calculate_hand_score(
                [self.dealer_hand[0]]
            )
        else:
            # Show all cards once the player's turn is over
            ui_dealer_hand = self.dealer_hand
            ui_dealer_score = BlackjackService._calculate_hand_score(self.dealer_hand)

        return {
            "user_id": self.user_id,
            "bet_amount": self.bet_amount,
            "game_state": self.game_state,
            "player_hand": self.player_hand,
            "dealer_hand": ui_dealer_hand,
            "player_score": BlackjackService._calculate_hand_score(self.player_hand),
            "dealer_score": ui_dealer_score,
        }


class BlackjackService:
    def __init__(self, db_manager):
        self._db_manager = db_manager

    async def initialize(self):
        """
        初始化数据库表（仅在应用启动时执行一次）
        这个函数只在FastAPI应用启动时调用，不是每次游戏都调用
        """
        await self._db_manager._execute(self._db_manager._init_database_logic)
        log.info(
            "Blackjack games table initialized (only once at application startup)."
        )
        await self.cleanup_stale_games()

    # --- Core Game Logic ---
    @staticmethod
    def _create_deck() -> List[str]:
        """Creates a standard 52-card deck."""
        return [f"{suit}{rank}" for suit in SUITS for rank in RANKS]

    @staticmethod
    def _shuffle_deck(deck: List[str]) -> None:
        """Shuffles the deck in place."""
        random.shuffle(deck)

    @staticmethod
    def _deal_card(deck: List[str]) -> str:
        """Deals one card from the deck."""
        return deck.pop()

    @staticmethod
    def _get_card_value(card: str) -> int:
        """Gets the numerical value of a card."""
        # Check for "10" first, as it's two characters
        if card.endswith("10"):
            return 10

        # Then check for single-character ranks
        rank_char = card[-1]
        if rank_char in ["J", "Q", "K"]:
            return 10
        if rank_char == "A":
            return 11

        # Otherwise, it's a number card
        return int(rank_char)

    @staticmethod
    def _calculate_hand_score(hand: List[str]) -> int:
        """Calculates the score of a hand."""
        score = 0
        ace_count = 0
        for card in hand:
            if card == "Hidden":
                continue
            score += BlackjackService._get_card_value(card)
            if "A" in card:
                ace_count += 1

        while score > 21 and ace_count > 0:
            score -= 10
            ace_count -= 1
        return score

    @staticmethod
    def _is_soft_hand(hand: List[str]) -> bool:
        """Checks if a hand is 'soft' (contains an Ace counted as 11)."""
        score = BlackjackService._calculate_hand_score(hand)

        non_ace_score = 0
        ace_count = 0
        for card in hand:
            if "A" in card:
                ace_count += 1
            else:
                if card == "Hidden":
                    continue
                non_ace_score += BlackjackService._get_card_value(card)

        hard_score = non_ace_score + ace_count

        # If the calculated score is greater than the hard score, it means
        # at least one Ace was counted as 11, making the hand soft.
        return ace_count > 0 and score > hard_score

    # --- Database Interaction ---
    async def _save_game_state(self, game: BlackjackGame):
        """Saves the entire game state to the database."""
        query = """
            REPLACE INTO blackjack_games (user_id, bet_amount, game_state, deck, player_hand, dealer_hand)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            game.user_id,
            game.bet_amount,
            game.game_state,
            json.dumps(game.deck),
            json.dumps(game.player_hand),
            json.dumps(game.dealer_hand),
        )
        await self._db_manager._execute(
            self._db_manager._db_transaction, query, params, commit=True
        )

    async def get_active_game(self, user_id: int) -> Optional[BlackjackGame]:
        """Retrieves the current active game for a user from the database."""
        query = "SELECT * FROM blackjack_games WHERE user_id = ?"
        row = await self._db_manager._execute(
            self._db_manager._db_transaction, query, (user_id,), fetch="one"
        )
        if row:
            return BlackjackGame(
                user_id=row["user_id"],
                bet_amount=row["bet_amount"],
                game_state=row["game_state"],
                deck=json.loads(row["deck"]),
                player_hand=json.loads(row["player_hand"]),
                dealer_hand=json.loads(row["dealer_hand"]),
            )
        return None

    async def delete_game(self, user_id: int):
        """Deletes a game record for a user."""
        query = "DELETE FROM blackjack_games WHERE user_id = ?"
        await self._db_manager._execute(
            self._db_manager._db_transaction, query, (user_id,), commit=True
        )
        log.info(f"Deleted game for user {user_id}.")

    # --- Public Service Methods ---
    async def start_game(self, user_id: int, bet_amount: int) -> BlackjackGame:
        """Starts a new game of blackjack, checking for immediate win/loss conditions."""
        deck = self._create_deck()
        self._shuffle_deck(deck)

        player_hand = [self._deal_card(deck), self._deal_card(deck)]
        dealer_hand = [self._deal_card(deck), self._deal_card(deck)]

        player_score = self._calculate_hand_score(player_hand)
        dealer_score = self._calculate_hand_score(dealer_hand)

        game_state = "player_turn"  # Default state

        # Check for immediate Blackjack scenarios
        if player_score == 21:
            if dealer_score == 21:
                game_state = "finished_push"  # Both have Blackjack
            else:
                game_state = "finished_blackjack"  # Player has Blackjack
        elif dealer_score == 21:
            game_state = "finished_loss"  # Dealer has Blackjack, player does not

        game = BlackjackGame(
            user_id=user_id,
            bet_amount=bet_amount,
            game_state=game_state,  # Use the newly determined state
            deck=deck,
            player_hand=player_hand,
            dealer_hand=dealer_hand,
        )

        await self._save_game_state(game)
        log.info(
            f"Started new game for user {user_id} with bet {bet_amount}. Initial state: {game_state}"
        )
        return game

    async def player_hit(self, user_id: int) -> BlackjackGame:
        """Handles the player's 'hit' action."""
        game = await self.get_active_game(user_id)
        if not game or game.game_state != "player_turn":
            raise ValueError("It's not your turn to hit.")

        game.player_hand.append(self._deal_card(game.deck))

        player_score = self._calculate_hand_score(game.player_hand)
        if player_score > 21:
            game.game_state = "finished_loss"

        await self._save_game_state(game)
        return game

    async def player_stand(
        self, user_id: int, is_double_down: bool = False
    ) -> BlackjackGame:
        """Handles the player's 'stand' action and completes the dealer's turn."""
        game = await self.get_active_game(user_id)
        if not game:
            raise ValueError("No active game found.")

        if not is_double_down and game.game_state != "player_turn":
            raise ValueError("It's not your turn to stand.")

        game.game_state = "dealer_turn"

        dealer_score = self._calculate_hand_score(game.dealer_hand)
        while dealer_score < 17 or (
            dealer_score == 17 and BlackjackService._is_soft_hand(game.dealer_hand)
        ):
            game.dealer_hand.append(self._deal_card(game.deck))
            dealer_score = self._calculate_hand_score(game.dealer_hand)

        player_score = self._calculate_hand_score(game.player_hand)

        # --- 调试日志 ---
        log.info(
            f"结算判断: UserID={game.user_id}, PlayerHand={game.player_hand} ({player_score}), "
            f"DealerHand={game.dealer_hand} ({dealer_score})"
        )

        if dealer_score > 21 or player_score > dealer_score:
            game.game_state = "finished_win"
        elif dealer_score > player_score:
            game.game_state = "finished_loss"
        else:
            game.game_state = "finished_push"

        log.info(f"最终结果: UserID={game.user_id}, Result={game.game_state}")
        # --- 日志结束 ---

        await self._save_game_state(game)
        return game

    async def double_down(self, user_id: int, double_amount: int) -> BlackjackGame:
        """Handles the player's 'double down' action."""
        game = await self.get_active_game(user_id)
        if not game or game.game_state != "player_turn":
            raise ValueError("It's not your turn to double down.")

        if len(game.player_hand) != 2:
            raise ValueError("You can only double down on your initial two cards.")

        # Double the bet
        game.bet_amount += double_amount

        # Player hits once
        game.player_hand.append(self._deal_card(game.deck))
        player_score = self._calculate_hand_score(game.player_hand)

        if player_score > 21:
            game.game_state = "finished_loss"
            # Save the final state when player busts
            await self._save_game_state(game)
        else:
            # Save state with the player's new card before the dealer plays.
            await self._save_game_state(game)
            # Automatically stand after doubling down
            game = await self.player_stand(user_id, is_double_down=True)

        return game

    async def cleanup_stale_games(self):
        """Cleans up all unfinished games on startup and refunds the bets."""
        coin_service = __import__(
            "src.chat.features.odysseia_coin.service.coin_service",
            fromlist=["coin_service"],
        ).coin_service

        log.info("Cleaning up all unfinished blackjack games...")
        rows = await self._db_manager._execute(
            self._db_manager._db_transaction,
            "SELECT user_id, bet_amount FROM blackjack_games",
            (),
            fetch="all",
        )
        if not rows:
            log.info("No stale blackjack games found to clean up.")
            return

        cleaned_count = 0
        for user_id, bet_amount in rows:
            try:
                log.warning(
                    f"Cleaning up stale game for user {user_id} with bet {bet_amount}."
                )
                await coin_service.add_coins(
                    user_id, bet_amount, "Blackjack game refund due to service restart"
                )
                await self.delete_game(user_id)
                log.info(
                    f"Successfully refunded {bet_amount} to user {user_id} and deleted stale game."
                )
                cleaned_count += 1
            except Exception as e:
                log.error(
                    f"Failed to clean up stale game for user {user_id}. Error: {e}",
                    exc_info=True,
                )

        if cleaned_count > 0:
            log.info(f"Finished cleaning up {cleaned_count} stale blackjack games.")


# --- Singleton Instance ---
blackjack_service = BlackjackService(chat_db_manager)
