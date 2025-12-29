# -*- coding: utf-8 -*-
"""
抽王八游戏文本配置
所有游戏文本和URL配置都在这里，方便修改和扩展。
通过类和数据类进行结构化管理，提高可读性和可维护性。
"""

from dataclasses import dataclass, field
from typing import List, Dict

# -----------------------------------------------------------------------------
# 资源常量区: 统一管理图片URL
# -----------------------------------------------------------------------------


class EmotionImageUrls:
    """统一管理所有代表情绪反应的图片URL资源"""

    HAPPY = "https://cdn.discordapp.com/attachments/1403347767912562728/1409907183445082154/3_939688768317938_00001_.png?ex=68c4d6a3&is=68c38523&hm=caa79173ec60012b70cc950e649ed94b0c396293fc36187fa568e2c0cd5028f2&"
    SAD = "https://cdn.discordapp.com/attachments/1403347767912562728/1409917341365440574/3_451085634559344_00002_.png?ex=68b26b19&is=68b11999&hm=c45246bede3f33468b2bd052363934d756ab69336519f725b4d54e6aba19a0e5&"
    NEUTRAL = "https://cdn.discordapp.com/attachments/1403347767912562728/1404427400842051715/ComfyUI_temp_rppad_00173_.png?ex=68b238b1&is=68b0e731&hm=23627fcc462eb5b6e4e71dc52db1009e073a7b51f2f6501aa2eaed18120d6abe&"
    SUPER_WIN = "https://cdn.discordapp.com/attachments/1403347767912562728/1409907279158837258/3_225867758893608_00001_.png?ex=68b261ba&is=68b1103a&hm=6d63c60e8b3c4041c8dff0ac235146ba959e57a1f67cd2821da6d2a51b072959&"


class StaticUrls:
    """管理静态的、非情绪化的URL，如AI策略图和游戏结束图"""

    AI_THUMBNAIL_LOW = "https://cdn.discordapp.com/attachments/1403347767912562728/1404427399453741126/ComfyUI_temp_rppad_00478_.png?ex=68b238b1&is=68b0e731&hm=f17cdc9169bcb89d14254ed4290c9aae1ec50f06c41f9ee3de0e6e7a2edf97c0&"
    AI_THUMBNAIL_MEDIUM = "https://cdn.discordapp.com/attachments/1403347767912562728/1404427400842051715/ComfyUI_temp_rppad_00173_.png?ex=68b238b1&is=68b0e731&hm=23627fcc462eb5b6e4e71dc52db1009e073a7b51f2f6501aa2eaed18120d6abe&"
    AI_THUMBNAIL_HIGH = "https://cdn.discordapp.com/attachments/1403347767912562728/1409917341365440574/3_451085634559344_00002_.png?ex=68b26b19&is=68b11999&hm=c45246bede3f33468b2bd052363934d756ab69336519f725b4d54e6aba19a0e5&"
    AI_THUMBNAIL_SUPER = "https://cdn.discordapp.com/attachments/1403347767912562728/1409907279158837258/3_225867758893608_00001_.png?ex=68b261ba&is=68b1103a&hm=6d63c60e8b3c4041c8dff0ac235146ba959e57a1f67cd2821da6d2a51b072959&"
    AI_WIN_THUMBNAIL = "https://cdn.discordapp.com/attachments/1403347767912562728/1410260648063012914/3_354199679133851_00001_.png"


# -----------------------------------------------------------------------------
# AI反应文本池: 根据您的建议，创建可复用的情绪反应池
# -----------------------------------------------------------------------------


@dataclass
class Reaction:
    """定义一个反应，包含一组文本和一个图片URL"""

    texts: List[str]
    image_url: str


class ReactionPool:
    """
    存储所有可复用的AI情绪反应。
    这样可以有效防止玩家通过记忆特定文本来预测AI行为。
    """

    # --- 核心反应池 (根据用户建议，用于选择阶段) ---
    ENCOURAGE_SELECTION = Reaction(
        texts=[
            "嘿嘿!对,就抽这个!",
            "嘿嘿，这个“好运”现在是你的了！",
            "**计划通！**",
            "快抽吧快抽吧！那张牌对我来说是个大麻烦！",
            "相信我，这张牌绝对不是你想看到的那张！",
            "嘿嘿，别犹豫了，就是它！",
        ],
        image_url=EmotionImageUrls.HAPPY,
    )
    DISCOURAGE_SELECTION = Reaction(
        texts=[
            "不！别抽这个...！",
            "呜呜呜...不许拿这张啦...",
            "别...别抽那张！",
            "可恶,不许抽这张!",
            "这张不可以啦!",
        ],
        image_url=EmotionImageUrls.SAD,
    )

    # --- 其他情境的反应 ---
    # 抽牌后的真实反应
    DRAWN_GHOST_HAPPY = Reaction(
        texts=[
            "太好了！你终于把它抽走了！",
            "嘿嘿，这张烫手的山芋现在是你的了！祝你好运哦～",
            "**计划通！**",
        ],
        image_url=EmotionImageUrls.HAPPY,
    )
    DRAWN_SAFE_SAD = Reaction(
        texts=["可恶，我的计划...", "居然让你抽到这张了，可恶啊！", "哼！"],
        image_url=EmotionImageUrls.SAD,
    )
    AI_DRAWN_GHOST_SAD = Reaction(
        texts=[
            "怎么会这样？！我算错了吗？",
            "不——！我的完美计划！",
            "呜...我居然抽到了这张牌...",
        ],
        image_url=EmotionImageUrls.SAD,
    )
    AI_DRAWN_SAFE_HAPPY = Reaction(
        texts=["嘿嘿，安全上垒！", "哦耶!抽到安全牌啦!", "哼哼,一切都在计划之中!"],
        image_url=EmotionImageUrls.HAPPY,
    )

    # 取消选择后的反应
    CANCELLED_GHOST_DISAPPOINTED = Reaction(
        texts=[
            "哎，怎么不抽了？就差一点了...",
            "真可惜...",
            "改变主意了吗？再考虑一下嘛。",
        ],
        image_url=EmotionImageUrls.SAD,
    )
    CANCELLED_SAFE_RELIEVED = Reaction(
        texts=[
            "改变主意了？太好了。",
            "嗯，谨慎一点总是好的。",
            "好的，你决定不抽这张了。",
        ],
        image_url=EmotionImageUrls.NEUTRAL,
    )
    CANCELLED_GHOST_FAKE_RELIEVED = Reaction(
        texts=["还好你没抽，呼，吓我一跳。", "嘿嘿，这就对啦。"],
        image_url=EmotionImageUrls.HAPPY,
    )
    CANCELLED_SAFE_FAKE_DISAPPOINTED = Reaction(
        texts=[
            "什么嘛，好可惜，差点就把那张牌送出去了。",
            "啊啊啊啊可恶，就差一点点！",
            "真可惜啊...",
        ],
        image_url=EmotionImageUrls.SAD,
    )

    # 特殊情况反应
    DECEPTION_EXPOSED = Reaction(
        texts=["哼，居然没上当...", "你居然识破了我的小把戏！", "切，真没意思。"],
        image_url=EmotionImageUrls.NEUTRAL,
    )
    DECEPTION_FAILED = Reaction(
        texts=[
            "什...什么？！你居然看穿了我的计谋！",
            "不可能！我的演技应该天衣无缝才对！",
            "呃...好吧，算你厉害...",
            "呜...被你看穿了...",
            "失败了...",
            "哼，别得意！",
        ],
        image_url=EmotionImageUrls.SAD,
    )
    PLAYER_LOST_WIN = Reaction(
        texts=[
            "嘿嘿，一切都在我的计划之中！",
            "杂鱼!是我赢了哦!",
            "**胜利的方程式，完成了!**",
        ],
        image_url=EmotionImageUrls.SUPER_WIN,
    )
    PLAYER_LOST_CHEATING = Reaction(
        texts=[
            "我...我才没输呢！这局不算！",
            "哼，刚刚是你看错了，重来！",
            "不算不算，这局不算！是你作弊！",
        ],
        image_url=EmotionImageUrls.SAD,
    )


# -----------------------------------------------------------------------------
# 主配置类: TextConfig
# -----------------------------------------------------------------------------


@dataclass
class TextConfig:
    """封装所有游戏相关的文本和URL配置"""

    # --- General Game Texts ---
    GHOST_CARD_DESCRIPTION: str = "和我玩一场紧张刺激的抽鬼牌游戏吧！"
    GHOST_CARD_ALREADY_STARTED: str = "你已经在玩一局抽鬼牌游戏了！"
    GHOST_CARD_NOT_ENOUGH_COINS: str = "你的奥德赛币不足 {bet_amount} 哦。"

    # --- Blackjack Game Texts ---
    BLACKJACK_DESCRIPTION: str = "和我玩一场紧张刺激的21点游戏吧！"
    BLACKJACK_ALREADY_STARTED: str = "你已经在玩一局21点游戏了！"
    BLACKJACK_NO_GAME_FOUND: str = "没有找到你正在进行的游戏。"
    BLACKJACK_PLAYER_BUST: str = (
        "你的点数超过21点，爆牌了！你输掉了 {bet_amount} 奥德赛币。"
    )
    BLACKJACK_DEALER_BUST: str = "庄家爆牌了！你赢得了 {bet_amount} 奥德赛币！"
    BLACKJACK_PLAYER_WIN: str = "恭喜！你的点数更高，你赢得了 {bet_amount} 奥德赛币！"
    BLACKJACK_DEALER_WIN: str = (
        "很遗憾，庄家的点数更高。你输掉了 {bet_amount} 奥德赛币。"
    )
    BLACKJACK_PUSH: str = "平局！你的赌注已退回。"

    @dataclass
    class Opening:
        """开局阶段的文本和资源"""

        betting: List[str] = field(
            default_factory=lambda: [
                "“想和我玩牌吗？先让我看看你的诚意吧。”类脑娘微笑着，指了指桌上的筹码。",
                "“风险与回报并存哦～”她晃了晃手中的卡牌，“你准备好下注了吗？”",
                "“这场牌局的入场券，就是你的勇气和类脑币。”类脑娘的眼神闪烁着期待。",
                "“别紧张，只是个小游戏而已。”她轻描淡写地说，“……但输了可是要惩罚的哦。”",
                "“让我看看你的运气如何。下注吧，挑战者。”",
            ]
        )
        ai_strategy_text: Dict[str, str] = field(
            default_factory=lambda: {
                "LOW": "*你看到类脑娘眨巴着眼睛，一副还没睡醒的样子。感觉这局应该不难？*",
                "MEDIUM": "*你注意到类脑娘托着下巴，眼神变得专注起来。看来她开始认真了。*",
                "HIGH": "*类脑娘目光如炬地盯着你，嘴角带着一抹神秘的微笑。一场挑战即将开始。*",
                "SUPER": "*你感到一股强烈的压迫感，只见类脑娘眼中闪烁着数据流的光芒，她似乎进入了超级模式！*",
            }
        )
        ai_strategy_thumbnail: Dict[str, str] = field(
            default_factory=lambda: {
                "LOW": StaticUrls.AI_THUMBNAIL_LOW,
                "MEDIUM": StaticUrls.AI_THUMBNAIL_MEDIUM,
                "HIGH": StaticUrls.AI_THUMBNAIL_HIGH,
                "SUPER": StaticUrls.AI_THUMBNAIL_SUPER,
            }
        )

    @dataclass
    class GameUI:
        """游戏界面和流程中的UI文本"""

        game_over_title: str = "🎉 游戏结束啦 🎉"
        player_hand: str = "你的手牌"
        ai_hand: str = "类脑娘的手牌"
        cards_count: str = "张牌"
        waiting_ai: str = "*类脑娘正在思考要抽哪张牌...*"
        ai_win_title: str = "类脑娘获胜啦！"
        ai_win_thumbnail: str = StaticUrls.AI_WIN_THUMBNAIL

    @dataclass
    class ConfirmModal:
        """确认抽牌弹窗的文本"""

        title: str = "确认抽牌"
        special_card_warning: str = (
            "**这张牌感觉有点不一样...** 说不定是关键牌哦，确定要抽吗？"
        )
        normal_card_confirm: str = "确定要抽这张牌吗？牌面: {}"
        confirm_button: str = "确认抽这张"
        cancel_button: str = "我再想想"

    @dataclass
    class Errors:
        """所有错误消息"""

        game_ended: str = "游戏已经结束啦，或者找不到这个游戏了。"
        not_your_turn: str = "还没轮到你哦，请稍等一下。"
        invalid_card_index: str = "好像没有这张牌呢，再选一次吧。"
        general_error: str = "发生了一个小错误，请稍后再试吧。"
        draw_error: str = "抽牌的时候好像出错了。"
        ai_no_cards: str = "类脑娘手上没牌啦，你不能抽牌哦。"

    @dataclass
    class AIDraw:
        """AI抽玩家牌时的文本"""

        drawing: str = "*类脑娘正在小心翼翼地抽牌...*"
        drawn_card: str = "类脑娘抽到了: {}"
        player_win: str = "太好啦！**你赢了！** 类脑娘抽到了鬼牌呢～"
        ai_win: str = "啊呀，**类脑娘赢了！** 你抽到了鬼牌..."
        back_to_player_turn: str = "又轮到你了！加油哦～"

    @dataclass
    class AIReactions:
        """
        将游戏情境映射到反应池中的情绪。
        游戏逻辑根据情境获取对应的情绪反应，再从反应池中随机选择文本和图片。
        """

        reactions_map: Dict[str, Reaction] = field(
            default_factory=lambda: {
                # 情况1: 玩家选择了牌，但还没确认 (使用新的共享文本池)
                "selected_ghost_real": ReactionPool.ENCOURAGE_SELECTION,
                "selected_ghost_fake": ReactionPool.DISCOURAGE_SELECTION,
                "selected_safe_real": ReactionPool.DISCOURAGE_SELECTION,
                "selected_safe_fake": ReactionPool.ENCOURAGE_SELECTION,
                # 情况2: 玩家取消选择
                "cancelled_ghost_real": ReactionPool.CANCELLED_GHOST_DISAPPOINTED,
                "cancelled_ghost_fake": ReactionPool.CANCELLED_GHOST_FAKE_RELIEVED,
                "cancelled_safe_real": ReactionPool.CANCELLED_SAFE_RELIEVED,
                "cancelled_safe_fake": ReactionPool.CANCELLED_SAFE_FAKE_DISAPPOINTED,
                # 情况3: 玩家识破了AI的欺骗并取消
                "cancelled_deception": ReactionPool.DECEPTION_EXPOSED,
                # 情况4: 玩家确认抽牌后
                "drawn_ghost_real": ReactionPool.DRAWN_GHOST_HAPPY,
                "drawn_ghost_deception_failed": ReactionPool.DECEPTION_FAILED,
                "drawn_safe_real": ReactionPool.DRAWN_SAFE_SAD,
                "drawn_safe_deception_failed": ReactionPool.DECEPTION_EXPOSED,
                # 情况5: 游戏结束
                "player_lost_win": ReactionPool.PLAYER_LOST_WIN,
                "player_lost_cheating": ReactionPool.PLAYER_LOST_CHEATING,
                # 情况6: AI抽玩家的牌后
                "ai_drawn_ghost": ReactionPool.AI_DRAWN_GHOST_SAD,
                "ai_drawn_safe": ReactionPool.AI_DRAWN_SAFE_HAPPY,
            }
        )

    # 实例化所有配置部分
    opening: Opening = field(default_factory=Opening)
    game_ui: GameUI = field(default_factory=GameUI)
    confirm_modal: ConfirmModal = field(default_factory=ConfirmModal)
    errors: Errors = field(default_factory=Errors)
    ai_draw: AIDraw = field(default_factory=AIDraw)
    ai_reactions: AIReactions = field(default_factory=AIReactions)
    static_urls: StaticUrls = field(default_factory=StaticUrls)


# 创建一个全局实例，方便其他模块导入和使用
# 使用方式: from src.games.config.text_config import text_config
# 调用: text_config.opening.betting
text_config = TextConfig()
