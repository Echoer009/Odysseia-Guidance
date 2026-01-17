from datetime import date
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import TokenUsage


class TokenUsageService:
    @staticmethod
    async def get_token_usage(
        session: AsyncSession, usage_date: date
    ) -> TokenUsage | None:
        result = await session.execute(
            select(TokenUsage).filter(TokenUsage.date == usage_date)
        )
        return result.scalars().first()

    @staticmethod
    async def create_token_usage(
        session: AsyncSession,
        usage_date: date,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> TokenUsage:
        new_usage = TokenUsage(
            date=usage_date,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            call_count=1,
        )
        session.add(new_usage)
        await session.commit()
        return new_usage

    @staticmethod
    async def update_token_usage(
        session: AsyncSession,
        usage_record: TokenUsage,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> TokenUsage:
        usage_record.input_tokens += input_tokens
        usage_record.output_tokens += output_tokens
        usage_record.total_tokens += total_tokens
        usage_record.call_count += 1
        await session.commit()
        return usage_record


token_usage_service = TokenUsageService()
