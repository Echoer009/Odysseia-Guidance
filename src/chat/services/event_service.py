import os
import json
from typing import Optional, Dict, Any, List
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
        self.selected_faction_id = None  # 新增：用于存储当前选择的派系ID
        self._load_and_check_events()

    def _load_and_check_events(self):
        """
        从文件系统加载所有活动配置，并找出当前激活的活动。
        这个方法可以在服务初始化时调用，也可以通过定时任务定期调用以刷新状态。
        """

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

            # start_date = datetime.fromisoformat(manifest["start_date"])
            # end_date = datetime.fromisoformat(manifest["end_date"])

            # if start_date <= now < end_date: # NOTE: 为方便测试，暂时禁用日期检查
            # 只要 is_active 为 true, 就加载活动
            self._active_event = self._load_full_event_config(event_id)
            log.info(
                f"活动已激活 (测试模式，日期检查已绕过): {self._active_event['event_name']}"
            )
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

    def get_event_factions(self) -> Optional[List[Dict[str, Any]]]:
        """获取当前激活活动的派系列表"""
        if self._active_event:
            return self._active_event.get("factions")
        return None

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
        if not self._active_event or "prompts" not in self._active_event:
            log.info("EventService: 没有检测到活动或活动提示词配置。")
            return None

        # 如果选择了派系人设，则不使用任何覆盖，让 PromptService 去加载派系包
        if self.selected_faction_id:
            log.info(
                f"EventService: 已选择派系 '{self.selected_faction_id}'，跳过提示词覆盖逻辑。"
            )
            return None

        prompts_config = self._active_event["prompts"]
        log.info(f"EventService: 正在检查此活动的通用提示词配置: {prompts_config}")

        # 仅在没有选择派系时，才返回通用活动提示词
        fallback_overrides = prompts_config.get("overrides")
        log.info(f"EventService: 返回通用提示词: {fallback_overrides}")
        return fallback_overrides

    def get_system_prompt_faction_pack_content(self) -> Optional[str]:
        """
        获取当前选择派系的派系包文件内容。
        """
        if not self._active_event:
            return None

        selected_faction = self.get_selected_faction()
        if not selected_faction:
            return None

        all_packs_content = self._active_event.get("system_prompt_faction_pack_content")
        if not all_packs_content:
            return None

        log.debug(f"正在为当前选择的派系 '{selected_faction}' 提供派系包内容。")
        return all_packs_content.get(selected_faction)

    def set_selected_faction(self, faction_id: Optional[str]):
        """
        设置当前活动手动选择的派系。
        """
        if self._active_event:
            self.selected_faction_id = faction_id
            log.info(f"EventService: 手动选择的派系人设 ID 已设置为: {faction_id}")
        else:
            log.warning("EventService: 尝试设置派系人设，但当前没有激活的活动。")

    def get_selected_faction(self) -> Optional[str]:
        """
        获取当前活动手动选择的派系。
        """
        return self.selected_faction_id

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
