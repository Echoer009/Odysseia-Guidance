import discord
import logging

log = logging.getLogger(__name__)

PROFILE_MODAL_CUSTOM_ID = "personal_profile_edit_modal"


class ProfileEditModal(discord.ui.Modal, title="创建你的个人记忆档案"):
    """
    一个模态框，用于让用户创建或编辑他们的个人档案。
    """

    def __init__(self, custom_id: str = PROFILE_MODAL_CUSTOM_ID):
        super().__init__(custom_id=custom_id)

    # 定义档案字段
    name = discord.ui.TextInput(
        label="你的称呼",
        placeholder="类脑娘应该如何称呼你？例如：阿P",
        style=discord.TextStyle.short,
        required=True,
        max_length=50,
        custom_id="name",
    )

    personality = discord.ui.TextInput(
        label="你的性格特点",
        placeholder="简单描述一下你的性格。例如：乐观、有点内向、喜欢开玩笑",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300,
        custom_id="personality",
    )

    background = discord.ui.TextInput(
        label="你的背景故事或设定",
        placeholder="可以是你真实的经历摘要，也可以是你希望扮演的虚拟角色设定。例如：一个来自未来，热爱探索的旅行者。",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        custom_id="background",
    )

    preferences = discord.ui.TextInput(
        label="你的偏好或禁忌",
        placeholder="有什么特别喜欢或不喜欢的话题吗？例如：喜欢聊科幻电影，不喜欢剧透。",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
        custom_id="preferences",
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 提交逻辑将由Cog处理，这里不需要发送任何响应
        # 实际的数据保存操作会通过调用服务层方法在Cog中完成
        try:
            # 不需要在这里调用 defer，因为 Cog 中的 on_modal_submit 会处理交互响应
            log.info(f"用户 {interaction.user.id} 提交了个人档案。")

        except Exception as e:
            log.error(f"处理个人档案提交时发生错误: {e}", exc_info=True)
            # 注意：在这种情况下，Cog 中的 on_modal_submit 可能已经调用了 defer，
            # 所以我们不能直接发送消息。这个错误会被 Cog 中的 on_modal_submit 捕获并处理。

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        log.error(f"个人档案模态框发生错误: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "发生了一个未知的错误，请联系管理员。", ephemeral=True
            )


class ProfileEditButton(discord.ui.Button):
    """一个触发个人档案编辑模态框的按钮"""

    def __init__(self):
        super().__init__(
            label="创建/编辑我的档案",
            style=discord.ButtonStyle.primary,
            emoji="📝",
            custom_id="profile_edit_button",
        )

    async def callback(self, interaction: discord.Interaction):
        modal = ProfileEditModal()
        await interaction.response.send_modal(modal)


class ProfileEditView(discord.ui.View):
    """包含编辑档案按钮的视图"""

    def __init__(self, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(ProfileEditButton())
