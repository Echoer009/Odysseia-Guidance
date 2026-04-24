# -*- coding: utf-8 -*-
"""
导入指定用户与类脑娘的聊天记录到对话块数据库，并生成 RAG 向量嵌入。

用法:
    python scripts/import_user_conversation_history.py --guild <服务器ID> --user <用户ID>

可选参数:
    --dry-run              仅遍历和统计，不写入数据库
    --block-size <N>       每个对话块包含的消息条数（默认 10）
    --max-messages <N>     最多读取的消息条数（默认 5000）
    --channel-ids <id,...> 只扫描指定频道ID（逗号分隔），不指定则扫描所有文字频道和帖子

运行前确保:
    1. .env 文件中 DISCORD_TOKEN、数据库配置正确
    2. Ollama 服务可用（如果 VECTOR_MODE=local）
"""

import asyncio
import argparse
import logging
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

import discord
from dotenv import load_dotenv
import os
from tqdm import tqdm

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from src.database.database import AsyncSessionLocal
from src.database.models import ConversationBlock
from src.chat.services.embedding_factory import (
    get_embedding_service,
    get_embedding_column,
)
from src.chat.config.chat_config import CONVERSATION_MEMORY_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

EMOJI_REGEX = re.compile(r"<a?:[^:]+:\d+>")


def clean_discord_emojis(text: str) -> str:
    cleaned = EMOJI_REGEX.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_discord_mentions(text: str, bot_user: discord.ClientUser) -> str:
    text = text.replace(f"<@{bot_user.id}>", f"@{bot_user.display_name}")
    text = text.replace(f"<@!{bot_user.id}>", f"@{bot_user.display_name}")
    return text.strip()


def format_conversation_text(messages: List[Dict]) -> str:
    lines = []
    for msg in messages:
        role = msg["role"]
        text = msg["text"]
        text = clean_discord_emojis(text)
        if role == "user":
            lines.append(f"用户: {text}")
        else:
            lines.append(f"类脑娘: {text}")
    return "\n".join(lines)


def extract_time_range(messages: List[Dict]) -> Tuple[datetime, datetime]:
    timestamps = [msg["timestamp"] for msg in messages if msg.get("timestamp")]
    if timestamps:
        ts_list = []
        for ts in timestamps:
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            ts_list.append(ts)
        return min(ts_list), max(ts_list)
    now = datetime.now()
    return now, now


def chunk_messages(messages: List[Dict], block_size: int) -> List[List[Dict]]:
    chunks = []
    for i in range(0, len(messages), block_size):
        chunks.append(messages[i : i + block_size])
    return chunks


class ConversationImporter(discord.Client):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        block_size: int,
        max_messages: int,
        channel_ids: Optional[List[int]],
        dry_run: bool,
    ):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)

        self.guild_id = guild_id
        self.user_id = user_id
        self.block_size = block_size
        self.max_blocks = CONVERSATION_MEMORY_CONFIG.get("max_blocks_per_user", 100)
        self.channel_ids = set(channel_ids) if channel_ids else None
        self.dry_run = dry_run

        self.collected_messages: List[Dict] = []
        self._ready_event = asyncio.Event()

    async def on_ready(self):
        log.info(f"Bot 已登录: {self.user}")
        self._ready_event.set()

    async def run_import(self):
        await self._ready_event.wait()

        guild = self.get_guild(self.guild_id)
        if not guild:
            log.error(f"未找到服务器 {self.guild_id}")
            await self.close()
            return

        log.info(f"目标服务器: {guild.name} ({guild.id})")
        log.info(f"目标用户 ID: {self.user_id}")
        log.info(f"Bot ID: {self.user.id}")

        target_member = guild.get_member(self.user_id)
        if target_member:
            log.info(f"目标用户: {target_member.display_name}")
        else:
            log.warning(f"在服务器中未找到用户 {self.user_id}，将继续扫描...")

        channels = []
        for channel in guild.text_channels:
            if self.channel_ids and channel.id not in self.channel_ids:
                continue
            channels.append(("text_channel", channel, channel.name))

        if hasattr(guild, 'forum_channels'):
            for forum_channel in guild.forum_channels:
                if self.channel_ids and forum_channel.id not in self.channel_ids:
                    continue
                channels.append(("forum_channel", forum_channel, forum_channel.name))

        log.info(f"共 {len(channels)} 个频道待扫描")

        total_scanned = 0
        for ch_type, channel, ch_name in tqdm(channels, desc="扫描频道", unit="ch"):
            log.info(f"扫描频道: {ch_name} ({channel.id}) [{ch_type}]")
            try:
                count = await self._scan_channel(ch_type, channel)
                total_scanned += count
                log.info(f"  频道 {ch_name}: 找到 {count} 条相关消息")
            except discord.Forbidden:
                log.warning(f"  无权限读取频道 {ch_name}，跳过")
            except Exception as e:
                log.error(f"  扫描频道 {ch_name} 时出错: {e}", exc_info=True)

        log.info(f"\n扫描完成，共收集到 {len(self.collected_messages)} 条相关消息")

        self.collected_messages.sort(key=lambda m: m["timestamp"])

        blocks = chunk_messages(self.collected_messages, self.block_size)
        log.info(f"共 {len(blocks)} 个对话块（block_size={self.block_size}）")

        max_blocks = CONVERSATION_MEMORY_CONFIG.get("max_blocks_per_user", 100)
        if len(blocks) > max_blocks:
            dropped = len(blocks) - max_blocks
            blocks = blocks[-max_blocks:]
            log.warning(
                f"对话块数量 ({len(blocks) + dropped}) 超过上限 ({max_blocks})，"
                f"丢弃最早的 {dropped} 个块，保留最新的 {max_blocks} 个"
            )

        for i, block_msgs in enumerate(blocks):
            text = format_conversation_text(block_msgs)
            start_t, end_t = extract_time_range(block_msgs)
            log.info(
                f"  块 {i+1}/{len(blocks)}: {len(block_msgs)} 条消息, "
                f"时间 {start_t.strftime('%Y-%m-%d %H:%M')} ~ "
                f"{end_t.strftime('%Y-%m-%d %H:%M')}"
            )

        if self.dry_run:
            log.info("\n[dry-run] 未写入数据库")
            await self.close()
            return

        await self._write_blocks(blocks)

        await self.close()

    async def _scan_channel(self, ch_type: str, channel) -> int:
        count = 0

        if ch_type == "text_channel":
            count += await self._read_message_history(channel)
            async for thread in channel.archived_threads(limit=None):
                if self.channel_ids and thread.id not in self.channel_ids:
                    continue
                count += await self._read_message_history(thread)
            for thread in channel.threads:
                if self.channel_ids and thread.id not in self.channel_ids:
                    continue
                count += await self._read_message_history(thread)

        elif ch_type == "forum_channel":
            async for thread in channel.archived_threads(limit=None):
                if self.channel_ids and thread.id not in self.channel_ids:
                    continue
                count += await self._read_message_history(thread)
            for thread in channel.threads:
                if self.channel_ids and thread.id not in self.channel_ids:
                    continue
                count += await self._read_message_history(thread)

        return count

    async def _read_message_history(self, channel, retries: int = 3) -> int:
        count = 0
        bot_id = self.user.id
        BATCH_SIZE = 1000
        total_read = 0
        target_user_msg_count = self.max_blocks * self.block_size
        user_count_total = 0

        all_messages = []
        before = None

        while True:
            batch = []
            for attempt in range(retries):
                try:
                    async for message in channel.history(
                        limit=BATCH_SIZE, before=before, oldest_first=False
                    ):
                        batch.append(message)
                    break
                except discord.Forbidden:
                    raise
                except Exception as e:
                    if attempt < retries - 1:
                        wait = 5 * (attempt + 1)
                        log.warning(f"  读取 {channel.name} 失败 ({e})，{wait}s 后重试 ({attempt+1}/{retries})...")
                        await asyncio.sleep(wait)
                    else:
                        log.error(f"读取 {channel.name} 历史消息出错（已重试 {retries} 次）: {e}")
                        batch = []
                        break

            if not batch:
                break

            all_messages.extend(batch)
            total_read += len(batch)

            user_in_batch = sum(1 for m in batch if m.author.id == self.user_id)
            user_count_total += user_in_batch
            log.info(
                f"  [{channel.name}] 已读 {total_read} 条 "
                f"(本批: {len(batch)} 条, 目标用户: {user_in_batch}, "
                f"累计目标用户: {user_count_total}/{target_user_msg_count})"
            )

            before = min(batch, key=lambda m: m.id)

            if len(batch) < BATCH_SIZE:
                break

            if user_count_total >= target_user_msg_count:
                log.info(f"  [{channel.name}] 已收集足够的目标用户消息 ({user_count_total}>={target_user_msg_count})，停止读取")
                break

            await asyncio.sleep(1.5)

        all_messages.sort(key=lambda m: m.id)

        log.info(f"  [{channel.name}] 共读取 {len(all_messages)} 条消息")

        user_count = sum(1 for m in all_messages if m.author.id == self.user_id)
        bot_count = sum(1 for m in all_messages if m.author.id == bot_id)
        other_count = len(all_messages) - user_count - bot_count
        log.info(f"  [{channel.name}] 用户消息: {user_count}, Bot消息: {bot_count}, 其他: {other_count}")

        for m in all_messages:
            if m.author.id == self.user_id:
                has_mention = f"<@{bot_id}>" in (m.content or "") or f"<@!{bot_id}>" in (m.content or "")
                has_ref = m.reference is not None and m.reference.message_id is not None
                log.info(f"  [USER样本] id={m.id} mention={has_mention} ref={has_ref} ref_id={m.reference.message_id if m.reference else None} content={repr((m.content or '')[:100])}")
                break

        convo_ids = set()

        changed = True
        iteration = 0
        while changed:
            changed = False
            iteration += 1
            added_this_round = 0
            for message in all_messages:
                if message.id in convo_ids:
                    continue

                author_id = message.author.id
                content = message.content or ""

                if not content.strip() and not message.stickers:
                    continue

                is_user = author_id == self.user_id
                is_bot = author_id == bot_id

                if not is_user and not is_bot:
                    continue

                add = False

                if is_user:
                    mentions_bot = f"<@{bot_id}>" in content or f"<@!{bot_id}>" in content
                    if mentions_bot:
                        add = True
                    if message.reference and message.reference.message_id:
                        ref_id = message.reference.message_id
                        if ref_id in convo_ids:
                            add = True

                if is_bot:
                    if message.reference and message.reference.message_id:
                        ref_id = message.reference.message_id
                        if ref_id in convo_ids:
                            add = True

                if add:
                    convo_ids.add(message.id)
                    changed = True
                    added_this_round += 1

            log.info(f"  [{channel.name}] 迭代 {iteration}: 新增 {added_this_round} 条, 总计 {len(convo_ids)} 条")

        for message in all_messages:
            if message.id not in convo_ids:
                continue
            content = message.content or ""
            if not content.strip() and not message.stickers:
                continue
            content = clean_discord_mentions(content, self.user)
            role = "user" if message.author.id == self.user_id else "model"
            self.collected_messages.append({
                "role": role,
                "text": content,
                "timestamp": message.created_at,
            })
            count += 1
            if count % 50 == 0 and count > 0:
                log.info(f"  {channel.name}: 已收集 {count} 条相关消息...")

        return count

    async def _write_blocks(self, blocks: List[List[Dict]]):
        embedding_service = await get_embedding_service()
        embedding_col = await get_embedding_column()

        log.info(f"当前 embedding 列: {embedding_col}")

        success = 0
        failed = 0
        total = len(blocks)

        for i, block_msgs in enumerate(
            tqdm(blocks, desc="写入对话块", unit="block")
        ):
            conversation_text = format_conversation_text(block_msgs)
            start_time, end_time = extract_time_range(block_msgs)

            embedding = None
            try:
                embedding = await embedding_service.generate_embedding(
                    text=conversation_text, task_type="retrieval_document"
                )
            except Exception as e:
                log.error(f"  生成 embedding 失败: {e}")

            if not embedding:
                log.warning(f"  对话块 {i+1} embedding 为空，跳过")
                failed += 1
                continue

            try:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        block = ConversationBlock(
                            discord_id=str(self.user_id),
                            conversation_text=conversation_text,
                            start_time=start_time,
                            end_time=end_time,
                            message_count=len(block_msgs),
                            summarized=0,
                        )

                        if embedding_col == "qwen_embedding":
                            block.qwen_embedding = embedding
                        else:
                            block.bge_embedding = embedding

                        session.add(block)
                        await session.flush()
                        block_id = block.id

                success += 1
                log.info(f"  对话块 {i+1} 写入成功 (id={block_id})")
            except Exception as e:
                log.error(f"  写入对话块 {i+1} 失败: {e}", exc_info=True)
                failed += 1

        log.info(f"\n写入完成: 成功 {success}, 失败 {failed}, 总计 {total}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="导入指定用户与类脑娘的聊天记录到对话块数据库"
    )
    parser.add_argument(
        "--guild", type=int, required=True, help="目标服务器 ID"
    )
    parser.add_argument(
        "--user", type=int, required=True, help="目标用户的 Discord ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅遍历和统计，不写入数据库",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=CONVERSATION_MEMORY_CONFIG.get("block_size", 10),
        help=f"每个对话块包含的消息条数（默认 {CONVERSATION_MEMORY_CONFIG.get('block_size', 10)}）",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="已废弃：现在自动读取全部消息",
    )
    parser.add_argument(
        "--channel-ids",
        type=str,
        default=None,
        help="只扫描指定频道ID（逗号分隔）",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    channel_ids = None
    if args.channel_ids:
        channel_ids = [int(x.strip()) for x in args.channel_ids.split(",") if x.strip()]

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.error("未找到 DISCORD_TOKEN，请检查 .env 文件")
        sys.exit(1)

    importer = ConversationImporter(
        guild_id=args.guild,
        user_id=args.user,
        block_size=args.block_size,
        max_messages=args.max_messages,
        channel_ids=channel_ids,
        dry_run=args.dry_run,
    )

    asyncio.create_task(importer.run_import())
    await importer.start(token)


if __name__ == "__main__":
    asyncio.run(main())
