import logging
from src.chat.services.ai.service import ai_service
from src.chat.features.affection.service.affection_service import AffectionService
from src.chat.services.config_override_service import config_override_service
from src.chat.services.prompt_service import prompt_service
from src.chat.utils.prompt_utils import extract_persona_prompt
from src.chat.config import chat_config as app_config  # 导入 chat_config
from src.chat.services.ai.providers.base import GenerationConfig

log = logging.getLogger(__name__)


class GiftService:
    def __init__(self, ai_svc, affection_service: AffectionService):
        self.ai_service = ai_svc
        self.affection_service = affection_service

    async def generate_gift_response(self, user, item_name: str) -> str:
        """
        Generates a gift response from the AI based on the user's gift.
        """
        user_id = user.id
        affection_status = await self.affection_service.get_affection_status(user_id)
        affection_level_name = affection_status.get("level_name", "NEUTRAL")

        persona_source = await prompt_service.get_prompt_async("SYSTEM_PROMPT")
        persona_prompt = extract_persona_prompt(persona_source or "")
        # 从 app_config 获取提示词模板
        gift_system_prompt = await config_override_service.get(
            "feature.gift_system_prompt",
            app_config.GIFT_SYSTEM_PROMPT,
        )
        system_prompt = gift_system_prompt.format(persona=persona_prompt)

        gift_prompt = await config_override_service.get(
            "feature.gift_prompt",
            app_config.GIFT_PROMPT,
        )
        user_prompt = gift_prompt.format(
            user_name=user.display_name,
            item_name=item_name,
            affection_level=affection_level_name,
        )

        # 将 system_prompt 和 user_prompt 合并
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        # 从 app_config 获取专用于礼物的生成配置
        gift_gen_config = app_config.GEMINI_GIFT_GEN_CONFIG

        log.info(f"为礼物 {item_name} 生成AI回应的完整提示: {combined_prompt}")

        # 构建 messages 格式
        messages = [{"role": "user", "content": combined_prompt}]

        # 创建 GenerationConfig
        config = GenerationConfig(
            temperature=gift_gen_config.get("temperature", 1.0),
            top_p=gift_gen_config.get("top_p", 0.95),
            max_output_tokens=gift_gen_config.get("max_output_tokens", 1024),
        )

        # 使用 ai_service.generate() 方法
        result = await self.ai_service.generate(messages=messages, config=config)
        response_text = result.content

        log.info(f"为礼物 {item_name} 生成AI回应的返回结果: {response_text}")

        return response_text or ""


# 创建单例
gift_service = GiftService(ai_service, AffectionService())
