# -*- coding: utf-8 -*-

import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict

# 将项目根目录添加到Python路径中，以便导入src模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.features.games.services.blackjack_service import (
    blackjack_service,
    Card,
    Game,
    GameStatus,
    HandStatus,
)


# --- Pydantic 模型定义 ---
class CardModel(BaseModel):
    suit: str
    rank: str
    value: int


class CardPlaceholderModel(BaseModel):
    suit: str = "hidden"
    rank: str = "?"
    value: int = 0


class HandModel(BaseModel):
    cards: List[CardModel | CardPlaceholderModel]
    bet: int
    status: str
    value: int
    can_split: bool
    can_double_down: bool


class GameStateModel(BaseModel):
    game_id: str
    player_hands: List[HandModel]
    dealer_hand: HandModel
    status: str
    current_hand_index: int
    winnings: Dict[int, int]
    can_offer_insurance: bool


class StartGameRequest(BaseModel):
    bet_amount: int = 10


class InsuranceRequest(BaseModel):
    place_bet: bool


# --- FastAPI 应用实例 ---
app = FastAPI()


# --- 辅助函数 ---
def game_to_model(game: Game) -> GameStateModel:
    """将Game对象转换为Pydantic模型，并处理信息隐藏"""
    is_game_over = game.status == GameStatus.GAME_OVER

    # 转换庄家手牌
    dealer_cards_model = []
    if is_game_over:
        dealer_cards_model = [
            CardModel.model_validate(c, from_attributes=True)
            for c in game.dealer_hand.cards
        ]
    else:
        # 隐藏第二张牌
        if len(game.dealer_hand.cards) > 0:
            dealer_cards_model.append(
                CardModel.model_validate(
                    game.dealer_hand.cards[0], from_attributes=True
                )
            )
        if len(game.dealer_hand.cards) > 1:
            dealer_cards_model.append(CardPlaceholderModel())

    dealer_hand_model = HandModel(
        cards=dealer_cards_model,
        bet=0,
        status=game.dealer_hand.status.value,
        value=game.dealer_hand.value
        if is_game_over
        else CardModel.model_validate(
            game.dealer_hand.cards[0], from_attributes=True
        ).value,
        can_split=False,
        can_double_down=False,
    )

    # 转换玩家手牌
    player_hands_model = [
        HandModel(
            cards=[
                CardModel.model_validate(c, from_attributes=True) for c in hand.cards
            ],
            bet=hand.bet,
            status=hand.status.value,
            value=hand.value,
            can_split=hand.can_split,
            can_double_down=hand.can_double_down,
        )
        for hand in game.player_hands
    ]

    return GameStateModel(
        game_id=game.game_id,
        player_hands=player_hands_model,
        dealer_hand=dealer_hand_model,
        status=game.status.value,
        current_hand_index=game.current_hand_index,
        winnings=game.winnings,
        can_offer_insurance=blackjack_service.can_offer_insurance(game),
    )


# --- API 路由 ---
@app.post("/api/game", response_model=GameStateModel)
async def start_game(request: StartGameRequest):
    """API: 开始一局新游戏"""
    user_id = 1
    guild_id = 1
    game_id = blackjack_service.start_game(user_id, guild_id, request.bet_amount)
    game = blackjack_service.get_game_state(game_id)
    if not game:
        raise HTTPException(status_code=500, detail="Failed to create game")
    return game_to_model(game)


def get_game_or_404(game_id: str) -> Game:
    """获取游戏实例，如果找不到则抛出404异常"""
    game = blackjack_service.get_game_state(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@app.post("/api/game/{game_id}/hit", response_model=GameStateModel)
async def player_hit(game_id: str):
    """API: 玩家要牌"""
    updated_game = blackjack_service.player_hit(game_id)
    if not updated_game:
        raise HTTPException(status_code=400, detail="Invalid action: HIT")
    return game_to_model(updated_game)


@app.post("/api/game/{game_id}/stand", response_model=GameStateModel)
async def player_stand(game_id: str):
    """API: 玩家停牌"""
    updated_game = blackjack_service.player_stand(game_id)
    if not updated_game:
        raise HTTPException(status_code=400, detail="Invalid action: STAND")
    return game_to_model(updated_game)


@app.post("/api/game/{game_id}/double", response_model=GameStateModel)
async def player_double(game_id: str):
    """API: 玩家双倍下注"""
    updated_game = blackjack_service.player_double_down(game_id)
    if not updated_game:
        raise HTTPException(status_code=400, detail="Invalid action: DOUBLE DOWN")
    return game_to_model(updated_game)


@app.post("/api/game/{game_id}/split", response_model=GameStateModel)
async def player_split(game_id: str):
    """API: 玩家分牌"""
    updated_game = blackjack_service.player_split(game_id)
    if not updated_game:
        raise HTTPException(status_code=400, detail="Invalid action: SPLIT")
    return game_to_model(updated_game)


@app.post("/api/game/{game_id}/insurance", response_model=GameStateModel)
async def player_insurance(game_id: str, request: InsuranceRequest):
    """API: 玩家购买保险"""
    updated_game = blackjack_service.player_insurance(game_id, request.place_bet)
    if not updated_game:
        raise HTTPException(status_code=400, detail="Invalid action: INSURANCE")
    return game_to_model(updated_game)


# --- 静态文件和主页 ---
app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """提供游戏主页面"""
    try:
        with open("web/templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")


# --- 运行命令 ---
# 要运行此应用，请在终端中使用命令: uvicorn web.app:app --reload --port 5001
