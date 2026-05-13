# -*- coding: utf-8 -*-
"""
用户人设偏好服务 + Prompt 人设变体 单元测试
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.chat.services.persona_preference_service import (
    PersonaPreferenceService,
    persona_preference_service,
)
from src.chat.services.prompt_service import PromptService
from src.chat.config.prompts import PROMPT_CONFIG, PERSONA_VARIANTS


# ---------------------------------------------------------------------------
# PersonaPreferenceService — DB 交互测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPersonaPreferenceService:
    """测试 PersonaPreferenceService 的数据库读写。"""

    async def test_get_persona_style_default_when_no_record(self, clean_tables):
        """没有记录时返回 default。"""
        style = await persona_preference_service.get_persona_style("99999")
        assert style == "default"

    async def test_set_persona_style_gentle(self, clean_tables):
        """设置 gentle 后能正确读取。"""
        ok = await persona_preference_service.set_persona_style("10001", "gentle")
        assert ok is True

        style = await persona_preference_service.get_persona_style("10001")
        assert style == "gentle"

    async def test_set_persona_style_default_explicitly(self, clean_tables):
        """显式设置 default 后能正确读取。"""
        await persona_preference_service.set_persona_style("10002", "gentle")
        await persona_preference_service.set_persona_style("10002", "default")

        style = await persona_preference_service.get_persona_style("10002")
        assert style == "default"

    async def test_set_persona_style_invalid(self, clean_tables):
        """无效的 style 值会被拒绝。"""
        ok = await persona_preference_service.set_persona_style("10003", "unknown")
        assert ok is False

    async def test_set_persona_style_updates_existing(self, clean_tables):
        """重复设置会更新而非创建新记录。"""
        await persona_preference_service.set_persona_style("10004", "gentle")
        await persona_preference_service.set_persona_style("10004", "default")

        style = await persona_preference_service.get_persona_style("10004")
        assert style == "default"

    async def test_multiple_users_independent(self, clean_tables):
        """不同用户的偏好互不影响。"""
        await persona_preference_service.set_persona_style("10010", "gentle")
        await persona_preference_service.set_persona_style("10011", "default")

        assert await persona_preference_service.get_persona_style("10010") == "gentle"
        assert await persona_preference_service.get_persona_style("10011") == "default"
        assert await persona_preference_service.get_persona_style("10012") == "default"


# ---------------------------------------------------------------------------
# PromptService._get_persona_system_prompt — 纯逻辑测试（不需要 DB）
# ---------------------------------------------------------------------------


class TestGetPersonaSystemPrompt:
    """测试 PromptService._get_persona_system_prompt 的变体查找逻辑。"""

    def setup_method(self):
        self.service = PromptService()

    def test_default_style_returns_none(self):
        """default 风格应返回 None，表示不覆盖。"""
        result = self.service._get_persona_system_prompt("default", None)
        assert result is None

    def test_unknown_style_returns_none(self):
        """不存在的 style 返回 None。"""
        result = self.service._get_persona_system_prompt("nonexistent", None)
        assert result is None

    def test_gentle_default_model(self):
        """gentle + 无模型名 → 返回 PERSONA_VARIANTS['gentle']['default'] 的 SYSTEM_PROMPT。"""
        result = self.service._get_persona_system_prompt("gentle", None)
        assert result is not None
        assert "信任优先" in result

    def test_gentle_with_model_no_override(self):
        """gentle + 存在的模型名但该模型无专属变体 → fallback 到 default。"""
        result = self.service._get_persona_system_prompt("gentle", "gemini-3-flash-custom")
        assert result is not None
        assert "信任优先" in result

    def test_gentle_with_nonexistent_model(self):
        """gentle + 不存在的模型名 → fallback 到 default。"""
        result = self.service._get_persona_system_prompt("gentle", "some-random-model")
        assert result is not None


# ---------------------------------------------------------------------------
# PromptService + PERSONA_VARIANTS 数据完整性
# ---------------------------------------------------------------------------


class TestPersonaVariantsDataIntegrity:
    """测试 PERSONA_VARIANTS 配置的完整性。"""

    def test_gentle_variant_exists(self):
        assert "gentle" in PERSONA_VARIANTS

    def test_gentle_has_default_key(self):
        assert "default" in PERSONA_VARIANTS["gentle"]

    def test_gentle_has_system_prompt(self):
        prompt = PERSONA_VARIANTS["gentle"]["default"]["SYSTEM_PROMPT"]
        assert prompt is not None
        assert len(prompt.strip()) > 100

    def test_gentle_prompt_differs_from_default(self):
        """温柔版提示词应与 default 版有区别。"""
        default_prompt = PROMPT_CONFIG["default"]["SYSTEM_PROMPT"]
        gentle_prompt = PERSONA_VARIANTS["gentle"]["default"]["SYSTEM_PROMPT"]
        assert default_prompt != gentle_prompt
