import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging

# 假设的配置路径
EVENTS_DIR = "src/chat/events"
log = logging.getLogger(__name__)


class EventService:
    """
    管理和提供对当前激活节日活动信息的访问。
    """

    def __init__(self):
        self._active_event = None
        self.selected_faction_info = (
            None  # 用于存储当前选择的派系信息 {'event_id': str, 'faction_id': str}
        )
        self._load_and_check_events()

    def _load_and_check_events(self):
        """
        从文件系统加载所有活动配置，并找出当前激活的活动。
        这个方法可以在服务初始化时调用，也可以通过定时任务定期调用以刷新状态。
        """
        now = datetime.now(timezone.utc)
        if not os.path.exists(EVENTS_DIR):
            log.warning(f"活动配置目录不存在: {EVENTS_DIR}")
            return

        for event_id in os.listdir(EVENTS_DIR):
            manifest_path = os.path.join(EVENTS_DIR, event_id, "manifest.json")

            if not os.path.exists(manifest_path):
                continue

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            is_active_flag = manifest.get("is_active", False)
            if not is_active_flag:
                continue

            start_date = datetime.fromisoformat(
                manifest["start_date"].replace("Z", "+00:00")
            )
            end_date = datetime.fromisoformat(
                manifest["end_date"].replace("Z", "+00:00")
            )

            if start_date <= now < end_date:
                self._active_event = self._load_full_event_config(event_id)
                log.info(f"活动已激活: {self._active_event['event_name']}")
                # 假设一次只有一个活动是激活的
                return

        # 如果没有找到激活的活动
        self._active_event = None
        log.info("当前没有激活的活动。")

    def _load_full_event_config(self, event_id: str) -> Dict[str, Any]:
        """
        加载指定活动的所有相关配置文件并合并成一个字典。
        """
        event_path = os.path.join(EVENTS_DIR, event_id)
        config = {}

        # 加载所有配置文件
        for config_file in [
            "manifest.json",
            "factions.json",
            "items.json",
            "prompts.json",
        ]:
            file_path = os.path.join(event_path, config_file)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 将配置文件内容合并到主配置字典中
                    if config_file == "manifest.json":
                        config.update(data)
                    else:
                        # 去掉 .json 后缀作为 key
                        key_name = config_file.split(".")[0]
                        config[key_name] = data

        # --- 新增：加载派系包文件 ---
        if "prompts" in config and "system_prompt_faction_packs" in config["prompts"]:
            faction_packs_config = config["prompts"]["system_prompt_faction_packs"]
            loaded_packs = {}

            for faction_id, relative_path in faction_packs_config.items():
                pack_file_path = os.path.join(event_path, relative_path)
                if os.path.exists(pack_file_path):
                    with open(pack_file_path, "r", encoding="utf-8") as f:
                        loaded_packs[faction_id] = f.read()
                else:
                    log.warning(f"派系包文件未找到: {pack_file_path}")

            config["system_prompt_faction_pack_content"] = loaded_packs

        return config

    def get_active_event(self) -> Optional[Dict[str, Any]]:
        """
        返回当前激活的活动配置字典，如果没有则返回 None。
        """
        return self._active_event

    def get_event_factions(self) -> List[Dict[str, Any]]:
        """获取所有事件中可用的派系，用于手动选择。"""
        all_factions = []
        if not os.path.exists(EVENTS_DIR):
            log.warning(f"活动目录 '{EVENTS_DIR}' 不存在。")
            return []

        for event_id in os.listdir(EVENTS_DIR):
            event_path = os.path.join(EVENTS_DIR, event_id)
            if not os.path.isdir(event_path):
                continue

            factions_path = os.path.join(event_path, "factions.json")
            if os.path.exists(factions_path):
                try:
                    with open(factions_path, "r", encoding="utf-8") as f:
                        factions_data = json.load(f)
                        for faction in factions_data:
                            faction["event_id"] = event_id
                            all_factions.append(faction)
                except json.JSONDecodeError as e:
                    log.error(f"解析派系文件JSON失败 '{factions_path}': {e}")
                except Exception as e:
                    log.error(f"处理派系文件时发生未知错误 '{factions_path}': {e}")

        log.info(f"共找到 {len(all_factions)} 个可供选择的派系。")
        return all_factions

    def get_event_items(self) -> Optional[List[Dict[str, Any]]]:
        """获取当前激活活动的商品列表"""
        if self._active_event:
            return self._active_event.get("items")
        return None

    def get_prompt_overrides(self) -> Optional[Dict[str, str]]:
        """
        获取当前激活活动的提示词覆盖配置。
        如果设置了当前选择的派系，则不进行任何覆盖，以便使用派系包。
        """
        # 如果已手动选择派系，则不应用任何通用提示词覆盖
        if self.get_selected_faction():
            log.info(
                f"EventService: 已选择派系 '{self.get_selected_faction()}'，跳过通用提示词覆盖。"
            )
            return None

        # 仅在没有手动选择派系时，才检查时间激活的活动是否需要通用覆盖
        if self._active_event and "prompts" in self._active_event:
            prompts_config = self._active_event["prompts"]
            log.info(f"EventService: 正在检查此活动的通用提示词配置: {prompts_config}")
            fallback_overrides = prompts_config.get("overrides")
            log.info(f"EventService: 返回通用提示词: {fallback_overrides}")
            return fallback_overrides

        log.info("EventService: 没有检测到活动或活动提示词配置。")
        return None

    def get_system_prompt_faction_pack_content(self) -> Optional[str]:
        """
        根据当前选择的派系，动态加载并返回其派系包文件内容。
        """
        if not self.selected_faction_info:
            return None

        event_id = self.selected_faction_info.get("event_id")
        faction_id = self.selected_faction_info.get("faction_id")

        if not event_id or not faction_id:
            return None

        event_path = os.path.join(EVENTS_DIR, event_id)
        prompts_path = os.path.join(event_path, "prompts.json")

        if not os.path.exists(prompts_path):
            log.warning(
                f"派系 '{faction_id}' 所在的事件 '{event_id}' 没有 prompts.json 文件。"
            )
            return None

        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                prompts_config = json.load(f)

            faction_packs_config = prompts_config.get("system_prompt_faction_packs")
            if not faction_packs_config or faction_id not in faction_packs_config:
                log.warning(f"prompts.json 中没有找到派系 '{faction_id}' 的配置。")
                return None

            relative_path = faction_packs_config[faction_id]
            pack_file_path = os.path.join(event_path, relative_path)

            if os.path.exists(pack_file_path):
                with open(pack_file_path, "r", encoding="utf-8") as f:
                    log.debug(
                        f"正在为选择的派系 '{faction_id}' 从 '{pack_file_path}' 加载派系包。"
                    )
                    return f.read()
            else:
                log.warning(f"派系包文件未找到: {pack_file_path}")
                return None

        except Exception as e:
            log.error(f"加载派系 '{faction_id}' 的提示词包时出错: {e}")
            return None

    def set_selected_faction(self, faction_id: Optional[str]):
        """
        根据派系ID设置当前手动选择的派系。
        """
        if not faction_id:
            self.selected_faction_info = None
            log.info("EventService: 派系选择已重置。")
            return

        all_factions = self.get_event_factions()
        found_faction = next(
            (f for f in all_factions if f["faction_id"] == faction_id), None
        )

        if found_faction:
            self.selected_faction_info = {
                "event_id": found_faction["event_id"],
                "faction_id": faction_id,
            }
            log.info(
                f"EventService: 手动选择的派系人设已设置为: {self.selected_faction_info}"
            )
        else:
            self.selected_faction_info = None
            log.warning(f"EventService: 尝试设置一个不存在的派系ID: {faction_id}")

    def get_selected_faction(self) -> Optional[str]:
        """
        获取当前活动手动选择的派系 ID。
        """
        return (
            self.selected_faction_info.get("faction_id")
            if self.selected_faction_info
            else None
        )

    def set_winning_faction(self, faction_id: str):
        """
        设置当前活动的获胜派系。
        """
        if self._active_event:
            self._active_event["winning_faction"] = faction_id
            log.info(
                f"活动 '{self._active_event['event_name']}' 的获胜派系已设置为: {faction_id}"
            )
        else:
            log.warning("尝试设置获胜派系，但当前没有激活的活动。")

    def get_winning_faction(self) -> Optional[str]:
        """
        获取当前活动的获胜派系。
        """
        if self._active_event:
            return self._active_event.get("winning_faction")
        return None


# 单例模式
event_service = EventService()
