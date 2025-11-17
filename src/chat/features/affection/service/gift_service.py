import logging
from src.chat.services.gemini_service import GeminiService
from src.chat.features.affection.service.affection_service import AffectionService
from src.chat.utils.prompt_utils import extract_persona_prompt
from src.chat.config.prompts import SYSTEM_PROMPT
from src.chat.config import chat_config as app_config  # 导入 chat_config

log = logging.getLogger(__name__)


class GiftService:
    def __init__(
        self, gemini_service: GeminiService, affection_service: AffectionService
    ):
        self.gemini_service = gemini_service
        self.affection_service = affection_service

    async def generate_gift_response(self, user, item_name: str) -> str:
        """
        Generates a gift response from the AI based on the user's gift.
        """
        user_id = user.id
        affection_status = await self.affection_service.get_affection_status(user_id)
        affection_level_name = affection_status.get("level_name", "NEUTRAL")

        persona_prompt = extract_persona_prompt(SYSTEM_PROMPT)
        # 从 app_config 获取提示词模板
        system_prompt = app_config.GIFT_SYSTEM_PROMPT.format(persona=persona_prompt)

        user_prompt = app_config.GIFT_PROMPT.format(
            user_name=user.display_name,
            item_name=item_name,
            affection_level=affection_level_name,
        )

        # 将 system_prompt 和 user_prompt 合并
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        # 从 app_config 获取专用于礼物的生成配置
        gift_gen_config = app_config.GEMINI_GIFT_GEN_CONFIG

        log.info(f"为礼物 {item_name} 生成AI回应的完整提示: {combined_prompt}")

        # 使用新的 generate_simple_response 方法，并传入完整的生成配置
        response_text = await self.gemini_service.generate_simple_response(
            prompt=combined_prompt, generation_config=gift_gen_config
        )

        log.info(f"为礼物 {item_name} 生成AI回应的返回结果: {response_text}")

        return response_text
