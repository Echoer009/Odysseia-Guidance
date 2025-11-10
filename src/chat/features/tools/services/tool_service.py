from google.genai import types
import discord
import inspect
from typing import Optional, Dict, Callable
import logging

log = logging.getLogger(__name__)


class ToolService:
    """
    一个负责执行 Gemini 模型请求的工具函数调用的服务。
    它使用一个从工具名称到可调用函数的映射来查找和运行适当的工具。
    """

    def __init__(self, bot: discord.Client, tool_map: Dict[str, Callable]):
        """
        初始化 ToolService。

        Args:
            bot: Discord 客户端实例，将注入到需要它的工具中。
            tool_map: 一个字典，将工具名称映射到其对应的异步函数实现。
        """
        self.bot = bot
        self.tool_map = tool_map
        log.info(
            f"ToolService 已使用 {len(tool_map)} 个工具进行初始化: {list(tool_map.keys())}"
        )

    async def execute_tool_call(
        self,
        tool_call: types.FunctionCall,
        channel: Optional[discord.TextChannel] = None,
        author_id: Optional[int] = None,
        log_detailed: bool = False,
    ) -> types.Part:
        """
        执行单个工具调用，并以可发送回 Gemini 模型的格式返回结果。
        这个版本通过依赖注入来提供上下文（如 bot 实例、channel），并处理备用参数（如 author_id）。

        Args:
            tool_call: 来自 Gemini API 响应的函数调用对象。
            channel: 可选的当前消息所在的 Discord 频道对象。
            author_id: 可选的当前消息作者的 Discord ID，用作某些参数的备用值。

        Returns:
            一个格式化为 FunctionResponse 的 Part 对象，其中包含工具的输出。
        """
        tool_name = tool_call.name
        if log_detailed:
            log.info(f"--- [工具执行流程]: 准备执行 '{tool_name}' ---")

        tool_function = self.tool_map.get(tool_name)

        if not tool_function:
            log.error(f"找不到工具 '{tool_name}' 的实现。")
            return types.Part.from_function_response(
                name=tool_name, response={"error": f"Tool '{tool_name}' not found."}
            )

        try:
            # 步骤 1: 从模型响应中提取参数
            tool_args = dict(tool_call.args)
            if log_detailed:
                log.info(f"模型提供的参数: {tool_args}")

            # 步骤 2: 注入应用程序级别的依赖项 (依赖注入)
            tool_args["bot"] = self.bot
            if log_detailed:
                log.info("已注入 'bot' 实例。")

            # 步骤 3: 注入上下文信息
            if author_id is not None:
                if not tool_args.get("user_id"):
                    tool_args["user_id"] = str(author_id)
                    if log_detailed:
                        log.info(
                            f"模型未提供有效 'user_id'，已自动填充为消息作者 ID: {author_id}"
                        )
            if channel:
                tool_args["channel"] = channel
                # 自动填充 guild_id
                if channel.guild:
                    tool_args.setdefault("guild_id", str(channel.guild.id))
                if log_detailed:
                    log.info(
                        f"已注入 'channel' (ID: {channel.id}) 和 'guild_id' (ID: {channel.guild.id if channel.guild else 'N/A'})。"
                    )

            # 步骤 4: 智能地传递 log_detailed 参数
            # 检查工具函数是否接受 'log_detailed' 关键字参数
            sig = inspect.signature(tool_function)
            if "log_detailed" in sig.parameters:
                tool_args["log_detailed"] = log_detailed

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
                    name=tool_name, response={"result": result}
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
