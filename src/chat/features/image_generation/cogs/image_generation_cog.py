import logging
import io
import discord
from discord import app_commands
from discord.ext import commands

from src.chat.config.chat_config import COMFYUI_CONFIG
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from ..services.comfyui_service import ComfyUIService

log = logging.getLogger(__name__)
IMAGE_GENERATION_COST = COMFYUI_CONFIG["IMAGE_GENERATION_COST"]


class ImageGenerationCog(commands.Cog):
    """处理图像生成相关命令的 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.comfyui_service = None
        if COMFYUI_CONFIG["ENABLED"]:
            log.info("ComfyUI 服务已启用，正在初始化...")
            self.comfyui_service = ComfyUIService(
                server_address=COMFYUI_CONFIG["SERVER_ADDRESS"],
                workflow_path=COMFYUI_CONFIG["WORKFLOW_PATH"],
            )
        else:
            log.warning("ComfyUI 服务已被禁用。")

    @app_commands.command(name="draw", description="使用 AI 生成一张图片")
    @app_commands.describe(
        positive_prompt="你想要在图片中看到什么（正面提示词）",
        negative_prompt="你不希望在图片中看到什么（负面提示词）",
        seed="随机种子，用于复现结果",
    )
    async def draw(
        self,
        interaction: discord.Interaction,
        positive_prompt: str,
        negative_prompt: str = "",
        seed: int = 12345,
    ):
        """/draw 命令的实现"""
        # 仅限私聊使用
        if interaction.guild is not None:
            await interaction.response.send_message(
                "此命令只能在与我的私聊中使用哦。", ephemeral=True
            )
            return

        # 检查服务是否已配置
        if not self.comfyui_service:
            await interaction.response.send_message(
                "抱歉，图像生成服务当前未配置。", ephemeral=True
            )
            return

        user_id = interaction.user.id

        # 1. 检查余额并扣费
        balance = await coin_service.get_balance(user_id)
        if balance < IMAGE_GENERATION_COST:
            await interaction.response.send_message(
                f"你的类脑币余额不足哦！生成图片需要 {IMAGE_GENERATION_COST}，你当前只有 {balance}。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        new_balance = await coin_service.remove_coins(
            user_id, IMAGE_GENERATION_COST, "AI 图像生成"
        )
        if new_balance is None:
            await interaction.followup.send("抱歉，扣费时发生错误，请稍后再试。")
            return

        try:
            # 2. 调用服务生成图片
            log.info(f"用户 {user_id} 请求生成图片，提示词: {positive_prompt}")
            image_data = await self.comfyui_service.generate_image(
                positive_prompt, negative_prompt, seed
            )

            # 3. 发送结果
            if image_data:
                file = discord.File(io.BytesIO(image_data), filename="image.png")
                await interaction.followup.send(
                    f"图片生成成功！消耗 {IMAGE_GENERATION_COST} 类脑币，剩余 {new_balance}。",
                    file=file,
                )
            else:
                # 生成失败，返还费用
                await coin_service.add_coins(
                    user_id, IMAGE_GENERATION_COST, "图像生成失败返还"
                )
                await interaction.followup.send(
                    "抱歉，图片生成失败，已返还你的类脑币。"
                )

        except Exception as e:
            log.error(f"处理 /draw 命令时发生未知错误: {e}")
            # 发生未知错误，返还费用
            await coin_service.add_coins(
                user_id, IMAGE_GENERATION_COST, "图像生成异常返还"
            )
            await interaction.followup.send(
                "处理你的请求时发生了一个意料之外的错误，已返还你的类脑币。"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ImageGenerationCog(bot))
