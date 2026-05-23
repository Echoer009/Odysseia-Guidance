# -*- coding: utf-8 -*-
"""
URL 过滤服务 - 过滤搜索结果中的非官方 AI API 中转站和贩子站点
"""
import re
from typing import List, Any


# 已知非官方 AI API 中转/倒卖域名关键词（正则，匹配域名中包含这些词的）
_UNOFFICIAL_AI_DOMAIN_PATTERNS: List[re.Pattern] = [
    re.compile(r"api[-_]?(中转|代理|转发|zhongzhuan|proxy|relay)", re.IGNORECASE),
    re.compile(r"(key|api)[-_]?(批发|零售|代充|小店|店铺|商城|商店|shop|store|sell|buy)", re.IGNORECASE),
    re.compile(r"(openai|gpt|claude|gemini|deepseek)[-_]?(代理|中转|转发|zhuan|daili)", re.IGNORECASE),
    re.compile(r"(卖|售|出)(key|api|账号|account)", re.IGNORECASE),
    re.compile(r"(低价|便宜|白嫖|免费|福利)(api|key|gpt|claude|gemini)", re.IGNORECASE),
    re.compile(r"api[-_]?(站|平台|hub|portal)", re.IGNORECASE),
    re.compile(r"(openai|gpt|claude)[-_]?mirror", re.IGNORECASE),
    re.compile(r"aisdk|apihub|aigc.*(mall|shop|store)", re.IGNORECASE),
]

# 已知的非官方 API 贩子站点（完整域名匹配）
_UNOFFICIAL_AI_DOMAINS: set[str] = {
    "api.acytoo.com",
    "ai.acytoo.com",
    "chat.acytoo.com",
    "api.openai-proxy.com",
    "api.chatanywhere.tech",
    "api.chatanywhere.com.cn",
    "api.ohmygpt.com",
    "api2d.com",
    "api.forchange.cn",
    "api.qaqgpt.com",
    "api.gpt.ge",
    "api.aigc2d.com",
    "api.openai-sb.com",
    "api.gptsapi.net",
    "api.gptapi.us",
    "api.taobigang.com",
    "api.token-ai.cn",
    "api.xyhelper.cn",
    "api.cubeyun.cn",
    "api.zhizengzeng.com",
    "api.xiaoai.plus",
    "api.1rmb.tk",
    "api.mnzdna.xyz",
    "api.wisdgod.com",
    "api.aiask.icu",
    "api.pro365.space",
    "api.ailiaili.lat",
    "api.openai-hk.com",
    "api.openai365.net",
    "api.v36.cm",
    "api.jujustack.com",
    "api.yiweigpt.top",
    "api.luebana.eu.org",
    "api.chatnio.net",
    "api.bianxie.ai",
    "api.nextapi.fun",
    "api.tcip.top",
    "api.aiit.cc",
    "api.veesandbox.xyz",
    "freeapi.iqyi.us.kg",
    "api.g4f.icu",
    "api.autoexbot.com",
    "api.jchlu.cn",
    "api.nova-ai.top",
    "api.lks360.xyz",
    "api.godofai.xyz",
    "api.gpt8080.com",
    "api.xbbapi.xyz",
    "api.xtyxy.xyz",
    "api.waterai.eu.org",
    "api.aa1.cn",
    "api.kaie.work",
    "api.xiehuan.org",
}

# URL 路径中暗示中转/贩卖的关键词
_UNOFFICIAL_URL_PATH_KEYWORDS: List[str] = [
    "中转", "代理", "zhongzhuan", "proxy", "relay",
    "批发", "零售", "代充", "折扣", "discount", "cheap",
    "白嫖", "免费api", "免费key", "free-api", "free-key",
]


def is_unoffical_ai_api_site(url: str) -> bool:
    """
    判断 URL 是否为非官方 AI API 中转/贩卖站点。

    检查顺序：
    1. 域名完整匹配已知黑名单
    2. 域名正则匹配可疑模式
    3. URL 路径中包含可疑关键词
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False

    hostname_lower = hostname.lower()

    if hostname_lower in _UNOFFICIAL_AI_DOMAINS:
        return True

    if any(pat.search(hostname_lower) for pat in _UNOFFICIAL_AI_DOMAIN_PATTERNS):
        return True

    path_lower = parsed.path.lower()
    if any(kw in path_lower for kw in _UNOFFICIAL_URL_PATH_KEYWORDS):
        return True

    return False


def filter_ai_api_results(items: List[Any]) -> List[Any]:
    """
    从结果列表中剔除已知的非官方 AI API 中转/贩卖站点。

    Args:
        items: 待过滤的列表，每项可以是 str 或带有 .url 属性的对象

    Returns:
        过滤后的列表
    """
    filtered = []
    for item in items:
        url = item if isinstance(item, str) else getattr(item, "url", "")
        if not is_unoffical_ai_api_site(url):
            filtered.append(item)
    return filtered
