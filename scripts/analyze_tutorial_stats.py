import os
import re


def count_stats(text):
    """计算文本的字符数、单词数和近似Token数。"""
    character_count = len(text)

    # 使用正则表达式匹配中文、英文单词和数字，作为更准确的“词”
    # 这对于混合文本和中文分词有更好的近似效果
    words = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fa5]", text)
    word_count = len(words)

    # 对于中文为主的文档，通常一个汉字算一个Token，或接近1个Token。
    # 这里我们使用字符数作为Token的粗略估计，这对于中文语境比较常见。
    # 也可以使用 character_count / 1.5 或其他系数进行估算，但这取决于具体的Tokenzier。
    # 为避免复杂性，我们直接用字符数作为Token数报告。
    estimated_token_count = character_count

    return character_count, word_count, estimated_token_count


def analyze_tutorial_directory(base_dir="tutorial/"):
    """遍历教程目录，分析所有Markdown文件的字数和Token数。"""
    total_character_count = 0
    total_word_count = 0
    total_token_count = 0

    print(f"开始分析目录: {base_dir}\n")
    print(
        f"{'文件路径':<60} | {'字符数':<8} | {'词数(近似)':<10} | {'Token数(估算)':<12}"
    )
    print("-" * 100)

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    char_count, word_count, token_count = count_stats(content)

                    total_character_count += char_count
                    total_word_count += word_count
                    total_token_count += token_count

                    print(
                        f"{filepath:<60} | {char_count:<8} | {word_count:<10} | {token_count:<12}"
                    )
                except Exception as e:
                    print(f"错误处理文件 {filepath}: {e}")

    print("-" * 100)
    print(
        f"{'总计':<60} | {total_character_count:<8} | {total_word_count:<10} | {total_token_count:<12}"
    )
    print("\nToken数是基于字符数的粗略估算，具体数值会因使用的LLM分词器而异。")


if __name__ == "__main__":
    analyze_tutorial_directory("tutorial/")
