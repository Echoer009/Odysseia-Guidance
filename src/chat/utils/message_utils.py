# -*- coding: utf-8 -*-

import discord

DISCORD_MESSAGE_LIMIT = 2000
DISCORD_EMBED_DESCRIPTION_LIMIT = 4096
DISCORD_EMBED_FIELD_VALUE_LIMIT = 1024


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = None
        for sep in ["\n\n", "\n", " "]:
            idx = remaining.rfind(sep, 0, limit)
            if idx > limit * 0.25:
                split_at = idx
                break

        if split_at is None:
            split_at = limit

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n ")

    return chunks


def truncate_text(text: str, limit: int, suffix: str = "...") -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)] + suffix


async def safe_send(sendable, text: str, **kwargs) -> list[discord.Message]:
    chunks = split_message(text)
    messages = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            msg = await sendable.send(chunk, **kwargs)
        else:
            msg = await sendable.send(chunk)
        messages.append(msg)
    return messages


async def safe_reply(
    message: discord.Message, text: str, **kwargs
) -> list[discord.Message]:
    chunks = split_message(text)
    messages = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            msg = await message.reply(chunk, **kwargs)
        else:
            msg = await message.channel.send(chunk)
        messages.append(msg)
    return messages
