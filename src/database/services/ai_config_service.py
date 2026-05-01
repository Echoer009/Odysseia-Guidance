# -*- coding: utf-8 -*-
"""
AI 配置服务

通过 PostgreSQL 数据库管理 AI Provider 和 Model 配置。
"""

import logging
from typing import Optional, Dict, List, Any

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import AiProvider, AiModel
from src.database.database import AsyncSessionLocal

log = logging.getLogger(__name__)


class AiConfigService:
    """
    AI Provider / Model 配置的数据库 CRUD 服务。
    """

    @staticmethod
    async def get_all_providers(
        session: AsyncSession, enabled_only: bool = False
    ) -> List[AiProvider]:
        stmt = select(AiProvider).options(selectinload(AiProvider.models))
        if enabled_only:
            stmt = stmt.where(AiProvider.enabled == 1)
        stmt = stmt.order_by(AiProvider.id)
        result = await session.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    async def get_provider_by_name(
        session: AsyncSession, name: str
    ) -> Optional[AiProvider]:
        stmt = (
            select(AiProvider)
            .options(selectinload(AiProvider.models))
            .where(AiProvider.name == name)
        )
        result = await session.execute(stmt)
        return result.scalars().unique().first()

    @staticmethod
    async def create_provider(
        session: AsyncSession,
        name: str,
        provider_type: str,
        display_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> AiProvider:
        provider = AiProvider(
            name=name,
            provider_type=provider_type,
            display_name=display_name,
            api_key_encrypted=api_key,
            base_url=base_url,
            extra=extra,
            enabled=1,
        )
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        return provider

    @staticmethod
    async def update_provider(
        session: AsyncSession,
        provider_id: int,
        **kwargs,
    ) -> Optional[AiProvider]:
        stmt = select(AiProvider).where(AiProvider.id == provider_id)
        result = await session.execute(stmt)
        provider = result.scalars().first()
        if not provider:
            return None

        for key, value in kwargs.items():
            if key == "api_key":
                provider.api_key_encrypted = value
            elif hasattr(provider, key):
                setattr(provider, key, value)

        await session.commit()
        await session.refresh(provider)
        return provider

    @staticmethod
    async def delete_provider(session: AsyncSession, provider_id: int) -> bool:
        stmt = select(AiProvider).where(AiProvider.id == provider_id)
        result = await session.execute(stmt)
        provider = result.scalars().first()
        if not provider:
            return False
        await session.delete(provider)
        await session.commit()
        return True

    @staticmethod
    async def get_all_models(
        session: AsyncSession, enabled_only: bool = False
    ) -> List[AiModel]:
        stmt = select(AiModel).options(selectinload(AiModel.provider))
        if enabled_only:
            stmt = stmt.where(AiModel.enabled == 1)
        stmt = stmt.order_by(AiModel.id)
        result = await session.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    async def get_models_by_provider(
        session: AsyncSession, provider_id: int, enabled_only: bool = False
    ) -> List[AiModel]:
        stmt = select(AiModel).where(AiModel.provider_id == provider_id)
        if enabled_only:
            stmt = stmt.where(AiModel.enabled == 1)
        stmt = stmt.order_by(AiModel.id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_model_by_name(
        session: AsyncSession, model_name: str
    ) -> Optional[AiModel]:
        stmt = (
            select(AiModel)
            .options(selectinload(AiModel.provider))
            .where(AiModel.model_name == model_name)
        )
        result = await session.execute(stmt)
        return result.scalars().unique().first()

    @staticmethod
    async def create_model(
        session: AsyncSession,
        model_name: str,
        display_name: str,
        provider_id: int,
        actual_model: str,
        description: Optional[str] = None,
        supports_vision: bool = False,
        supports_tools: bool = True,
        supports_thinking: bool = False,
        max_output_tokens: int = 8192,
        generation_config: Optional[Dict[str, Any]] = None,
        prompt_config: Optional[Dict[str, Any]] = None,
    ) -> AiModel:
        model = AiModel(
            model_name=model_name,
            display_name=display_name,
            provider_id=provider_id,
            actual_model=actual_model,
            description=description,
            supports_vision=1 if supports_vision else 0,
            supports_tools=1 if supports_tools else 0,
            supports_thinking=1 if supports_thinking else 0,
            max_output_tokens=max_output_tokens,
            generation_config=generation_config,
            prompt_config=prompt_config,
            enabled=1,
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)
        return model

    @staticmethod
    async def update_model(
        session: AsyncSession,
        model_id: int,
        **kwargs,
    ) -> Optional[AiModel]:
        stmt = select(AiModel).where(AiModel.id == model_id)
        result = await session.execute(stmt)
        model = result.scalars().first()
        if not model:
            return None

        bool_fields = {"supports_vision", "supports_tools", "supports_thinking"}
        for key, value in kwargs.items():
            if hasattr(model, key):
                if key in bool_fields:
                    value = 1 if value else 0
                setattr(model, key, value)

        await session.commit()
        await session.refresh(model)
        return model

    @staticmethod
    async def delete_model(session: AsyncSession, model_id: int) -> bool:
        stmt = select(AiModel).where(AiModel.id == model_id)
        result = await session.execute(stmt)
        model = result.scalars().first()
        if not model:
            return False
        await session.delete(model)
        await session.commit()
        return True


ai_config_service = AiConfigService()
