import asyncio
import os
from src.chat.features.tarot.services.tarot_service import TarotService


async def main():
    """
    通过执行一次占卜并保存结果图片来测试 TarotService。
    """
    print("--- 开始塔罗牌服务测试 ---")

    # 创建服务实例
    tarot_service = TarotService()

    # 确保输出目录存在
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "tarot_spread.png")

    print("正在进行一次三牌占卜...")
    # 调用服务以获取图片数据和卡牌信息
    image_data, cards = await tarot_service.perform_reading(
        question="这是一个测试问题", spread_type="three_card"
    )

    if image_data:
        print(f"已收到图片数据 ({len(image_data)} 字节)。")
        try:
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"已成功将牌阵图片保存至: {output_path}")
        except Exception as e:
            print(f"保存图片时出错: {e}")
    else:
        print("错误: 未生成图片数据。请检查服务日志以获取详细信息。")
        print("请确保 'assets/tarot_cards/' 目录下存在卡牌图片。")

    if cards:
        print("\n抽到的卡牌:")
        for card in cards:
            key = "meaning_up" if card["orientation"] == "upright" else "meaning_rev"
            keywords = card[key].split(", ")
            print(
                f"- {card['name']} ({card['orientation']}), "
                f"关键词: {keywords[0]}, {keywords[1]}"
            )
    else:
        print("错误: 未返回卡牌数据。")

    print("\n--- 塔罗牌服务测试结束 ---")


if __name__ == "__main__":
    # 从命令行运行此异步脚本
    asyncio.run(main())
