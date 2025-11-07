from google.genai import types
import discord
import inspect
from typing import Optional, Dict, Callable, Any
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
        author_id: Optional[int] = None,
    ) -> types.Part:
        """
        执行单个工具调用，并以可发送回 Gemini 模型的格式返回结果。
        这个版本通过依赖注入来提供上下文（如 bot 实例），并处理备用参数（如 author_id）。

        Args:
            tool_call: 来自 Gemini API 响应的函数调用对象。
            author_id: 可选的当前消息作者的 Discord ID，用作某些参数的备用值。

        Returns:
            一个格式化为 FunctionResponse 的 Part 对象，其中包含工具的输出。
        """
        tool_name = tool_call.name
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
            log.info(f"模型提供的参数: {tool_args}")

            # 步骤 2: 注入应用程序级别的依赖项 (依赖注入)
            # 这些是模型不知道也不需要知道的运行时对象。
            tool_args["bot"] = self.bot
            log.info("已注入 'bot' 实例。")

            # 步骤 3: 注入上下文信息
            # 如果工具需要 user_id 但模型没有提供，则使用 author_id 作为备用
            if author_id is not None:
                # 使用 setdefault 避免覆盖模型已经提供的 user_id
                tool_args.setdefault("user_id", str(author_id))
                log.info(
                    f"确保 'user_id' 存在 (备用值为 author_id): {tool_args['user_id']}"
                )

            # 步骤 4: 执行工具函数
            result = await tool_function(**tool_args)
            log.info(f"工具 '{tool_name}' 执行完毕。")

            # 步骤 5: 根据工具返回的结果，构造相应的 Part
            if "image_data" in result and isinstance(result["image_data"], dict):
                # 这是一个多模态（图片）结果
                image_info = result["image_data"]
                log.info(f"检测到图片结果，MIME 类型: {image_info.get('mime_type')}")
                part = types.Part(
                    inline_data=types.Blob(
                        mime_type=image_info.get("mime_type", "image/png"),
                        data=image_info.get("data", b""),
                    )
                )
                log.info(f"已为 '{tool_name}' 构造包含图片的 Part。")
                return part
            else:
                # 这是一个标准的文本/JSON结果（包括错误信息）
                part = types.Part.from_function_response(
                    name=tool_name, response={"result": result}
                )
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
