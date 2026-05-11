# -*- coding: utf-8 -*-
import base64
import random
import time
import logging
from typing import Optional
from pathlib import Path

import httpx

from src.chat.config.chat_config import GPT_IMAGE_CONFIG

log = logging.getLogger(__name__)


class GPTImageService:
    def __init__(self):
        self._api_key = GPT_IMAGE_CONFIG["API_KEY"]
        self._base_url = GPT_IMAGE_CONFIG["BASE_URL"]
        self._model = GPT_IMAGE_CONFIG["MODEL"]
        self._size = GPT_IMAGE_CONFIG["SIZE"]
        self._quality = GPT_IMAGE_CONFIG["QUALITY"]
        self._timeout = GPT_IMAGE_CONFIG["TIMEOUT"]
        self._reference_image_url = GPT_IMAGE_CONFIG.get("REFERENCE_IMAGE_URL")
        self._client: Optional[httpx.AsyncClient] = None
        self._reference_images: list[bytes] = []
        self._initialized = False

    async def initialize(self):
        if not self._api_key:
            log.warning("GPTImageService: 未配置 API key，服务已禁用")
            self._initialized = True
            return

        assets_dir = Path(__file__).parent.parent.parent.parent / "assets"
        for f in sorted(assets_dir.glob("ref_*.png")):
            data = f.read_bytes()
            self._reference_images.append(data)
            log.info(f"GPTImageService: 加载参考图 {f.name} ({len(data)} bytes)")

        if not self._reference_images:
            log.warning("GPTImageService: assets/ 下无 reference_*.png 文件")
            if self._reference_image_url:
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(self._reference_image_url)
                        resp.raise_for_status()
                        self._reference_images.append(resp.content)
                        log.info(
                            f"GPTImageService: 已缓存远程参考图 ({len(resp.content)} bytes)"
                        )
                except Exception as e:
                    log.warning(f"GPTImageService: 缓存参考图片失败: {e}")

        log.info(
            f"GPTImageService 初始化完成, base_url={self._base_url}, model={self._model}"
        )
        self._initialized = True

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        return self._client

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def generate_feeding_image(
        self,
        food_image_bytes: bytes,
        food_mime_type: str,
        food_description: str,
        scene_description: str = "",
    ) -> Optional[bytes]:
        if not self.is_available:
            return None

        start_time = time.time()
        scene_text = scene_description if scene_description else ""
        log.info(
            f"GPTImageService: 开始生成图片，食物='{food_description}', "
            f"场景描写='{scene_text[:60] if scene_text else '无'}'"
        )

        try:
            if self._reference_images:
                picked = random.choice(self._reference_images)
                log.info(
                    f"GPTImageService: 随机选中参考图 ({len(picked)} bytes, 共 {len(self._reference_images)} 张)"
                )
                result = await self._try_edit(
                    food_image_bytes, food_mime_type, scene_text or food_description, picked
                )
            else:
                log.info("GPTImageService: 无参考图，跳过 EDIT 策略")
                result = None
            if result is not None:
                elapsed = time.time() - start_time
                log.info(
                    f"GPTImageService: [EDIT] 成功, 耗时 {elapsed:.2f}s, 大小={len(result)} bytes"
                )
                return result
        except Exception as e:
            elapsed = time.time() - start_time
            log.warning(f"GPTImageService: [EDIT] 失败, 耗时 {elapsed:.2f}s: {e}")

        try:
            result = await self._try_generate(scene_text or food_description)
            if result is not None:
                elapsed = time.time() - start_time
                log.info(
                    f"GPTImageService: [GENERATE] 成功, 耗时 {elapsed:.2f}s, 大小={len(result)} bytes"
                )
                return result
        except Exception as e:
            elapsed = time.time() - start_time
            log.error(f"GPTImageService: [GENERATE] 失败, 耗时 {elapsed:.2f}s: {e}")

        elapsed = time.time() - start_time
        log.error(f"GPTImageService: 所有策略均失败, 总耗时 {elapsed:.2f}s")
        return None

    async def _try_edit(
        self,
        food_image_bytes: bytes,
        food_mime_type: str,
        scene_text: str,
        reference_bytes: bytes,
    ) -> Optional[bytes]:
        client = self._get_client()

        prompt = (
            scene_text
            if scene_text
            else (
                "画该角色（只参考第一张图的人物外貌和画风）"
                "正在开心吃着第二张图中的食物。\n"
                "**禁止参考原图的姿势、角度、背景和环境**，自由构图，"
                "食物看起来美味诱人，角色表情愉悦满足，整体氛围轻松温馨。"
            )
        )

        files = [
            ("image", ("reference.png", reference_bytes, "image/png")),
            ("image", ("food.png", food_image_bytes, food_mime_type or "image/png")),
        ]
        data = {
            "model": self._model,
            "prompt": prompt,
            "n": "1",
            "size": self._size,
            "input_fidelity": "low",
            "response_format": "b64_json",
        }

        response = await client.post("/images/edits", files=files, data=data)
        response.raise_for_status()
        return self._extract_image(response.json())

    async def _try_generate(self, prompt_text: str) -> Optional[bytes]:
        client = self._get_client()

        prompt = prompt_text or "一个可爱的动漫少女正在开心地吃着美味的食物，表情愉悦。温暖柔和的插画风格。"

        body = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "size": self._size,
            "quality": self._quality,
            "response_format": "b64_json",
        }

        response = await client.post("/images/generations", json=body)
        response.raise_for_status()
        return self._extract_image(response.json())

    def _extract_image(self, response_data: dict) -> Optional[bytes]:
        images = response_data.get("data", [])
        if not images:
            log.warning("GPTImageService: 响应中无图片数据")
            return None

        image_data = images[0]

        if "b64_json" in image_data:
            return base64.b64decode(image_data["b64_json"])

        log.warning(
            f"GPTImageService: 非预期的响应格式: {list(image_data.keys())}"
        )
        return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


gpt_image_service = GPTImageService()
