import os
import re


def clean_text(text):
    """
    移除文本中的emoji符号。
    此正则表达式经过优化，可避免错误地移除中文字符或符号。
    """
    # 一个更安全的、经过策划的Emoji正则表达式，以避免影响中文字符
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # Emoticons
        "\U0001f300-\U0001f5ff"  # Symbols and Pictographs
        "\U0001f680-\U0001f6ff"  # Transport & Map Symbols
        "\U0001f1e0-\U0001f1ff"  # Flags (iOS)
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U00002600-\U000026ff"  # Miscellaneous Symbols
        "\U00002700-\U000027bf"  # Dingbats
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)


def process_knowledge_files(input_dir, output_dir):
    """
    处理指定目录下的所有知识文件，仅移除emoji。
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")

    for filename in os.listdir(input_dir):
        if filename.endswith((".md", ".txt")):
            input_path = os.path.join(input_dir, filename)
            basename, _ = os.path.splitext(filename)
            output_path = os.path.join(output_dir, f"cleaned_{basename}.txt")

            print(f"正在处理: {input_path}")

            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 1. 清洗文本
                cleaned_content = clean_text(content)

                # 2. 直接保存清洗后的内容
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(cleaned_content)

                print(f"已保存至: {output_path}")

            except Exception as e:
                print(f"处理文件 {input_path} 时出错: {e}")


if __name__ == "__main__":
    INPUT_DIRECTORY = "knowledge_data"
    OUTPUT_DIRECTORY = "knowledge_data_cleaned"

    print("开始处理知识库文件...")
    process_knowledge_files(INPUT_DIRECTORY, OUTPUT_DIRECTORY)
    print("所有文件处理完毕。")
