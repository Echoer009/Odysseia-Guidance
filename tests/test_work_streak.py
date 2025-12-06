import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

# 添加 asyncio 标记，确保 pytest 能正确处理异步测试
pytestmark = pytest.mark.asyncio

from src.chat.features.work_game.services.work_db_service import WorkDBService
from src.chat.features.work_game.config.work_config import WorkConfig

# 定义测试用的用户ID
USER_ID = 12345

# 定义一个固定的UTC+8时区，以便测试中使用
# 这与 work_db_service.py 中使用的 UTC 时间刷新逻辑不同，
# 仅用于在测试用例中创建一个明确的、与时区相关的 "现在" 的时间点。
APP_TIMEZONE = timezone(timedelta(hours=8))

# 定义固定的时间点用于测试
# 我们假设 "今天" 是 2025年12月7日 中午12点 (UTC+8)
# 这对应 UTC 时间是 2025年12月7日 凌晨4点
TODAY = datetime(2025, 12, 7, 12, 0, 0, tzinfo=APP_TIMEZONE)
YESTERDAY = TODAY - timedelta(days=1)
TWO_DAYS_AGO = TODAY - timedelta(days=2)


@pytest.fixture
def work_db_service():
    """创建一个 WorkDBService 的实例用于测试，并模拟其数据库依赖。"""
    service = WorkDBService()
    # 我们模拟 get_user_work_status 和 _update_user_work_status_from_dict
    # 这样测试就不会真正访问数据库
    service.get_user_work_status = AsyncMock()
    service._update_user_work_status_from_dict = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_streak_first_day(work_db_service, mocker):
    """测试用户首次打工时，连续天数应为1。"""
    # 模拟数据库返回一个新用户的状态
    work_db_service.get_user_work_status.return_value = {
        "consecutive_work_days": 0,
        "last_streak_date": None,
    }
    # 模拟当前时间
    # 使用更健壮的方式 mock datetime
    mock_datetime = MagicMock()
    mock_datetime.now.return_value = TODAY
    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
    mocker.patch(
        "src.chat.features.work_game.services.work_db_service.datetime", mock_datetime
    )

    is_achieved, new_streak = await work_db_service.update_work_record_and_check_streak(
        USER_ID
    )

    assert not is_achieved
    assert new_streak == 1
    # 验证数据库更新时传入了正确的数据
    work_db_service._update_user_work_status_from_dict.assert_called_once()
    call_args = work_db_service._update_user_work_status_from_dict.call_args[0][1]
    assert call_args["consecutive_work_days"] == 1
    assert call_args["last_streak_date"] == TODAY.date().isoformat()


@pytest.mark.asyncio
async def test_streak_consecutive_day(work_db_service, mocker):
    """测试用户连续第二天打工，天数应+1。"""
    # 模拟数据库返回用户昨天打过工的状态
    work_db_service.get_user_work_status.return_value = {
        "consecutive_work_days": 1,
        "last_streak_date": YESTERDAY.date().isoformat(),
    }
    # 模拟当前时间为 "今天"
    mock_datetime = MagicMock()
    mock_datetime.now.return_value = TODAY
    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
    mock_datetime.date.side_effect = datetime.date
    mocker.patch(
        "src.chat.features.work_game.services.work_db_service.datetime", mock_datetime
    )

    is_achieved, new_streak = await work_db_service.update_work_record_and_check_streak(
        USER_ID
    )

    assert not is_achieved
    assert new_streak == 2
    call_args = work_db_service._update_user_work_status_from_dict.call_args[0][1]
    assert call_args["consecutive_work_days"] == 2


@pytest.mark.asyncio
async def test_streak_same_day_no_change(work_db_service, mocker):
    """[核心测试] 测试用户在同一天多次打工，连续天数不应改变。"""
    # 模拟数据库返回用户今天已经打过工的状态
    work_db_service.get_user_work_status.return_value = {
        "consecutive_work_days": 3,  # 假设已经连续3天
        "last_streak_date": TODAY.date().isoformat(),
    }
    # 模拟当前时间为 "今天" 的晚些时候
    later_today = TODAY + timedelta(hours=2)
    mock_datetime = MagicMock()
    mock_datetime.now.return_value = later_today
    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
    mocker.patch(
        "src.chat.features.work_game.services.work_db_service.datetime", mock_datetime
    )

    is_achieved, new_streak = await work_db_service.update_work_record_and_check_streak(
        USER_ID
    )

    assert not is_achieved
    assert new_streak == 3  # 天数应该保持不变
    call_args = work_db_service._update_user_work_status_from_dict.call_args[0][1]
    assert call_args["consecutive_work_days"] == 3


@pytest.mark.asyncio
async def test_streak_broken(work_db_service, mocker):
    """测试用户中断一天后打工，连续天数应重置为1。"""
    # 模拟数据库返回用户前天打过工的状态
    work_db_service.get_user_work_status.return_value = {
        "consecutive_work_days": 5,
        "last_streak_date": TWO_DAYS_AGO.date().isoformat(),
    }
    # 模拟当前时间为 "今天"
    mock_datetime = MagicMock()
    mock_datetime.now.return_value = TODAY
    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
    mocker.patch(
        "src.chat.features.work_game.services.work_db_service.datetime", mock_datetime
    )

    is_achieved, new_streak = await work_db_service.update_work_record_and_check_streak(
        USER_ID
    )

    assert not is_achieved
    assert new_streak == 1  # 天数应重置
    call_args = work_db_service._update_user_work_status_from_dict.call_args[0][1]
    assert call_args["consecutive_work_days"] == 1


@pytest.mark.asyncio
async def test_streak_achieved_and_reset(work_db_service, mocker):
    """测试用户达成全勤奖励目标后，状态应正确并重置天数。"""
    # 为了测试方便，我们临时将目标天数设为3天
    mocker.patch.object(WorkConfig, "STREAK_DAYS", 3)

    # 模拟用户已连续2天，且昨天是最后一次
    work_db_service.get_user_work_status.return_value = {
        "consecutive_work_days": 2,
        "last_streak_date": YESTERDAY.date().isoformat(),
    }
    # 模拟当前时间为 "今天"
    mock_datetime = MagicMock()
    mock_datetime.now.return_value = TODAY
    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
    mocker.patch(
        "src.chat.features.work_game.services.work_db_service.datetime", mock_datetime
    )

    is_achieved, new_streak = await work_db_service.update_work_record_and_check_streak(
        USER_ID
    )

    assert is_achieved  # 应该达成奖励
    assert new_streak == 0  # 天数应重置为0
    call_args = work_db_service._update_user_work_status_from_dict.call_args[0][1]
    assert call_args["consecutive_work_days"] == 0
