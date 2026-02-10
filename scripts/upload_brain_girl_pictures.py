# -*- coding: utf-8 -*-

"""
类脑娘吃东西图片上传脚本

功能：
1. 读取指定路径下的所有文件夹
2. 按文件夹把文件发送到 Discord 频道
3. 每九张图片一个消息，不足九张的也要处理
4. 抓取图片的 CDN 链接，处理掉 png 后的后缀
5. 按文件夹名称分类输出链接

使用方法：
    python scripts/upload_brain_girl_pictures.py <频道ID> <图片路径>

示例：
    python scripts/upload_brain_girl_pictures.py 123456789 "C:/Users/ECHO/Desktop/brain_girl_picture"
"""

import os
import sys
import asyncio
import argparse
import re
from pathlib import Path
from typing import Dict, List

import discord
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Discord Bot Token
_token = os.getenv("DISCORD_TOKEN")
if not _token:
    print("错误: 未找到 DISCORD_TOKEN 环境变量")
    sys.exit(1)
DISCORD_TOKEN: str = _token


# 图片扩展名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def get_image_files(folder_path: Path) -> List[Path]:
    """获取文件夹中的所有图片文件"""
    image_files = []
    for file in folder_path.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
            image_files.append(file)
    return sorted(image_files)


def remove_extension(url: str) -> str:
    """处理 URL，移除 .png 等后缀（包括 Discord CDN 的格式后缀）"""
    # Discord CDN URL 格式: https://cdn.discordapp.com/attachments/.../filename.png?size=...
    # 移除文件扩展名和查询参数
    # 先移除查询参数
    url = url.split("?")[0]
    # 移除文件扩展名
    url = re.sub(r"\.(png|jpg|jpeg|gif|webp|bmp)$", "", url, flags=re.IGNORECASE)
    return url


async def upload_images_to_discord(
    channel_id: int, base_path: str, batch_size: int = 9
) -> Dict[str, List[str]]:
    """
    上传图片到 Discord 频道

    Args:
        channel_id: Discord 频道 ID
        base_path: 图片文件夹根路径
        batch_size: 每批上传的图片数量（默认 9）

    Returns:
        按文件夹名称分类的 CDN 链接字典
    """
    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)

    # 存储结果的字典
    results: Dict[str, List[str]] = {}

    @client.event
    async def on_ready():
        print(f"已登录为 {client.user}")

        # 获取频道
        channel = client.get_channel(channel_id)
        if channel is None:
            print(f"错误: 无法找到频道 ID {channel_id}")
            await client.close()
            return

        if not isinstance(channel, discord.abc.Messageable):
            print(f"错误: 频道 {channel_id} 不是一个可发送消息的频道")
            await client.close()
            return

        base_folder = Path(base_path)
        if not base_folder.exists():
            print(f"错误: 路径 {base_path} 不存在")
            await client.close()
            return

        # 遍历所有子文件夹
        folders = [f for f in base_folder.iterdir() if f.is_dir()]
        folders.sort()

        print(f"\n找到 {len(folders)} 个文件夹")

        for folder in folders:
            folder_name = folder.name
            print(f"\n处理文件夹: {folder_name}")

            # 获取文件夹中的所有图片
            image_files = get_image_files(folder)

            if not image_files:
                print(f"  警告: 文件夹 {folder_name} 中没有图片")
                continue

            print(f"  找到 {len(image_files)} 张图片")

            # 分批上传图片
            results[folder_name] = []

            for i in range(0, len(image_files), batch_size):
                batch = image_files[i : i + batch_size]
                print(f"  上传第 {i // batch_size + 1} 批 ({len(batch)} 张图片)")

                # 准备文件列表
                files = []
                for img_file in batch:
                    try:
                        files.append(
                            discord.File(str(img_file), filename=img_file.name)
                        )
                    except Exception as e:
                        print(f"    警告: 无法读取文件 {img_file.name}: {e}")

                if not files:
                    continue

                try:
                    # 发送消息
                    message = await channel.send(files=files)

                    # 提取附件的 CDN 链接
                    for attachment in message.attachments:
                        cdn_url = attachment.url
                        clean_url = remove_extension(cdn_url)
                        results[folder_name].append(clean_url)
                        print(f"    已上传: {attachment.filename} -> {clean_url}")

                except discord.HTTPException as e:
                    print(f"    错误: 上传失败: {e}")
                except Exception as e:
                    print(f"    错误: 发生意外错误: {e}")

        # 完成后关闭客户端
        print("\n所有图片上传完成！")
        await client.close()

    # 启动客户端
    await client.start(DISCORD_TOKEN)

    return results


def print_results(results: Dict[str, List[str]]):
    """打印结果，格式化为迁移脚本期望的格式"""
    print("\n" + "=" * 60)
    print("上传结果 - 类脑娘吃东西图片 CDN 链接")
    print("=" * 60 + "\n")

    # 统计总数
    total_images = sum(len(urls) for urls in results.values())
    print(f"共 {len(results)} 个商品，{total_images} 张图片\n")

    # 输出格式：复制到 shop_config.py 的 BRAIN_GIRL_EATING_IMAGES
    print("=" * 60)
    print(
        "复制以下内容到 src/chat/config/shop_config.py 的 BRAIN_GIRL_EATING_IMAGES 字典"
    )
    print("=" * 60 + "\n")

    print("BRAIN_GIRL_EATING_IMAGES = {")
    for folder_name, urls in results.items():
        if urls:
            cg_url = urls[0]
            print(f'    "{folder_name}": "{cg_url}",  # 共 {len(urls)} 张图片')
    print("}\n")

    # 输出所有图片链接（备用）
    print("\n" + "=" * 60)
    print("所有图片链接（按商品分类）")
    print("=" * 60 + "\n")

    for folder_name, urls in results.items():
        print(f"# {folder_name} ({len(urls)} 张)")
        for url in urls:
            print(f'"{url}",')
        print()


def save_results_to_file(
    results: Dict[str, List[str]], output_path: str = "brain_girl_eating_images.txt"
):
    """保存结果到文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 类脑娘吃东西图片 CDN 链接\n")
        f.write(f"# 生成时间: {__import__('datetime').datetime.now()}\n")
        f.write(
            f"# 共 {len(results)} 个商品，{sum(len(urls) for urls in results.values())} 张图片\n\n"
        )

        # 复制到 shop_config.py 的格式
        f.write("=" * 60 + "\n")
        f.write(
            "复制以下内容到 src/chat/config/shop_config.py 的 BRAIN_GIRL_EATING_IMAGES 字典\n"
        )
        f.write("=" * 60 + "\n\n")

        f.write("BRAIN_GIRL_EATING_IMAGES = {\n")
        for folder_name, urls in results.items():
            if urls:
                cg_url = urls[0]
                f.write(f'    "{folder_name}": "{cg_url}",  # 共 {len(urls)} 张图片\n')
        f.write("}\n\n")

        for folder_name, urls in results.items():
            if urls:
                cg_url = urls[0]
                f.write(f'"{folder_name}": "{cg_url}",  # 共 {len(urls)} 张图片\n')

        # 输出所有图片链接（备用）
        f.write("\n" + "=" * 60 + "\n")
        f.write("所有图片链接（按商品分类）\n")
        f.write("=" * 60 + "\n\n")

        for folder_name, urls in results.items():
            f.write(f"# {folder_name} ({len(urls)} 张)\n")
            for url in urls:
                f.write(f'"{url}",\n')
            f.write("\n")

    print(f"\n结果已保存到: {output_path}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="上传类脑娘吃东西的图片到 Discord 频道"
    )
    parser.add_argument("channel_id", type=int, help="Discord 频道 ID")
    parser.add_argument(
        "path",
        type=str,
        help="图片文件夹路径",
        default=r"C:\Users\ECHO\Desktop\brain_girl_picture",
        nargs="?",
    )
    parser.add_argument(
        "--batch-size", type=int, default=9, help="每批上传的图片数量（默认: 9）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="brain_girl_eating_images.txt",
        help="输出文件路径（默认: brain_girl_eating_images.txt）",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("类脑娘吃东西图片上传脚本")
    print("=" * 60)
    print(f"频道 ID: {args.channel_id}")
    print(f"图片路径: {args.path}")
    print(f"每批数量: {args.batch_size}")
    print("=" * 60)

    # 上传图片
    results = await upload_images_to_discord(
        args.channel_id, args.path, args.batch_size
    )

    # 打印结果
    if results:
        print_results(results)
    else:
        print("\n没有上传任何图片")


if __name__ == "__main__":
    asyncio.run(main())
