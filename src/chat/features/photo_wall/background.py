# -*- coding: utf-8 -*-
"""中秋夜空占位背景生成器。

本模块用 Pillow 程序化绘制一张 1920x1080 的中秋夜景作为**占位背景**：
深蓝夜空渐变 + 满月与月晕 + 星星 + 云纹 + 底部山影。

如何替换为正式背景
------------------
直接用你自己的 1920x1080 (或同 16:9 比例) JPG 图片覆盖以下文件并重启服务即可：

    src/chat/features/photo_wall/assets/background.jpg

服务只在启动时检测到该文件**缺失**才会自动生成占位图，已有文件不会被覆盖。
建议导出/合成效果与网页预览一致，替换图请保持 16:9 比例。
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

WIDTH = 1920
HEIGHT = 1080

# 夜空渐变色：顶部深蓝 → 中部午夜蓝 → 地平线附近被月光照亮的蓝
SKY_TOP = (7, 12, 34)
SKY_MID = (15, 28, 60)
SKY_HORIZON = (34, 55, 92)

MOON_CENTER = (1450, 245)
MOON_RADIUS = 158
MOON_COLOR = (247, 240, 220)
MOON_SHADE = (222, 210, 182)


def _lerp(a: float, b: float, t: float) -> int:
    return int(round(a + (b - a) * t))


def _sky_gradient() -> Image.Image:
    """绘制垂直渐变的夜空底色。"""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    horizon_band = 0.62
    for y in range(HEIGHT):
        t = y / HEIGHT
        if t < horizon_band:
            c = tuple(_lerp(SKY_TOP[i], SKY_MID[i], t / horizon_band) for i in range(3))
        else:
            c = tuple(
                _lerp(SKY_MID[i], SKY_HORIZON[i], (t - horizon_band) / (1 - horizon_band))
                for i in range(3)
            )
        draw.line([(0, y), (WIDTH, y)], fill=c)
    return img.convert("RGBA")


def _add_stars(img: Image.Image, seed: int) -> None:
    """撒星星，上密下疏，避开月亮核心区。"""
    rnd = random.Random(seed)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    mx, my = MOON_CENTER
    for _ in range(260):
        x = rnd.uniform(0, WIDTH)
        y = rnd.uniform(0, HEIGHT * 0.78)
        dist = ((x - mx) ** 2 + (y - my) ** 2) ** 0.5
        if dist < MOON_RADIUS * 1.15:
            continue
        r = rnd.choice([0.6, 0.8, 1.0, 1.2, 1.5])
        alpha = rnd.randint(35, 200)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(232, 238, 255, alpha))
    # 少数亮星加十字闪光
    for _ in range(10):
        x = rnd.uniform(60, WIDTH - 60)
        y = rnd.uniform(40, HEIGHT * 0.5)
        dist = ((x - mx) ** 2 + (y - my) ** 2) ** 0.5
        if dist < MOON_RADIUS * 1.4:
            continue
        arm = rnd.uniform(5, 9)
        alpha = rnd.randint(120, 190)
        draw.line([(x - arm, y), (x + arm, y)], fill=(240, 244, 255, alpha), width=1)
        draw.line([(x, y - arm), (x, y + arm)], fill=(240, 244, 255, alpha), width=1)
    img.alpha_composite(overlay)


def _add_moon(img: Image.Image) -> None:
    """绘制满月：多层月晕 + 月面 + 淡淡的环形山阴影。"""
    mx, my = MOON_CENTER
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    # 月晕：由外向内逐渐变实的同心圆
    steps = 26
    outer = MOON_RADIUS * 2.9
    for i in range(steps):
        t = i / (steps - 1)
        r = outer + (MOON_RADIUS - outer) * t
        alpha = int(t * t * 90)
        draw.ellipse(
            [mx - r, my - r, mx + r, my + r],
            fill=(244, 232, 196, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(glow)

    moon_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    md = ImageDraw.Draw(moon_layer)
    md.ellipse(
        [mx - MOON_RADIUS, my - MOON_RADIUS, mx + MOON_RADIUS, my + MOON_RADIUS],
        fill=MOON_COLOR + (255,),
    )
    # 环形山：几个低对比度暗斑
    rnd = random.Random(42)
    craters = [
        (-0.35, -0.25, 0.22),
        (0.28, -0.38, 0.13),
        (0.15, 0.3, 0.18),
        (-0.15, 0.42, 0.10),
        (0.45, 0.12, 0.09),
        (-0.5, 0.18, 0.08),
    ]
    for fx, fy, fr in craters:
        cx = mx + fx * MOON_RADIUS * rnd.uniform(0.85, 1.1)
        cy = my + fy * MOON_RADIUS * rnd.uniform(0.85, 1.1)
        r = fr * MOON_RADIUS
        md.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=MOON_SHADE + (rnd.randint(36, 70),),
        )
    moon_layer = moon_layer.filter(ImageFilter.GaussianBlur(3))
    img.alpha_composite(moon_layer)


def _draw_cloud(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, alpha: int, color) -> None:
    """用重叠椭圆画一朵风格化的横长云。"""
    rnd = random.Random(int(cx * 131 + cy * 17 + scale * 7))
    lobes = [
        (0.00, 0.00, 0.55, 0.16),
        (-0.42, 0.10, 0.42, 0.12),
        (0.45, 0.08, 0.40, 0.13),
        (-0.15, -0.16, 0.38, 0.14),
        (0.20, -0.12, 0.34, 0.12),
        (0.62, -0.02, 0.28, 0.10),
        (-0.68, 0.02, 0.26, 0.09),
    ]
    for fx, fy, fw, fh in lobes:
        w = fw * scale * rnd.uniform(0.92, 1.08)
        h = fh * scale * rnd.uniform(0.85, 1.15)
        draw.ellipse(
            [cx + fx * scale - w, cy + fy * scale - h, cx + fx * scale + w, cy + fy * scale + h],
            fill=color + (alpha,),
        )


def _add_clouds(img: Image.Image, seed: int) -> None:
    """月周亮云 + 天空暗云，其中一朵从月亮下缘飘过。"""
    rnd = random.Random(seed)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    moonlit = (216, 226, 244)
    distant = (110, 130, 168)

    # 月亮下方飘过的亮云带
    _draw_cloud(draw, MOON_CENTER[0] - 60, MOON_CENTER[1] + MOON_RADIUS * 0.95, 560, 120, moonlit)
    _draw_cloud(draw, MOON_CENTER[0] + 260, MOON_CENTER[1] - MOON_RADIUS * 0.7, 380, 90, moonlit)

    # 远处暗云
    clouds = [
        (260, 200, 500, 46),
        (620, 380, 640, 38),
        (1500, 560, 700, 42),
        (980, 150, 420, 34),
        (120, 520, 460, 36),
    ]
    for cx, cy, scale, alpha in clouds:
        if rnd.random() < 0.35:
            continue
        _draw_cloud(draw, cx, cy, scale, alpha, distant)

    overlay = overlay.filter(ImageFilter.GaussianBlur(9))
    img.alpha_composite(overlay)


def _ridge_line(rnd: random.Random, base: float, amp: float, segments: int = 24) -> list:
    """生成一条带平滑起伏的山脊折线（从左边缘到右边缘）。"""
    points = []
    prev = base + rnd.uniform(-amp, amp) * 0.4
    for i in range(segments + 1):
        x = WIDTH * i / segments
        target = base + rnd.uniform(-amp, amp)
        y = (prev + target) / 2
        points.append((x, y))
        prev = y
    return points


def _add_mountains(img: Image.Image, seed: int) -> None:
    """底部两层山影：远山稍亮、近山最深，加轻微雾气过渡。"""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rnd = random.Random(seed)

    # 远山
    far_points = _ridge_line(rnd, HEIGHT * 0.80, HEIGHT * 0.10)
    far_poly = [(0, HEIGHT)] + far_points + [(WIDTH, HEIGHT)]
    draw.polygon(far_poly, fill=(21, 32, 60, 255))
    # 远山脊线的一丝月光
    draw.line(far_points, fill=(96, 118, 158, 110), width=2)

    # 山间雾带
    mist = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    md = ImageDraw.Draw(mist)
    md.rectangle([0, HEIGHT * 0.78, WIDTH, HEIGHT * 0.92], fill=(70, 92, 130, 34))
    mist = mist.filter(ImageFilter.GaussianBlur(30))
    img.alpha_composite(mist)

    # 近山
    near_points = _ridge_line(rnd, HEIGHT * 0.90, HEIGHT * 0.07, segments=18)
    near_poly = [(0, HEIGHT)] + near_points + [(WIDTH, HEIGHT)]
    draw.polygon(near_poly, fill=(8, 13, 32, 255))
    draw.line(near_points, fill=(52, 70, 108, 90), width=2)

    img.alpha_composite(overlay)


def generate_background(output_path: str) -> str:
    """生成占位背景并写入 output_path，返回该路径。"""
    img = _sky_gradient()
    _add_stars(img, seed=20260921)
    _add_moon(img)
    _add_clouds(img, seed=77)
    _add_mountains(img, seed=21)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, format="JPEG", quality=92)
    return str(path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成中秋照片墙占位背景")
    parser.add_argument("output", nargs="?", default="background.jpg", help="输出文件路径")
    args = parser.parse_args()
    print(f"背景已生成: {generate_background(args.output)}")
