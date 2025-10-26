import os
import json
import re
import sys

# 将项目根目录添加到 sys.path，以便可以导入项目模块（如果需要）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

REPUTATION_FILE = os.path.join(ROOT_DIR, "data", "key_reputations.json")
ENV_FILE = os.path.join(ROOT_DIR, ".env")


def load_reputations():
    """加载信誉分数文件"""
    if not os.path.exists(REPUTATION_FILE):
        print(f"错误: 信誉文件未找到于 {REPUTATION_FILE}")
        return None
    try:
        with open(REPUTATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"错误: 读取或解析信誉文件失败: {e}")
        return None


def get_keys_from_env():
    """从 .env 文件中获取 GEMINI_API_KEYS"""
    if not os.path.exists(ENV_FILE):
        print(f"错误: .env 文件未找到于 {ENV_FILE}")
        return None, None

    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r'GOOGLE_API_KEYS_LIST="(.*?)"', content, re.DOTALL)
        if not match:
            print(
                "错误: 在 .env 文件中未找到格式正确的 'GOOGLE_API_KEYS_LIST=\"...\"'。"
            )
            return None, None

        keys_str = match.group(1)

        # 对每个分割后的 key 去除可能存在的引号
        keys = [
            key.strip().strip('"').strip("'")
            for key in keys_str.split(",")
            if key.strip()
        ]
        return keys, content
    except IOError as e:
        print(f"错误: 读取 .env 文件失败: {e}")
        return None, None


def reformat_keys_in_env():
    """将 .env 文件中的密钥重新格式化为多行以提高可读性"""
    print("--- 正在重新格式化 .env 文件中的密钥 ---")
    current_keys, env_content = get_keys_from_env()
    if current_keys is None:
        return

    if not current_keys:
        print("在 .env 文件中没有找到要格式化的密钥。")
        return

    # 格式化密钥列表，每个密钥占一行
    formatted_keys_str = ",\n".join(current_keys)
    new_keys_block = f'GOOGLE_API_KEYS_LIST="{formatted_keys_str}"'

    # 使用正则表达式替换 .env 文件中的行 (移除 DOTALL 防止贪婪匹配)
    new_env_content = re.sub(
        r'GOOGLE_API_KEYS_LIST=".*?"',
        new_keys_block,
        env_content,
        flags=re.DOTALL,
    )

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(new_env_content)
        print(f"\n成功! 已将 {len(current_keys)} 个密钥重新格式化为多行。")
    except IOError as e:
        print(f"错误: 写入 .env 文件失败: {e}")


def add_keys_to_env():
    """向 .env 文件中添加新的密钥"""
    print("--- 正在向 .env 文件添加新密钥 ---")
    current_keys, env_content = get_keys_from_env()
    if current_keys is None:
        # 如果 .env 或变量不存在，则从一个空列表开始
        current_keys = []
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            env_content = f.read()

    print("请输入或粘贴要添加的新密钥。可以包含逗号、空格或换行符。")
    print(
        "输入完成后，在新的一行按 Ctrl+Z (Windows) 或 Ctrl+D (Linux/macOS) 结束输入。"
    )

    new_keys_input = sys.stdin.read()

    # 分割并清理输入的密钥
    # 使用正则表达式匹配逗号、空格、换行符等作为分隔符
    new_keys = re.split(r"[\s,]+", new_keys_input)
    # 过滤掉空字符串并去除每个密钥可能存在的引号
    cleaned_new_keys = [
        key.strip().strip('"').strip("'") for key in new_keys if key.strip()
    ]

    if not cleaned_new_keys:
        print("没有输入有效的密钥。操作已取消。")
        return

    # 合并并去重
    existing_keys_set = set(current_keys)
    unique_new_keys = [key for key in cleaned_new_keys if key not in existing_keys_set]

    if not unique_new_keys:
        print("所有输入的新密钥都已存在。无需添加。")
        return

    updated_keys = current_keys + unique_new_keys

    # 格式化更新后的密钥列表为多行
    formatted_keys_str = ",\n".join(updated_keys)
    new_keys_block = f'GOOGLE_API_KEYS_LIST="{formatted_keys_str}"'

    # 使用正则表达式替换 .env 文件中的行 (移除 DOTALL 防止贪婪匹配)
    new_env_content = re.sub(
        r'GOOGLE_API_KEYS_LIST=".*?"',
        new_keys_block,
        env_content,
        flags=re.DOTALL,
    )

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(new_env_content)
        print(f"\n成功! 添加了 {len(unique_new_keys)} 个新密钥。")
        print(f"现在共有 {len(updated_keys)} 个密钥。")
    except IOError as e:
        print(f"错误: 写入 .env 文件失败: {e}")


def run_status_check():
    """执行状态检查的功能"""
    print("--- 正在检查 API 密钥分数分布 ---")
    reputations = load_reputations()
    if reputations is None:
        return
    current_keys, _ = get_keys_from_env()
    if current_keys is None:
        return

    score_counts = {}
    for key, data in reputations.items():
        if key in current_keys:
            if isinstance(data, dict) and "reputation" in data:
                score = data["reputation"]
                score_counts[score] = score_counts.get(score, 0) + 1

    if score_counts:
        print("\n--- 当前密钥分数分布 ---")
        sorted_scores = sorted(
            [s for s in score_counts.keys() if isinstance(s, (int, float))]
        )
        for score in sorted_scores:
            print(f"  - 分数: {score}, 密钥数量: {score_counts[score]}")
        print("-------------------------")
    else:
        print("没有找到与当前 .env 中密钥匹配的信誉数据。")


def run_default_removal():
    """执行默认的交互式密钥移除功能"""
    print("--- API 密钥信誉管理脚本 ---")

    reputations = load_reputations()
    if reputations is None:
        return

    current_keys, env_content = get_keys_from_env()
    if current_keys is None:
        return

    print(f"当前 .env 文件中共有 {len(current_keys)} 个密钥。")
    print(f"已加载 {len(reputations)} 个密钥的信誉数据。")

    # 首先，显示分数分布
    run_status_check()

    try:
        threshold_str = input(
            "\n请输入要移除的密钥的信誉分数阈值 (例如, 输入 10 将移除所有分数低于 10 的密钥): "
        )
        threshold = int(threshold_str)
    except (ValueError, KeyboardInterrupt):
        print("\n无效输入或用户中断。操作已取消。")
        return

    keys_to_remove = {
        key
        for key, data in reputations.items()
        if key in current_keys
        and isinstance(data, dict)
        and data.get("reputation", float("inf")) < threshold
    }

    if not keys_to_remove:
        print(f"没有找到信誉分数低于 {threshold} 的密钥。无需任何操作。")
        return

    print(
        f"\n警告: 发现 {len(keys_to_remove)} 个密钥的信誉分数低于阈值，将被从 .env 文件中移除:"
    )
    for key in keys_to_remove:
        reputation_value = reputations.get(key, {})
        score_display = (
            reputation_value.get("reputation", "N/A")
            if isinstance(reputation_value, dict)
            else "格式错误"
        )
        print(f"  - {key} (分数: {score_display})")

    try:
        confirm = input("\n您确定要永久移除以上所列的密钥吗? (y/n): ").lower()
    except KeyboardInterrupt:
        print("\n操作已取消。")
        return

    if confirm != "y":
        print("操作已取消。")
        return

    updated_keys = [key for key in current_keys if key not in keys_to_remove]

    if updated_keys:
        # 格式化密钥列表，每个密钥占一行
        formatted_keys_str = ",\n".join(updated_keys)
        new_keys_block = f'GOOGLE_API_KEYS_LIST="{formatted_keys_str}"'
    else:
        new_keys_block = 'GOOGLE_API_KEYS_LIST=""'

    # 使用正则表达式替换 .env 文件中的行 (移除 DOTALL 防止贪婪匹配)
    new_env_content = re.sub(
        r'GOOGLE_API_KEYS_LIST=".*?"',
        new_keys_block,
        env_content,
        flags=re.DOTALL,
    )

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(new_env_content)
        print(f"\n成功! 已从 .env 文件中移除 {len(keys_to_remove)} 个密钥。")
        print(f"剩余 {len(updated_keys)} 个密钥。")
    except IOError as e:
        print(f"错误: 写入 .env 文件失败: {e}")


def main():
    """主执行函数，现在仅用于命令分发"""
    global ENV_FILE  # 声明我们将修改全局变量

    env_path_override = None
    # 手动解析 --env-file 参数
    if "--env-file" in sys.argv:
        try:
            index = sys.argv.index("--env-file")
            env_path_override = sys.argv[index + 1]
            # 从参数列表中移除标志和值，以免干扰后续逻辑
            sys.argv.pop(index)
            sys.argv.pop(index)
        except (ValueError, IndexError):
            print("错误: --env-file 标志需要一个路径参数。")
            return

    if env_path_override:
        if not os.path.exists(env_path_override):
            print(f"错误: 提供的 .env 文件路径不存在: {env_path_override}")
            return
        ENV_FILE = env_path_override
        print(f"--- 正在对指定的 .env 文件进行操作: {ENV_FILE} ---")

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "status":
            run_status_check()
        elif command == "reformat":
            reformat_keys_in_env()
        elif command == "add":
            add_keys_to_env()
        else:
            print(f"错误: 未知命令 '{command}'")
            print("可用命令: status, reformat, add")
    else:
        run_default_removal()


if __name__ == "__main__":
    main()
