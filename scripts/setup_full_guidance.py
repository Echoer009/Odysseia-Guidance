# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import argparse
import re
import logging
from typing import Dict, Any, Optional

import discord
import yaml
from dotenv import load_dotenv

# --- 路径设置 ---
# 将 src 目录添加到 Python 路径中，以便导入项目模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 在导入我们自己的模块之前加载环境变量
load_dotenv()

# --- 模块导入 ---
from src.guidance.utils.database import guidance_db_manager as db_manager

# 导入解析器
from scripts.parsers.persona_template_parser import parse_persona_templates
from src.guidance.services.deployment_service import deploy_all_panels

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# --- 全局变量 ---
# 使用环境变量中的 Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    raise ValueError("错误：请在 .env 文件中设置 BOT_TOKEN 或 DISCORD_TOKEN")

# --- Discord Bot 客户端 ---
# 需要 intents 来获取服务器成员和身份组信息
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = discord.Client(intents=intents)

# --- 核心功能 ---


def parse_channel_messages(file_path: str) -> Dict[str, Any]:
    """
    解析 markdown 文件，提取所有消息模板。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    templates = {}
    # 修正了正则表达式，添加了 `\)` 来正确匹配末尾的括号
    template_pattern = re.compile(
        r"###\s*.*?`((?:channel|forum|thread)\(\d+\))`\s*\)(.+?)(?=\n###|\Z)", re.S
    )

    def _parse_single_message_block(msg_content):
        if not msg_content:
            return None
        msg_data = {}

        def extract_field(pattern, text):
            match = re.search(pattern, text, re.S)
            if match:
                return match.group(1).strip()
            return None

        msg_data["title"] = extract_field(
            r"\s*\*\s*\*Embed 标题:\*\*\s*`(.+?)`", msg_content
        )

        description_raw = extract_field(
            r"\s*\*\s*\*Embed 描述:\*\*\s*(.+?)(?=\n\s*\*|\Z)", msg_content
        )
        if description_raw:
            # 移除 markdown 引用符号
            cleaned_description = (
                description_raw.strip().replace("> ", "").replace(">", "")
            )
            # 处理转义的换行符
            cleaned_description = cleaned_description.replace("\\n", "\n")
            msg_data["description"] = cleaned_description

        msg_data["image_url"] = extract_field(
            r"\s*\*\s*\*Embed 大图 URL:\*\*\s*`(.+?)`", msg_content
        )
        msg_data["thumbnail_url"] = extract_field(
            r"\s*\*\s*\*Embed 缩略图 URL:\*\*\s*`(.+?)`", msg_content
        )
        msg_data["footer_text"] = extract_field(
            r"\s*\*\s*\*Embed 页脚:\*\*\s*`(.+?)`", msg_content
        )

        # 移除值为 None 或空字符串的键
        msg_data = {k: v for k, v in msg_data.items() if v is not None and v != ""}

        return msg_data if msg_data else None

    for match in template_pattern.finditer(content):
        template_name, block_content = match.groups()

        parsed_data = {"permanent_data": [], "temporary_data": []}

        # 提取永久消息内容
        perm_match = re.search(
            r"\*\s*\*\*永久消息面板\s*\(.+?\)\*\*(.+?)(?=\n\s*\*\s*\*\*临时消息|\Z)",
            block_content,
            re.S,
        )
        if perm_match:
            perm_content = perm_match.group(1)
            perm_message = _parse_single_message_block(perm_content)
            if perm_message:
                parsed_data["permanent_data"].append(perm_message)

        # 提取临时消息列表内容 - 同时匹配"临时消息列表"和"临时消息"
        temp_list_match = re.search(
            r"\*\s*\*\*临时消息(?:列表)?\s*\(.+?\)\*\*(.+)", block_content, re.S
        )
        if temp_list_match:
            temp_list_content = temp_list_match.group(1)
            # 寻找所有以 '*' 开头的消息块（每个消息块以 "*   -" 开头）
            message_blocks = re.split(r"\n\s*\*\s*\-", temp_list_content)
            for block in message_blocks:
                if block.strip():
                    # 清理每个块开头的列表标记和缩进
                    cleaned_block = re.sub(r"^\s*\*\s*", "", block).strip()
                    if cleaned_block:
                        temp_message = _parse_single_message_block(cleaned_block)
                        if temp_message:
                            parsed_data["temporary_data"].append(temp_message)

        if parsed_data["permanent_data"] or parsed_data["temporary_data"]:
            templates[template_name] = parsed_data

    return templates


async def clear_existing_config(guild_id: int):
    """在写入新配置前，清空指定服务器的所有旧引导配置。"""
    log.info(f"--- 正在清空服务器 {guild_id} 的旧配置 ---")

    # 1. 删除所有标签 (这将通过 ON DELETE CASCADE 级联删除所有关联的路径)
    tags = await db_manager.get_all_tags(guild_id)
    for tag in tags:
        await db_manager.delete_tag(tag["tag_id"])
    log.info(f"  - 已删除 {len(tags)} 个标签及其关联路径。")

    # 2. 删除所有频道专属消息
    channel_messages = await db_manager.get_all_channel_messages(guild_id)
    for msg in channel_messages:
        await db_manager.remove_channel_message(msg["channel_id"])
    log.info(f"  - 已删除 {len(channel_messages)} 条频道专属消息配置。")

    # 3. 删除所有消息模板
    deleted_templates = await db_manager.delete_all_message_templates(guild_id)
    log.info(f"  - 已删除 {deleted_templates} 个消息模板。")

    # 4. 清空触发身份组
    await db_manager.set_trigger_roles(guild_id, [])
    log.info("  - 已清空触发身份组。")

    # 5. 清空服务器基础配置 (buffer_role_id, verified_role_id, default_tag_id)
    await db_manager.set_stage_role(guild_id, "buffer", None)
    await db_manager.set_stage_role(guild_id, "verified", None)
    await db_manager.set_default_tag(guild_id, None)
    log.info("  - 已重置服务器基础配置。")

    log.info("--- ✅ 清空完成 ---")


async def clear_deployed_panels(guild: discord.Guild):
    """Deletes all previously deployed permanent panels from their channels."""
    log.info("--- 正在删除旧的永久消息面板 ---")
    all_configs = await db_manager.get_all_channel_messages(guild.id)
    deployed_panels = [c for c in all_configs if c.get("deployed_message_id")]

    if not deployed_panels:
        log.info("  - 未找到任何已部署的旧面板。")
        return

    deleted_count = 0
    for config in deployed_panels:
        channel_id = config["channel_id"]
        message_id = config["deployed_message_id"]
        channel = guild.get_channel_or_thread(channel_id)

        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                log.warning(
                    f"  - ⚠️ 警告：找不到频道 ID {channel_id}，无法删除消息 {message_id}。"
                )
                continue

        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
            log.info(
                f"  - 已删除位于 #{channel.name} 的旧面板消息 (ID: {message_id})。"
            )
            deleted_count += 1
        except (discord.NotFound, discord.Forbidden):
            log.info(
                f"  - ℹ️ 信息：在 #{channel.name} 中找不到消息 ID {message_id} 或无权删除，可能已被手动删除。"
            )
        except Exception as e:
            log.error(f"  - ❌ 错误：删除消息 {message_id} 时发生错误: {e}")

    log.info(f"--- ✅ 旧面板删除完成：共删除 {deleted_count} 个。 ---")


async def setup_guidance(args: argparse.Namespace):
    """为指定的服务器部署完整的引导配置。"""
    guild_id = args.guild_id
    guild = bot.get_guild(guild_id)
    if not guild:
        log.error(f"❌ 错误：找不到服务器 ID: {guild_id}，或者机器人不在该服务器中。")
        return

    log.info(f"🚀 开始为服务器 '{guild.name}' (ID: {guild_id}) 部署引导配置...")

    # --- 1. 加载所有配置文件 ---
    log.info("--- 1. 正在加载配置文件 ---")
    script_dir = os.path.dirname(__file__)

    try:
        config_path = os.path.join(script_dir, "..", args.config_file)
        with open(config_path, "r", encoding="utf-8") as f:
            logic_config = yaml.safe_load(f)
        log.info(f"  - ✅ `{os.path.basename(config_path)}` (逻辑配置) 加载成功。")

        channel_messages = parse_channel_messages(
            os.path.join(script_dir, "..", "docs", "channel_message.md")
        )
        log.info(
            f"  - ✅ `channel_message.md` (频道消息) 加载成功，解析出 {len(channel_messages)} 个地点的配置。"
        )

        persona_templates = parse_persona_templates(
            os.path.join(script_dir, "..", "docs", "persona_templates.md")
        )
        log.info(
            f"  - ✅ `persona_templates.md` (私信模板) 加载成功，解析出 {len(persona_templates)} 个模板。"
        )
    except FileNotFoundError as e:
        log.error(f"❌ 错误：配置文件未找到: {e}")
        return
    except Exception as e:
        log.error(f"❌ 错误：解析配置文件时出错: {e}")
        return

    # --- 2. 清空旧配置 ---
    # 如果计划部署新面板，则先删除所有旧的已部署面板
    if args.deploy_panels:
        await clear_deployed_panels(guild)

    await clear_existing_config(guild_id)

    # --- 3. 写入新配置 ---
    log.info("--- 2. 正在写入新配置到数据库 ---")

    # 辅助函数：通过名称查找ID
    def get_role_id_by_name(name: str) -> Optional[int]:
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            log.warning(
                f"  ⚠️  警告：在服务器 '{guild.name}' 中找不到名为 '{name}' 的身份组。"
            )
        return role.id if role else None

    # 3.1 写入服务器基础配置
    server_config = logic_config.get("server_config", {})
    buffer_role_name = server_config.get("buffer_role_name")
    verified_role_name = server_config.get("verified_role_name")

    if buffer_role_name:
        buffer_role_id = get_role_id_by_name(buffer_role_name)
        if buffer_role_id:
            await db_manager.set_stage_role(guild_id, "buffer", buffer_role_id)
            log.info(
                f"  - 设置缓冲区身份组为: '{buffer_role_name}' (ID: {buffer_role_id})"
            )

    if verified_role_name:
        verified_role_id = get_role_id_by_name(verified_role_name)
        if verified_role_id:
            await db_manager.set_stage_role(guild_id, "verified", verified_role_id)
            log.info(
                f"  - 设置已验证身份组为: '{verified_role_name}' (ID: {verified_role_id})"
            )

    # 3.2 写入标签，并设置默认标签
    tags_config = logic_config.get("tags", [])
    default_tag_name = None
    created_tags_map = {}  # 用于存储 name -> id 的映射

    # --- 性能优化：一次性并行验证所有地点ID ---
    all_location_ids = set()
    for tag_config in tags_config:
        all_location_ids.update(tag_config.get("channels", []))
        all_location_ids.update(tag_config.get("threads", []))

    log.info(f"  - 发现 {len(all_location_ids)} 个唯一的地点ID，开始并行验证...")
    validation_tasks = [guild.fetch_channel(loc_id) for loc_id in all_location_ids]
    results = await asyncio.gather(*validation_tasks, return_exceptions=True)

    validated_locations = {}
    for i, result in enumerate(results):
        # 使用 all_location_ids 的有序列表来确保 loc_id 和 result 对应
        loc_id = list(all_location_ids)[i]
        if isinstance(result, (discord.abc.GuildChannel, discord.Thread)):
            validated_locations[loc_id] = result
        else:
            # 对于无效的ID，记录警告
            log.warning(f"  - ⚠️  验证失败：找不到 ID 为 {loc_id} 的地点或权限不足。")
    log.info(f"  - ✅ 验证完成，成功获取 {len(validated_locations)} 个地点的信息。")
    # --- 性能优化结束 ---

    for tag_config in tags_config:
        tag_name = tag_config["name"]
        tag_id = await db_manager.add_tag(
            guild_id, tag_name, tag_config.get("description")
        )
        created_tags_map[tag_name] = tag_id
        log.info(f"  - 创建标签: '{tag_name}' (ID: {tag_id})")

        if tag_config.get("is_default", False):
            default_tag_name = tag_name

        paths_data = []

        # 处理普通频道
        for location_id in tag_config.get("channels", []):
            channel = validated_locations.get(location_id)
            if channel:
                if not isinstance(channel, discord.Thread):
                    paths_data.append(
                        {
                            "location_id": location_id,
                            "location_type": "channel",
                            "message": None,
                        }
                    )
                else:
                    log.warning(
                        f"    - ⚠️  警告：ID {location_id} ('{channel.name}') 是一个帖子，但被配置在了 'channels' 列表下。"
                    )
            # 如果ID无效，之前已打印过警告，此处不再重复

        # 处理帖子
        for location_id in tag_config.get("threads", []):
            thread = validated_locations.get(location_id)
            if thread:
                if isinstance(thread, discord.Thread):
                    paths_data.append(
                        {
                            "location_id": location_id,
                            "location_type": "thread",
                            "message": None,
                        }
                    )
                else:
                    log.warning(
                        f"    - ⚠️  警告：ID {location_id} ('{thread.name}') 不是一个帖子，但被配置在了 'threads' 列表下。"
                    )
            # 如果ID无效，之前已打印过警告，此处不再重复

        if paths_data:
            await db_manager.set_path_for_tag(tag_id, paths_data)
            log.info(
                f"    - ✅ 成功为标签 '{tag_name}' 创建了包含 {len(paths_data)} 个频道/帖子的路径。"
            )

    # 在所有标签创建完毕后，设置默认标签
    if default_tag_name and default_tag_name in created_tags_map:
        default_tag_id = created_tags_map[default_tag_name]
        await db_manager.set_default_tag(guild_id, default_tag_id)
        log.info(f"  - 设置默认标签为: '{default_tag_name}' (ID: {default_tag_id})")

    # 3.2 写入路径和触发身份组
    paths_config = logic_config.get("paths", [])
    all_trigger_roles = []

    for path_config in paths_config:
        path_name = path_config["name"]
        trigger_role_name = path_config.get("trigger_role")

        if trigger_role_name:
            trigger_role_id = get_role_id_by_name(trigger_role_name)
            if trigger_role_id:
                # 构建 path_steps 数据
                path_steps = []
                for step in path_config.get("steps", []):
                    location_id = step.get("channel_id")
                    if location_id:
                        # 验证频道或帖子是否存在
                        if guild.get_channel(location_id) or guild.get_thread(
                            location_id
                        ):
                            path_steps.append(
                                {
                                    "location_id": location_id,
                                    "persona_template": step.get("persona_template"),
                                    # 可以根据需要添加其他步骤相关的配置
                                }
                            )
                        else:
                            log.warning(
                                f"    ⚠️  警告：在路径 '{path_name}' 中，找不到 ID 为 '{location_id}' 的频道或帖子。"
                            )
                    else:
                        log.warning(
                            f"    ⚠️  警告：路径 '{path_name}' 的一个步骤缺少 'channel_id'。"
                        )

                # 将路径数据和触发身份组ID存入数据库
                await db_manager.add_or_update_path(
                    guild_id, path_name, trigger_role_id, path_steps
                )
                all_trigger_roles.append(trigger_role_id)
                log.info(
                    f"  - 写入路径 '{path_name}'，由身份组 '{trigger_role_name}' (ID: {trigger_role_id}) 触发，包含 {len(path_steps)} 个步骤。"
                )

    # 更新服务器的总触发身份组列表
    if all_trigger_roles:
        await db_manager.set_trigger_roles(guild_id, all_trigger_roles)
        log.info(f"  - 更新服务器的触发身份组列表，共 {len(all_trigger_roles)} 个。")

    # 3.3 写入私信模板
    for template_name, template_data in persona_templates.items():
        await db_manager.set_message_template(guild_id, template_name, template_data)
    log.info(f"  - 写入了 {len(persona_templates)} 个私信模板。")

    # 3.4 写入频道专属消息
    for location_identifier, message_data in channel_messages.items():
        # location_identifier 格式为 "type(id)"
        match = re.match(r"(channel|thread)\((\d+)\)", location_identifier)
        if match:
            loc_type, loc_id_str = match.groups()
            loc_id = int(loc_id_str)
            await db_manager.set_channel_message(
                guild_id=guild_id,
                channel_id=loc_id,
                permanent_data=message_data.get("permanent_data", [{}])[0]
                if message_data.get("permanent_data")
                else {},
                temporary_data=message_data.get("temporary_data", []),
            )
    log.info(f"  - 写入了 {len(channel_messages)} 个地点的专属消息。")

    # --- 4. 部署永久消息面板 (可选) ---
    if args.deploy_panels:
        log.info("--- 3. 正在部署或更新永久消息面板 ---")
        success_count, fail_count, report_lines = await deploy_all_panels(guild)
        log.info("--- 部署报告 ---")
        for line in report_lines:
            # 移除 markdown 链接格式，简化输出
            cleaned_line = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", line)
            log.info(f"  {cleaned_line}")
        log.info(f"--- ✅ 部署完成：{success_count} 个成功, {fail_count} 个失败 ---")
        log.info("🎉 部署完成！所有配置已成功写入数据库并部署。")
    else:
        log.info(
            "🎉 部署完成！所有配置已成功写入数据库。使用 --deploy-panels 参数来部署消息面板。"
        )


@bot.event
async def on_ready():
    """当机器人准备好后执行。"""
    log.info(f"机器人已以 {bot.user} 的身份登录。")

    # 从命令行参数获取 guild_id
    parser = argparse.ArgumentParser(description="为指定服务器部署完整的新人引导配置。")
    parser.add_argument(
        "--guild-id", type=int, required=True, help="要部署配置的目标服务器 ID。"
    )
    parser.add_argument(
        "--config-file",
        type=str,
        default="docs/guidance_config.yaml",
        help="要使用的逻辑配置文件路径 (例如: docs/guidance_config_new.yaml)。",
    )
    parser.add_argument(
        "--deploy-panels",
        action="store_true",
        help="是否部署或更新频道内的永久消息面板。",
    )
    args = parser.parse_args()

    await setup_guidance(args)

    log.info("任务完成，正在关闭机器人...")
    await bot.close()
    # 给予 aiohttp 一个短暂但确切的时间来关闭所有底层连接
    await asyncio.sleep(0.25)


async def main():
    """主函数，启动机器人。"""
    if not BOT_TOKEN:
        log.error("错误：未在 .env 文件中找到 BOT_TOKEN。")
        return

    try:
        await bot.start(BOT_TOKEN)
    except discord.LoginFailure:
        log.error("错误：无效的 Bot Token。请检查 .env 文件。")
    except Exception as e:
        log.error(f"启动机器人时发生未知错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
