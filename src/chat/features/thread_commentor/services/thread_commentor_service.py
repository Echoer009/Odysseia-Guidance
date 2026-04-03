# -*- coding: utf-8 -*-

import logging
import json
import discord
from typing import Optional
from sqlalchemy.future import select
from datetime import datetime, timezone, timedelta

from src.chat.services.ai.service import ai_service
from src.chat.services.ai.providers.base import GenerationConfig
from src.chat.config.thread_prompts import get_random_praise_prompt
from src.chat.config.prompts import PROMPT_CONFIG
from src.chat.utils.prompt_utils import replace_emojis, get_thread_commentor_persona
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.config import chat_config
from src.database.database import AsyncSessionLocal
from src.database.models import CommunityMemberProfile

log = logging.getLogger(__name__)


class ThreadCommentorService:
    """处理新帖子评价功能的服务"""

    async def _get_user_memory(self, user_id: int) -> str:
        """
        从世界书和 ParadeDB 中获取用户的个人记忆。
        """
        memory_parts = []

        # 1. 从世界书获取用户档案
        try:
            profile_data = await world_book_service.get_profile_by_discord_id(user_id)
            if profile_data:
                source_data = {}
                source_metadata = profile_data.get("source_metadata")
                if isinstance(source_metadata, dict):
                    content_json_str = source_metadata.get("content_json")
                    if isinstance(content_json_str, str):
                        try:
                            source_data.update(json.loads(content_json_str))
                        except json.JSONDecodeError:
                            pass
                    for key in ["name", "personality", "background", "preferences"]:
                        if key in source_metadata and source_metadata[key]:
                            source_data[key] = source_metadata[key]
                source_data.update(profile_data)

                profile_map = {
                    "昵称": source_data.get("title") or source_data.get("name"),
                    "性格": source_data.get("personality"),
                    "背景": source_data.get("background"),
                    "偏好": source_data.get("preferences"),
                }
                profile_details = [
                    f"- {k}: {v}" for k, v in profile_map.items() if v and v != "未提供"
                ]
                if profile_details:
                    memory_parts.append(
                        "用户的公开档案：\n" + "\n".join(profile_details)
                    )
        except Exception as e:
            log.error(f"从世界书为用户 {user_id} 获取档案时出错: {e}")

        # 2. 从 ParadeDB 获取个人记忆摘要
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(CommunityMemberProfile.personal_summary).where(
                    CommunityMemberProfile.discord_id == str(user_id)
                )
                result = await session.execute(stmt)
                summary = result.scalars().first()
                if summary:
                    summary_text = f"我与该用户的过往对话摘要：\n{summary}"
                    memory_parts.append(summary_text)
        except Exception as e:
            log.error(f"从 ParadeDB 为用户 {user_id} 获取摘要时出错: {e}")

        if not memory_parts:
            return "关于这位用户，我暂时还没有任何记忆。"

        return "\n\n---\n".join(memory_parts)

    async def praise_new_thread(
        self, thread: discord.Thread, user_id: int, user_nickname: str
    ) -> Optional[str]:
        """
        针对新创建的帖子生成一段结合用户记忆的个性化夸奖。
        """
        try:
            log.info(f"[暖贴调试] 开始处理帖子 '{thread.name}' (ID: {thread.id})")
            log.info(f"[暖贴调试] 用户 ID: {user_id}, 昵称: {user_nickname}")

            # 检查用户是否禁用了暖贴功能
            has_withered = await coin_service.has_withered_sunflower(user_id)
            log.info(f"[暖贴调试] 用户是否禁用暖贴: {has_withered}")
            if has_withered:
                log.info(
                    f"用户 {user_id} 已禁用暖贴功能，跳过对帖子 '{thread.name}' 的评价。"
                )
                return None

            # 检查用户是否禁用了帖子回复功能
            blocks_replies = await coin_service.blocks_thread_replies(user_id)
            log.info(f"[暖贴调试] 用户是否禁用帖子回复: {blocks_replies}")
            if blocks_replies:
                log.info(
                    f"用户 {user_id} 已禁用帖子回复功能，跳过对帖子 '{thread.name}' 的评价。"
                )
                return None

            # 1. 获取帖子的初始消息
            # 注意：thread.starter_message 可能返回缓存中不完整的消息对象
            # 始终使用 fetch_message 来获取完整内容
            log.info("[暖贴调试] 尝试获取帖子初始消息...")
            try:
                # 使用 thread.id 作为起始消息的 ID
                first_message = await thread.fetch_message(thread.id)
                log.info("[暖贴调试] 从 fetch_message 获取成功")
            except discord.NotFound:
                log.warning(f"[暖贴调试] 无法找到帖子 {thread.id} 的初始消息")
                first_message = None
            except Exception as e:
                log.error(f"[暖贴调试] 获取帖子初始消息时出错: {e}")
                first_message = None

            log.info(f"[暖贴调试] first_message 存在: {first_message is not None}")
            if first_message:
                log.info(
                    f"[暖贴调试] first_message.content 长度: {len(first_message.content) if first_message.content else 0}"
                )
                # 检查是否有附件
                has_attachments = (
                    first_message.attachments and len(first_message.attachments) > 0
                )
                log.info(f"[暖贴调试] 是否有附件: {has_attachments}")

            if not first_message:
                log.info(
                    f"帖子 '{thread.name}' (ID: {thread.id}) 无法获取初始消息，跳过评价。"
                )
                return None

            # 2. 准备帖子内容
            title = thread.name
            tags = ", ".join([tag.name for tag in thread.applied_tags])

            # 处理内容：如果没有文字但有附件，使用占位符
            content = first_message.content
            if not content:
                if first_message.attachments:
                    # 有附件但没有文字
                    attachment_count = len(first_message.attachments)
                    content = f"[用户上传了 {attachment_count} 个附件（图片/文件）]"
                else:
                    # 既没有文字也没有附件
                    log.info(
                        f"帖子 '{thread.name}' (ID: {thread.id}) 没有有效的初始消息内容，跳过评价。"
                    )
                    return None

            max_content_length = 1500
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            thread_full_content = f"标题: {title}\n标签: {tags}\n内容: {content}"

            # 3. 获取用户记忆
            user_memory = await self._get_user_memory(user_id)

            # 4. 新增：调用 RAG 服务进行世界书搜索
            rag_context = ""
            try:
                log.info(f"开始为帖子 '{title}' 的内容进行 RAG 搜索...")
                rag_results = await world_book_service.find_entries(
                    latest_query=thread_full_content,
                    user_id=user_id,
                    guild_id=thread.guild.id,
                    user_name=user_nickname,
                    n_results=chat_config.RAG_N_RESULTS_THREAD_COMMENTOR,  # 最多获取10个相关条目
                    max_distance=0.7,
                )
                if rag_results:
                    rag_context_parts = [
                        "为了帮助你更好地理解帖子中可能提到的社区术语，这里有一些相关的背景知识："
                    ]
                    for result in rag_results:
                        entry_title = result.get("metadata", {}).get(
                            "title", "未知标题"
                        )
                        entry_content = result.get("document", "无内容")
                        rag_context_parts.append(
                            f"- **{entry_title}**: {entry_content}"
                        )

                    rag_context = "\n".join(rag_context_parts)
                    log.info(
                        f"RAG 搜索成功，为帖子 '{title}' 找到了 {len(rag_results)} 个相关条目。"
                    )
                else:
                    log.info(f"RAG 搜索没有为帖子 '{title}' 找到相关条目。")
            except Exception as e:
                log.error(
                    f"为帖子 '{title}' 进行 RAG 搜索时发生错误: {e}", exc_info=True
                )

            # 5. 准备调用所需的所有信息片段
            core_persona = get_thread_commentor_persona()
            task_prompt = get_random_praise_prompt().format(user_nickname=user_nickname)

            log.info(f"为帖子 '{title}' 构建带有破限功能的统一上下文，即将调用AI服务。")

            # 6. 手动构建带有“破限”逻辑的对话历史
            conversation_history = [
                {
                    "role": "user",
                    "parts": [PROMPT_CONFIG["default"]["JAILBREAK_USER_PROMPT"]],
                },
                {
                    "role": "model",
                    "parts": [PROMPT_CONFIG["default"]["JAILBREAK_MODEL_RESPONSE"]],
                },
                {"role": "user", "parts": [core_persona]},
                {"role": "model", "parts": ["好的，我是类脑娘，已经准备好了"]},
                {"role": "user", "parts": [user_memory]},
                {"role": "model", "parts": ["关于你的事情，我当然都记得"]},
            ]

            # 如果有 RAG 结果，则注入
            if rag_context:
                conversation_history.append({"role": "user", "parts": [rag_context]})
                conversation_history.append(
                    {"role": "model", "parts": ["哦哦，原来是这样！我明白了！"]}
                )

            conversation_history.extend(
                [
                    {"role": "user", "parts": [task_prompt]},
                    {"role": "model", "parts": ["好的，我记下了。"]},
                ]
            )

            # 注入最终指令到最后一条 model 消息
            beijing_tz = timezone(timedelta(hours=8))
            current_beijing_time = datetime.now(beijing_tz).strftime(
                "%Y年%m月%d日 %H:%M"
            )
            final_injection_content = PROMPT_CONFIG["default"][
                "JAILBREAK_FINAL_INSTRUCTION"
            ].format(
                guild_name=thread.guild.name,
                location_name=thread.parent.name if thread.parent else "未知版区",
                current_time=current_beijing_time,
            )

            last_model_message = conversation_history[-1]
            if last_model_message["role"] == "model" and last_model_message["parts"]:
                last_model_message["parts"][0] += f" {final_injection_content}"

            # 添加最终的用户输入（帖子内容）
            conversation_history.append(
                {"role": "user", "parts": [thread_full_content]}
            )

            # 7. 调用 AIService 生成评价
            config = GenerationConfig(temperature=1.0, max_output_tokens=1024)
            result = await ai_service.generate(
                messages=conversation_history, config=config
            )
            praise_text = result.content

            if praise_text:
                # 使用 prompt_utils 中的函数来处理表情符号
                processed_praise = replace_emojis(praise_text)
                log.info(f"成功为帖子 '{title}' 生成并处理后评价: {processed_praise}")
                return processed_praise
            else:
                log.warning(f"为帖子 '{title}' 生成评价时返回了空内容。")
                return None

        except discord.errors.NotFound:
            log.warning(f"无法找到帖子 {thread.id} 的初始消息，可能已被删除。")
            return None
        except Exception as e:
            log.error(
                f"为帖子 '{thread.name}' (ID: {thread.id}) 生成评价时发生意外错误: {e}",
                exc_info=True,
            )
            return None


thread_commentor_service = ThreadCommentorService()
