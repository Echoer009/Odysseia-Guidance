import os
import json
import random
import re
import sys
import asyncio
from typing import Optional

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
    if env_content is None:
        print("错误: 无法读取 .env 文件内容")
        return
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
    if env_content is None:
        print("错误: 无法读取 .env 文件内容")
        return
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
    if env_content is None:
        print("错误: 无法读取 .env 文件内容")
        return
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


async def test_api_key(
    api_key: str, model_name: str = "gemini-2.5-flash", test_type: str = "generate"
) -> dict:
    """
    测试指定的 API 密钥是否可用

    Args:
        api_key: 要测试的 API 密钥
        model_name: 要使用的模型名称
        test_type: 测试类型，"generate" 或 "embed"

    Returns:
        包含测试结果的字典
    """
    from google import genai
    from google.genai import types as genai_types
    from google.genai import errors as genai_errors

    base_url = os.getenv("GEMINI_API_BASE_URL")
    if not base_url:
        base_url = "https://brain-girl.echoer009.workers.dev/K6QeZf0mQ4l51paQA5/gemini"

    result = {
        "api_key": api_key[-8:] + "...",  # 只显示后8位
        "model": model_name,
        "test_type": test_type,
        "success": False,
        "error_type": None,
        "error_message": None,
        "response": None,
    }

    try:
        # 创建客户端
        http_options = genai_types.HttpOptions(base_url=base_url)
        client = genai.Client(api_key=api_key, http_options=http_options)

        # 发送测试请求
        loop = asyncio.get_event_loop()

        if test_type == "embed":
            # 测试 embed 功能
            embed_config = genai_types.EmbedContentConfig(
                task_type="retrieval_document"
            )
            embedding_result = await loop.run_in_executor(
                None,
                lambda: client.models.embed_content(
                    model=model_name,
                    contents=[genai_types.Part(text="测试文本")],
                    config=embed_config,
                ),
            )

            if embedding_result and embedding_result.embeddings:
                result["success"] = True
                values = embedding_result.embeddings[0].values
                if values is not None:
                    result["response"] = f"向量维度: {len(values)}"
                else:
                    result["response"] = "向量维度: 未知"
            else:
                result["error_type"] = "EmptyEmbedding"
                result["error_message"] = "API 返回了空嵌入"
        else:
            # 测试 generate 功能
            gen_config = genai_types.GenerateContentConfig(
                temperature=0.7, max_output_tokens=100
            )

            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=model_name,
                    contents=["你好，请回复一句话。"],
                    config=gen_config,
                ),
            )

            if response.parts:
                result["success"] = True
                text = response.text if response.text is not None else ""
                result["response"] = text.strip()[:100]  # 限制显示长度
            else:
                result["error_type"] = "EmptyResponse"
                result["error_message"] = "API 返回了空响应"

    except genai_errors.ClientError as e:
        result["error_type"] = "ClientError"
        result["error_message"] = str(e)
    except genai_errors.ServerError as e:
        result["error_type"] = "ServerError"
        result["error_message"] = str(e)
    except Exception as e:
        result["error_type"] = type(e).__name__
        result["error_message"] = str(e)

    return result


def run_test(
    score_threshold: Optional[int] = None,
    model_name: str = "gemini-2.5-flash",
    test_type: str = "generate",
):
    """
    执行 API 密钥测试

    Args:
        score_threshold: 要测试的密钥分数阈值，None 表示测试所有密钥
        model_name: 要使用的模型名称
        test_type: 测试类型，"generate" 或 "embed"
    """
    print(f"--- 正在测试 API 密钥 (模型: {model_name}, 类型: {test_type}) ---")

    reputations = load_reputations()
    if reputations is None:
        return

    current_keys, _ = get_keys_from_env()
    if current_keys is None:
        return

    # 筛选符合分数条件的密钥
    keys_to_test = []
    for key, data in reputations.items():
        if key in current_keys and isinstance(data, dict) and "reputation" in data:
            score = data["reputation"]
            if score_threshold is None or score == score_threshold:
                keys_to_test.append((key, score))

    if not keys_to_test:
        print(
            f"没有找到分数 {'=' if score_threshold is not None else ''} {score_threshold} 的密钥。"
        )
        return

    # 随机选择一个密钥进行测试
    selected_key, selected_score = random.choice(keys_to_test)
    print(f"\n随机选择的密钥: {selected_key[-8:]}... (分数: {selected_score})")
    print("正在发送测试请求...")

    # 异步运行测试
    result = asyncio.run(test_api_key(selected_key, model_name, test_type))

    print("\n--- 测试结果 ---")
    print(f"密钥: {result['api_key']}")
    print(f"模型: {result['model']}")
    print(f"测试类型: {result['test_type']}")
    print(f"状态: {'✓ 成功' if result['success'] else '✗ 失败'}")

    if result["success"]:
        print(f"响应: {result['response']}")
    else:
        print(f"错误类型: {result['error_type']}")
        print(f"错误信息: {result['error_message']}")
    print("----------------")


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
        elif command == "test":
            # 解析 test 命令参数
            score_threshold = None
            model_name = "gemini-2.5-flash"
            test_type = "generate"

            # 解析可选参数
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--score" and i + 1 < len(sys.argv):
                    try:
                        score_threshold = int(sys.argv[i + 1])
                        i += 2
                    except ValueError:
                        print("错误: --score 参数需要一个整数")
                        return
                elif sys.argv[i] == "--model" and i + 1 < len(sys.argv):
                    model_name = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--type" and i + 1 < len(sys.argv):
                    test_type = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1

            run_test(score_threshold, model_name, test_type)
        else:
            print(f"错误: 未知命令 '{command}'")
            print("可用命令: status, reformat, add, test")
            print("\ntest 命令用法:")
            print(
                "  python scripts/manage_api_keys.py test                    # 随机测试一个密钥"
            )
            print(
                "  python scripts/manage_api_keys.py test --score 0          # 测试分数为 0 的密钥"
            )
            print(
                "  python scripts/manage_api_keys.py test --score -220       # 测试分数为 -220 的密钥"
            )
            print(
                "  python scripts/manage_api_keys.py test --model gemini-2.5-flash  # 指定模型"
            )
    else:
        run_default_removal()


if __name__ == "__main__":
    main()
