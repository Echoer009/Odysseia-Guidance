import logging
import uuid
import json
import aiohttp
from typing import Optional, Dict, Any, Union
import copy

from src.chat.config.chat_config import COMFYUI_CONFIG

log = logging.getLogger(__name__)

# 从配置中读取节点映射和输出节点ID
NODE_MAPPING = COMFYUI_CONFIG.get("NODE_MAPPING", {})
IMAGE_OUTPUT_NODE_ID = COMFYUI_CONFIG.get("IMAGE_OUTPUT_NODE_ID")


class ComfyUIService:
    """处理与 ComfyUI API 通信的所有业务逻辑"""

    def __init__(self, server_address: str, workflow_path: str):
        self.server_address = server_address
        self.workflow_path = workflow_path

        # 从 URL 中提取主机地址，用于构建 ws 和 http 地址
        host = server_address.replace("https://", "").replace("http://", "")

        self.ws_url = f"ws://{host}/ws"
        self.prompt_url = f"http://{host}/prompt"
        self.view_url = f"http://{host}/view"

        self.workflow_template = self._load_workflow_template()

    def _load_workflow_template(self) -> Optional[Dict[str, Any]]:
        """在服务初始化时加载一次工作流文件"""
        try:
            with open(self.workflow_path, "r", encoding="utf-8") as f:
                log.info(f"成功加载工作流模板: {self.workflow_path}")
                return json.load(f)
        except FileNotFoundError:
            log.error(f"工作流文件未找到: {self.workflow_path}")
            return None
        except json.JSONDecodeError:
            log.error(f"无法解析工作流文件: {self.workflow_path}")
            return None
        except Exception as e:
            log.error(f"加载工作流时发生未知错误: {e}")
            return None

    async def generate_image(self, **kwargs: Union[str, int, float]) -> Optional[bytes]:
        """
        生成图像的核心方法，接受动态参数。

        Args:
            **kwargs: 包含要修改参数的键值对。
                      键应与 COMFYUI_CONFIG.NODE_MAPPING 中的键匹配。
                      例如: positive_prompt="a cat", width=1024

        Returns:
            成功时返回图像的字节数据，失败时返回 None。
        """
        client_id = str(uuid.uuid4())

        try:
            if not self.workflow_template:
                log.error("工作流模板未加载，无法生成图像。")
                return None

            workflow = self._prepare_workflow(**kwargs)

            image_filename = await self._queue_prompt_and_get_result(
                client_id, workflow
            )
            if not image_filename:
                return None

            image_data = await self._get_image(image_filename)
            return image_data

        except Exception as e:
            log.error(f"图像生成过程中发生未知错误: {e}")
            return None

    def _prepare_workflow(self, **kwargs: Union[str, int, float]) -> Dict[str, Any]:
        """根据动态参数修改工作流节点的副本"""
        log.info("正在准备工作流...")
        workflow = copy.deepcopy(self.workflow_template)

        for key, value in kwargs.items():
            if value is None:
                continue

            if key in NODE_MAPPING:
                node_id, input_field = NODE_MAPPING[key]
                if node_id in workflow and input_field in workflow[node_id]["inputs"]:
                    workflow[node_id]["inputs"][input_field] = value
                    log.info(
                        f"参数 '{key}' 已更新: 节点 '{node_id}' 的 '{input_field}' 设置为 {value}"
                    )
                else:
                    log.warning(
                        f"在工作流中找不到节点 '{node_id}' 或输入 '{input_field}' 来设置参数 '{key}'"
                    )
            else:
                log.warning(f"配置中未定义参数 '{key}' 的节点映射")

        return workflow

    async def _queue_prompt_and_get_result(
        self, client_id: str, workflow: Dict[str, Any]
    ) -> Optional[str]:
        """通过 WebSocket 连接监听并获取最终的图片文件名"""
        log.info(f"[{client_id}] 正在连接 WebSocket 并提交任务...")

        async with aiohttp.ClientSession() as session:
            # 1. 建立 WebSocket 连接
            try:
                async with session.ws_connect(self.ws_url, timeout=30) as ws:
                    log.info(f"[{client_id}] WebSocket 连接成功")

                    # 2. 提交任务
                    prompt_data = {"prompt": workflow, "client_id": client_id}
                    async with session.post(
                        self.prompt_url, json=prompt_data
                    ) as response:
                        if response.status != 200:
                            log.error(
                                f"[{client_id}] 提交任务失败: {response.status} {await response.text()}"
                            )
                            return None
                        log.info(f"[{client_id}] 任务提交成功")

                    # 3. 监听 WebSocket 消息
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            # 寻找执行完成且包含输出数据的消息
                            if (
                                data.get("type") == "executed"
                                and data["data"]["node"] == IMAGE_OUTPUT_NODE_ID
                            ):
                                images = data["data"]["output"].get("images")
                                if images and len(images) > 0:
                                    filename = images[0]["filename"]
                                    log.info(
                                        f"[{client_id}] 成功获取图片文件名: {filename}"
                                    )
                                    return filename
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except Exception as e:
                log.error(f"[{client_id}] WebSocket 通信或任务提交时发生错误: {e}")
                return None
        return None

    async def _get_image(self, filename: str) -> Optional[bytes]:
        """根据文件名从 ComfyUI 下载图片"""
        log.info(f"正在下载图片: {filename}...")
        params = {"filename": filename}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.view_url, params=params) as response:
                    if response.status == 200:
                        log.info(f"图片 {filename} 下载成功")
                        return await response.read()
                    else:
                        log.error(
                            f"下载图片失败: {response.status} {await response.text()}"
                        )
                        return None
            except Exception as e:
                log.error(f"下载图片时发生错误: {e}")
                return None


# 单例实例 (将在 Cog 中初始化)
# comfyui_service = ComfyUIService(server_address="YOUR_COMFYUI_URL", workflow_path="PATH_TO_WORKFLOW.json")
