# -*- coding: utf-8 -*-
"""大合影导出合成器：背景 + 圆形头像(无边框) + 名字小标签。

被 GET /api/photo/export 调用，也可以独立运行做本地测试。
头像直径随人数自适应（与前端同一份梯度），人越多越小。
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

LABEL_BG = (8, 13, 32, 200)
LABEL_TEXT = (244, 236, 214)
GOLD = (232, 201, 122)


def avatar_diameter_ratio(count: int) -> float:
    """头像直径（相对图片宽度的比例）随人数自适应。"""
    if count < 20:
        return 0.045
    if count < 50:
        return 0.038
    if count < 100:
        return 0.031
    if count < 200:
        return 0.026
    return 0.022


# CJK 字体候选：Windows 本机 / 常见 Linux 容器路径 / 本功能自带 fonts 目录
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_font_cache: Dict[int, Any] = {}


def _local_font_candidates() -> List[str]:
    bundled = Path(__file__).resolve().parent / "fonts"
    if bundled.is_dir():
        return sorted(str(p) for p in bundled.glob("*.[to]tf*"))
    return []


def _load_font(size: int):
    """按候选列表加载字体，全部失败则退回 Pillow 默认字体。"""
    if size in _font_cache:
        return _font_cache[size]
    font = None
    for candidate in _local_font_candidates() + _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(candidate, size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def _circular_avatar(avatar: Image.Image, diameter: int) -> Image.Image:
    """把头像裁成圆形（4x 超采样保证边缘平滑，无边框）。"""
    ss = 4
    big = diameter * ss
    src = avatar.convert("RGB").resize((big, big), Image.Resampling.LANCZOS)

    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, big - 1, big - 1], fill=255)
    mask = mask.resize((diameter, diameter), Image.Resampling.LANCZOS)

    out = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    out.paste(src.resize((diameter, diameter), Image.Resampling.LANCZOS), (0, 0), mask)
    return out


def _placeholder_avatar(display_name: str, diameter: int) -> Image.Image:
    """无头像时的占位贴纸：深蓝圆面 + 名字首字（无边框）。"""
    out = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    draw.ellipse([0, 0, diameter - 1, diameter - 1], fill=(24, 36, 68, 255))
    ch = (display_name or "?").strip()[:1] or "?"
    font = _load_font(max(14, int(diameter * 0.42)))
    bbox = draw.textbbox((0, 0), ch, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((diameter - w) / 2 - bbox[0], (diameter - h) / 2 - bbox[1]),
        ch,
        font=font,
        fill=GOLD,
    )
    return out


def _draw_name_label(
    draw: ImageDraw.ImageDraw, cx: float, top: float, name: str, diameter: int
) -> None:
    """头像下方的名字小标签（圆角深色底 + 浅金字），字号随头像尺寸缩放。"""
    font = _load_font(max(13, int(diameter * 0.26)))
    text = name.strip()[:20]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 8, 5
    box_w, box_h = tw + pad_x * 2, th + pad_y * 2
    x0, y0 = cx - box_w / 2, top
    draw.rounded_rectangle(
        [x0, y0, x0 + box_w, y0 + box_h],
        radius=box_h / 2,
        fill=LABEL_BG,
    )
    draw.text((x0 + pad_x - bbox[0], y0 + pad_y - bbox[1]), text, font=font, fill=LABEL_TEXT)



def compose_photo(background_path: str, entries: List[Dict[str, Any]]) -> bytes:
    """合成完整大合影，返回 PNG 字节流。所见即所得：仅背景 + 头像 + 名字，不额外添加任何元素。"""
    bg = Image.open(background_path).convert("RGBA")
    width, height = bg.size
    draw = ImageDraw.Draw(bg)

    diameter = int(avatar_diameter_ratio(len(entries)) * width)
    for entry in entries:
        cx = float(entry["x_ratio"]) * width
        cy = float(entry["y_ratio"]) * height

        avatar_path: Optional[str] = entry.get("avatar_path")
        sticker: Optional[Image.Image] = None
        if avatar_path and Path(avatar_path).is_file():
            try:
                sticker = _circular_avatar(Image.open(avatar_path), diameter)
            except Exception:
                sticker = None
        if sticker is None:
            sticker = _placeholder_avatar(str(entry.get("display_name") or "?"), diameter)

        bg.alpha_composite(sticker, (int(cx - diameter / 2), int(cy - diameter / 2)))
        _draw_name_label(
            draw, cx, cy + diameter / 2 + 6, str(entry.get("display_name") or "?"), diameter
        )

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="本地测试大合影合成")
    parser.add_argument("--background", required=True, help="背景图路径")
    parser.add_argument("--entries", required=True, help="JSON 文件或内联 JSON 数组")
    parser.add_argument("--output", default="photo_wall_export.png", help="输出 PNG 路径")
    args = parser.parse_args()

    try:
        entries = json.loads(args.entries)
    except json.JSONDecodeError:
        entries = json.loads(Path(args.entries).read_text(encoding="utf-8"))

    data = compose_photo(args.background, entries)
    Path(args.output).write_bytes(data)
    print(f"大合影已合成: {args.output} ({len(data)} bytes, {len(entries)} 条留影)")
