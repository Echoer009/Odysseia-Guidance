import asyncio
import io
import json
import os
import random
from typing import List, Dict, Any, Tuple, Optional

from PIL import Image

from src.chat.config.chat_config import TAROT_CONFIG


class TarotService:
    _instance = None
    _cards = []

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TarotService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not self._cards:
            self._load_cards()

    def _load_cards(self):
        """Loads tarot card data from the JSON file."""
        try:
            with open(
                "src/chat/features/tarot/data/tarot_cards.json", "r", encoding="utf-8"
            ) as f:
                self._cards = json.load(f)
        except FileNotFoundError:
            print("Error: tarot_cards.json not found. Make sure the path is correct.")
            self._cards = []
        except json.JSONDecodeError:
            print("Error: Could not decode tarot_cards.json. Check for syntax errors.")
            self._cards = []

    def draw_cards(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        Draws a specified number of unique cards from the deck.
        Each card is randomly assigned an orientation (upright or reversed).
        """
        if not self._cards:
            return []

        drawn_cards = random.sample(self._cards, count)

        for card in drawn_cards:
            card["orientation"] = random.choice(["upright", "reversed"])

        return drawn_cards

    def _generate_spread_image_sync(
        self, cards: List[Dict[str, Any]]
    ) -> Optional[bytes]:
        """
        (Sync) Generates a tarot spread image from card files using Pillow.
        This function is designed to be run in a separate thread.
        """
        try:
            # --- Image Dimensions ---
            card_width, card_height = 275, 475
            padding = 25
            num_cards = len(cards)
            spread_width = (card_width * num_cards) + (padding * (num_cards + 1))
            spread_height = card_height + (padding * 2)

            # --- Create Background ---
            background = Image.new(
                "RGB", (spread_width, spread_height), color="#1E1E1E"
            )

            # --- Paste Cards ---
            for i, card in enumerate(cards):
                # Construct file path
                file_name = card["image_file"]
                card_path = os.path.join(TAROT_CONFIG["CARDS_PATH"], file_name)

                if not os.path.exists(card_path):
                    print(f"Warning: Card image not found at {card_path}")
                    continue

                # Open, resize, and rotate card image
                card_img = Image.open(card_path).convert("RGBA")
                card_img = card_img.resize(
                    (card_width, card_height), Image.Resampling.LANCZOS
                )
                if card["orientation"] == "reversed":
                    card_img = card_img.rotate(180)

                # Calculate position and paste
                x_pos = (i * card_width) + ((i + 1) * padding)
                y_pos = padding
                background.paste(card_img, (x_pos, y_pos), card_img)

            # --- Save to Bytes ---
            img_byte_arr = io.BytesIO()
            background.save(img_byte_arr, format="PNG")
            return img_byte_arr.getvalue()

        except Exception as e:
            print(f"Error generating tarot spread image: {e}")
            return None

    async def _generate_spread_image(
        self, cards: List[Dict[str, Any]]
    ) -> Optional[bytes]:
        """
        (Async) Runs the synchronous image generation in a separate thread.
        """
        return await asyncio.to_thread(self._generate_spread_image_sync, cards)

    async def perform_reading(
        self, question: str, spread_type: str = "three_card"
    ) -> Tuple[Optional[bytes], Optional[List[Dict[str, Any]]]]:
        """
        Performs a tarot reading, generates an image, and returns both.
        """
        # 1. Draw cards
        card_count = 3 if spread_type == "three_card" else 1
        cards = self.draw_cards(card_count)
        if not cards:
            return None, None

        # 2. Generate the spread image
        image_data = await self._generate_spread_image(cards)

        return image_data, cards
