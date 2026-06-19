# -*- coding: utf-8 -*-
"""一次性脚本：把根目录 food/ gifts/ 的大图压成缩略图 webp，放到画廊目录。"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOOD_SRC = os.path.join(ROOT, "food")
GIFT_SRC = os.path.join(ROOT, "gifts")
DEST = os.path.join(ROOT, "src", "diary", "public", "assets", "gallery")

MAX_SIZE = 420  # 缩略图最大边长（展示仅 112px，420 足够 retina）
QUALITY = 82

# 文件名 -> 商品名（展示名）
FOOD_MAP = {
    "chocolate.png": "巧克力",
    "cookie.png": "曲奇饼干",
    "lolipop.png": "棒棒糖",
    "chips.png": "薯片",
    "mianhuatang.png": "棉花糖",
    "milktea.png": "珍珠奶茶",
    "zhaji.png": "疯狂星期四",
    "hanbao.png": "汉堡",
    "Standwitch.png": "三明治",
    "sushi.png": "寿司拼盘",
    "hotpot.png": "火锅套餐",
    "niupai.png": "牛排",
    "bafei.png": "芭菲",
}

GIFT_MAP = {
    "向日葵.png": "向日葵",
    "发卡.png": "小发夹",
    "烟花棒.png": "仙女棒",
    "围巾.png": "围巾",
    "软呢帽(害羞).png": "软呢帽",
    "八音盒.png": "八音盒",
    "星空灯.png": "星空投影灯",
    "教科书(慌张).png": "教科书",
    "滑板(摔哭了).png": "滑板",
    "万圣节.png": "万圣节",
    "连衣裙.png": "连衣裙",
    "鱼竿.png": "鱼竿",
}


def convert(src_dir: str, mapping: dict, subdir: str):
    out_dir = os.path.join(DEST, subdir)
    os.makedirs(out_dir, exist_ok=True)
    for fname, item in mapping.items():
        sp = os.path.join(src_dir, fname)
        if not os.path.exists(sp):
            print(f"  MISS: {fname}")
            continue
        op = os.path.join(out_dir, f"{item}.webp")
        with Image.open(sp) as im:
            im = im.convert("RGBA")
            im.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            # webp 不支持 RGBA 透明时用白底合成
            bg = Image.new("RGBA", im.size, (255, 252, 244, 255))
            bg.alpha_composite(im)
            bg.convert("RGB").save(op, "WEBP", quality=QUALITY, method=6)
        print(f"  OK: {fname} -> {item}.webp ({os.path.getsize(op)//1024} KB)")


print("=== food ===")
convert(FOOD_SRC, FOOD_MAP, "food")
print("=== gift ===")
convert(GIFT_SRC, GIFT_MAP, "gift")
print("done")
