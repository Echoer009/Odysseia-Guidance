# -*- coding: utf-8 -*-
"""
google-genai SDK 兼容性补丁

问题：google-genai SDK（截至 1.57.0）在序列化请求时，把 bytes 字段
（如图片 inline_data.data）编码为 **URL-safe base64**（使用 - 和 _）。
Google 官方 API 同时接受标准/URL-safe 两种，但部分第三方代理（如 goldenglow）
只认标准 base64（+ 和 /），会报：
    Invalid value for variable $contents. Error in $***.***.***.data: invalid value for type Bytes

修复：将 SDK 内部 `_common.encode_unserializable_types` 中的 bytes 编码
从 URL-safe base64 改为标准 base64。标准 base64 是 Gemini REST API 的规范编码，
对官方端点和兼容代理都能正常工作。

该补丁在导入本模块时自动应用一次，幂等。
"""

import base64
import datetime
import logging

log = logging.getLogger(__name__)

_PATCHED = False


def apply_genai_compatibility_patch() -> bool:
    """
    给 google-genai SDK 打补丁，使其 bytes 字段使用标准 base64 而非 URL-safe base64。

    幂等：重复调用安全。

    Returns:
        bool: 本次是否实际应用了补丁（True=刚打上，False=已打过或 SDK 不可用）
    """
    global _PATCHED
    if _PATCHED:
        return False

    try:
        from google.genai import _common
    except ImportError:
        return False

    def _encode_unserializable_types_standard(data):
        """与 SDK 原函数等价，但 bytes 使用标准 base64。"""
        processed_data: dict = {}
        if not isinstance(data, dict):
            return data
        for key, value in data.items():
            if isinstance(value, bytes):
                processed_data[key] = base64.b64encode(value).decode("ascii")
            elif isinstance(value, datetime.datetime):
                processed_data[key] = value.isoformat()
            elif isinstance(value, dict):
                processed_data[key] = _encode_unserializable_types_standard(value)
            elif isinstance(value, list):
                if all(isinstance(v, bytes) for v in value):
                    processed_data[key] = [
                        base64.b64encode(v).decode("ascii") for v in value
                    ]
                elif all(isinstance(v, datetime.datetime) for v in value):
                    processed_data[key] = [v.isoformat() for v in value]
                else:
                    processed_data[key] = [
                        _encode_unserializable_types_standard(v)
                        if isinstance(v, dict)
                        else v
                        for v in value
                    ]
            else:
                processed_data[key] = value
        return processed_data

    _common.encode_unserializable_types = _encode_unserializable_types_standard
    _PATCHED = True
    log.info(
        "已对 google-genai SDK 应用 base64 兼容补丁：bytes 字段改用标准 base64，"
        "以兼容严格的第三方 Gemini 代理。"
    )
    return True


# 导入即应用
apply_genai_compatibility_patch()
