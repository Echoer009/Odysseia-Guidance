from google.genai import types
import discord
import inspect
from typing import Optional, Dict, Callable, Any, List

import logging

from src.chat.config.chat_config import HIDDEN_TOOLS
from src.chat.features.tools.services.user_tool_settings_service import (
    user_tool_settings_service,
)

log = logging.getLogger(__name__)


class ToolService:
    """
    一个负责管理和执行 Gemini 模型工具的服务。

    它包含两个核心功能:
    1. 动态地为每个聊天上下文提供正确的工具列表。
    2. 执行模型请求的工具函数调用。
    """

    def __init__(
        self,
        bot: Optional[discord.Client],
        tool_map: Dict[str, Callable],
        tool_declarations: List[Callable],
    ):
        """
        初始化 ToolService。

        Args:
            bot: Discord 客户端实例，将注入到需要它的工具中。
            tool_map: 一个字典，将工具名称映射到其对应的异步函数实现。
            tool_declarations: 从工具加载器获得的原始工具函数声明列表。
        """
        self.bot = bot
        self.tool_map = tool_map
        self.tool_declarations = tool_declarations
        log.info(
            f"ToolService 已使用 {len(tool_map)} 个工具进行初始化: {list(tool_map.keys())}"
        )

    async def get_dynamic_tools_for_context(
        self, user_id_for_settings: Optional[str] = None
    ) -> List[Callable]:
        """
        根据提供的用户ID动态获取可用的工具列表。

        - 无论用户是否禁用工具，都返回所有工具声明。
        - 工具执行时会检查是否被用户禁用，如果被禁用则返回错误提示。

        Args:
            user_id_for_settings: 用于查询工具设置的用户的ID。如果为 None，则返回默认工具。

        Returns:
            所有工具函数列表（包括被用户禁用的工具）。
        """
        # 总是返回所有工具，让AI可以看到它们
        # 工具执行时会检查是否被禁用
        if not user_id_for_settings:
            log.info("未提供 user_id_for_settings，使用默认工具集。")
            return self.tool_declarations

        log.info(
            f"为用户 {user_id_for_settings} 返回所有工具声明（共 {len(self.tool_declarations)} 个）"
        )
        return self.tool_declarations

    async def execute_tool_call(
        self,
        tool_call: types.FunctionCall,
        channel: Optional[discord.TextChannel] = None,
        user_id: Optional[int] = None,
        log_detailed: bool = False,
        user_id_for_settings: Optional[str] = None,
    ) -> types.Part:
        """
        执行单个工具调用，并以可发送回 Gemini 模型的格式返回结果。
        这个版本通过依赖注入来提供上下文（如 bot 实例、channel），并处理备用参数（如 user_id）。

        Args:
            tool_call: 来自 Gemini API 响应的函数调用对象。
            channel: 可选的当前消息所在的 Discord 频道对象。
            user_id: 可选的当前消息作者的 Discord ID，用作某些参数的备用值。
            log_detailed: 是否记录详细日志。
            user_id_for_settings: 用于检查工具设置的用户ID（通常是帖子所有者的ID）。

        Returns:
            一个格式化为 FunctionResponse 的 Part 对象，其中包含工具的输出。
        """
        tool_name = tool_call.name
        if log_detailed:
            log.info(f"--- [工具执行流程]: 准备执行 '{tool_name}' ---")

        if not tool_name:
            log.error("接收到没有名称的工具调用。")
            return types.Part.from_function_response(
                name="unknown_tool",
                response={"error": "Tool call with no name received."},
            )

        tool_function = self.tool_map.get(tool_name)

        if not tool_function:
            log.error(f"找不到工具 '{tool_name}' 的实现。")
            return types.Part.from_function_response(
                name=tool_name, response={"error": f"Tool '{tool_name}' not found."}
            )

        # --- 检查工具是否被禁用 ---
        if user_id_for_settings:
            try:
                # HIDDEN_TOOLS 中的工具是系统必须保留的，不应该让用户控制
                if tool_name not in HIDDEN_TOOLS:
                    user_settings = (
                        await user_tool_settings_service.get_user_tool_settings(
                            user_id_for_settings
                        )
                    )
                    if user_settings and isinstance(user_settings, dict):
                        enabled_tools = user_settings.get("enabled_tools", [])
                        # 如果 enabled_tools 不为空且当前工具不在列表中，则禁用
                        if enabled_tools and tool_name not in enabled_tools:
                            log.info(
                                f"工具 '{tool_name}' 被 {user_id_for_settings} 禁用，拒绝执行。"
                            )
                            # 返回错误信息，让AI解释给用户
                            return types.Part.from_function_response(
                                name=tool_name,
                                response={
                                    "error": f"工具 '{tool_name}' 被帖子所有者禁用了。ta不让我干这个活啦!"
                                },
                            )
            except Exception as e:
                log.error(f"检查工具设置时出错: {e}", exc_info=True)
        # --- 结束检查 ---

        try:
            # 步骤 1: 从模型响应中提取参数
            tool_args: Dict[str, Any] = (
                {key: value for key, value in tool_call.args.items()}
                if tool_call.args
                else {}
            )
            if log_detailed:
                log.info(f"模型提供的参数: {tool_args}")

            # 步骤 2 & 3: 智能注入依赖和上下文
            # 我们不再检查函数签名，而是将所有可用的上下文信息直接注入
            # 到 tool_args 中。工具函数可以通过 **kwargs 来按需取用。
            sig = inspect.signature(tool_function)
            # 无条件注入 bot 实例，让工具函数可以通过 **kwargs 按需获取
            tool_args["bot"] = self.bot
            if log_detailed:
                log.info("已注入 'bot' 实例。")

            if user_id is not None:
                # 优先注入通用的 user_id
                # 统一将 user_id 转为字符串类型再注入，以适配工具函数的类型期望
                user_id_str = str(user_id)
                # 核心修复：只有当模型没有提供 user_id 时，才注入当前用户的 id 作为默认值。
                if "user_id" not in tool_args:
                    tool_args["user_id"] = user_id_str
                    if log_detailed:
                        log.info(
                            f"模型未提供 'user_id'，已注入当前用户 ID: {user_id_str}"
                        )

                # 为需要 author_id 的旧工具提供兼容性
                if "author_id" in sig.parameters and "author_id" not in tool_args:
                    tool_args["author_id"] = user_id_str
                    if log_detailed:
                        log.info(
                            f"为兼容性，已填充 'author_id': {tool_args['author_id']}"
                        )

            if channel:
                tool_args["channel"] = channel
                if log_detailed:
                    log.info(f"已注入 'channel' (ID: {channel.id}) 到 **kwargs。")
                if channel.guild:
                    # 同时注入 guild 对象本身和 guild_id，以提供最大的灵活性
                    tool_args["guild"] = channel.guild
                    tool_args["guild_id"] = str(channel.guild.id)
                    if log_detailed:
                        log.info(f"已注入 'guild' (ID: {channel.guild.id}) 实例。")
                if isinstance(channel, discord.Thread):
                    tool_args["thread_id"] = channel.id
                    if log_detailed:
                        log.info(f"检测到帖子上下文，已注入 'thread_id': {channel.id}")

            # 步骤 4: 智能地传递 log_detailed 参数
            if "log_detailed" in sig.parameters:
                tool_args["log_detailed"] = log_detailed

            # --- 安全加固：确保 'get_yearly_summary' 只能对当前用户执行 ---
            if tool_name == "get_yearly_summary" and user_id is not None:
                user_id_str = str(user_id)
                if tool_args.get("user_id") != user_id_str:
                    log.warning(
                        f"检测到模型为 get_yearly_summary 提供了不同的 user_id ({tool_args.get('user_id')})。"
                        f"已强制覆盖为当前用户 ID ({user_id_str})。"
                    )
                tool_args["user_id"] = user_id_str

            # --- 安全加固：确保 'issue_user_warning' 只能对当前用户执行 ---
            if tool_name == "issue_user_warning" and user_id is not None:
                user_id_str = str(user_id)
                if tool_args.get("user_id") != user_id_str:
                    log.warning(
                        f"检测到模型尝试为其他用户 ({tool_args.get('user_id')}) 调用警告工具。"
                        f"已强制重定向到当前用户 ({user_id_str})。"
                    )
                tool_args["user_id"] = user_id_str

            # 步骤 5: 执行工具函数
            result = await tool_function(**tool_args)
            if log_detailed:
                log.info(f"工具 '{tool_name}' 执行完毕。")

            # 步骤 5: 根据工具返回的结果，构造相应的 Part
            if "image_data" in result and isinstance(result["image_data"], dict):
                # 这是一个多模态（图片）结果
                image_info = result["image_data"]
                if log_detailed:
                    log.info(
                        f"检测到图片结果，MIME 类型: {image_info.get('mime_type')}"
                    )
                part = types.Part(
                    inline_data=types.Blob(
                        mime_type=image_info.get("mime_type", "image/png"),
                        data=image_info.get("data", b""),
                    )
                )
                if log_detailed:
                    log.info(f"已为 '{tool_name}' 构造包含图片的 Part。")
                return part
            else:
                # 这是一个标准的文本/JSON结果（包括错误信息）
                part = types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result or "操作成功完成，但没有返回文本内容。"},
                )
                if log_detailed:
                    log.info(f"已为 '{tool_name}' 构造标准的 FunctionResponse Part。")
                return part

        except Exception as e:
            log.error(f"执行工具 '{tool_name}' 时发生意外错误。", exc_info=True)
            return types.Part.from_function_response(
                name=tool_name,
                response={
                    "error": f"An unexpected error occurred during execution: {str(e)}"
                },
            )
