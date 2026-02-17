import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, date, timedelta
import logging
import re

# 假设的配置路径
EVENTS_DIR = "src/chat/events"
log = logging.getLogger(__name__)

# 春节相关常量
SPRING_FESTIVAL_2026_EVE = "spring_festival_eve"
SPRING_FESTIVAL_2026_DAY = "spring_festival_day"
SPRING_FESTIVAL_2026_GENERIC_DAY = "spring_festival_generic_day"

# 2026年春节（大年初一）日期
SPRING_FESTIVAL_2026_START = date(2026, 2, 17)  # 大年初一

# 初二到十四的节日描述映射
SPRING_FESTIVAL_DESCRIPTIONS = {
    2: "大年初二！回娘家、吃面条，寓意着“顺顺溜溜”，年味依旧浓厚~",
    3: "大年初三！小年朝，早睡晚起，寓意“赤狗日”，不宜拜年，适合在家休息~",
    4: "大年初四！迎灶神，全家团聚，寓意“羊日”，吉祥如意~",
    5: "大年初五！迎财神，放鞭炮，寓意“破五”，财源滚滚来~",
    6: "大年初六！送穷鬼，启市营业，寓意“马日”，马到成功~",
    7: "大年初七！人日庆生，吃七宝羹，寓意“人的生日”，万物复苏~",
    8: "大年初八！谷日生日，放生祈福，寓意“聚财”，八方来财~",
    9: "大年初九！玉皇大帝诞辰，祭天祈福，寓意“天日”，天赐良机~",
    10: "大年初十！祭石感恩，寓意“石头日”，稳固安康~",
    11: "大年初十一！子婿日，岳父宴请女婿，寓意“亲上加亲”~",
    12: "大年初十二！搭灯棚，准备元宵，寓意“添灯”，喜上加喜~",
    13: "大年初十三！灶王爷点查户口，寓意“灯头生日”，光明在前~",
    14: "大年初十四！试花灯，猜灯谜，寓意“守夜”，喜迎元宵~",
}


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
        对于需要动态参数的派系（如spring_festival_generic_day），会进行占位符替换。
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
                    content = f.read()

                    # 动态替换占位符
                    content = self._replace_faction_placeholders(faction_id, content)

                    return content
            else:
                log.warning(f"派系包文件未找到: {pack_file_path}")
                return None

        except Exception as e:
            log.error(f"加载派系 '{faction_id}' 的提示词包时出错: {e}")
            return None

    def _replace_faction_placeholders(self, faction_id: str, content: str) -> str:
        """
        根据派系ID替换内容中的占位符。
        """
        if faction_id == SPRING_FESTIVAL_2026_GENERIC_DAY:
            return self._replace_spring_festival_generic_day(content)

        # 可以在这里添加其他需要动态替换的派系
        # elif faction_id == "some_other_faction":
        #     return self._replace_some_other_faction(content)

        return content

    def _replace_spring_festival_generic_day(self, content: str) -> str:
        """
        为春节初二到十四的通用派系替换占位符。
        占位符：
        - {day}: 大年初几（2-14）
        - {festival_description}: 对应的节日描述
        """
        try:
            # 获取当前日期（使用本地时间，因为春节是中国的传统节日）
            today = date.today()

            # 计算距离春节的天数
            days_since_start = (today - SPRING_FESTIVAL_2026_START).days

            # 计算是初几（大年初一 + days_since_start）
            lunar_day = 1 + days_since_start

            # 验证是否在初二到十四范围内
            if lunar_day < 2 or lunar_day > 14:
                log.warning(
                    f"当前日期 {today} 不在春节初二到十四范围内（当前计算为初{lunar_day}）。"
                    f"将使用默认值初二（2）。"
                )
                lunar_day = 2

            # 获取节日描述
            description = SPRING_FESTIVAL_DESCRIPTIONS.get(
                lunar_day, f"大年初{lunar_day}！春节假期中，年味正浓~"
            )

            # 替换占位符
            replaced_content = content.replace("{day}", str(lunar_day))
            replaced_content = replaced_content.replace(
                "{festival_description}", description
            )

            log.debug(
                f"已替换春节通用派系占位符：day={lunar_day}, description={description[:50]}..."
            )

            return replaced_content

        except Exception as e:
            log.error(f"替换春节通用派系占位符时出错: {e}")
            return content

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

    def get_selected_faction_info(self) -> Optional[Dict[str, str]]:
        """
        获取当前手动选择的派系的完整信息，包括 event_id 和 faction_id。
        """
        return self.selected_faction_info

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
