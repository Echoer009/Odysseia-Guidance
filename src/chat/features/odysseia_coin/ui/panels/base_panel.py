from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar
import discord

if TYPE_CHECKING:
    from src.chat.features.odysseia_coin.ui.shop_ui import (
        SimpleShopView,
        TutorialManagementView,
    )

ViewT = TypeVar("ViewT", bound="SimpleShopView | TutorialManagementView")


class BasePanel(ABC, Generic[ViewT]):
    def __init__(self, view: ViewT):
        self.view = view
        self.shop_data = view.shop_data

    @abstractmethod
    async def create_embed(self) -> discord.Embed:
        raise NotImplementedError
