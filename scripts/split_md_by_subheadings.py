import os
import re
import argparse
import glob


def slugify(text):
    """将文本转换为适合文件名和URL的slug。"""
    # 移除标题开头的数字和点号，例如 "1.1 " 或 "1. "
    text = re.sub(r"^\d+(\.\d+)*\s*", "", text)
    # 移除类似 "A1_", "D9_" 这种字母数字组合的前缀
    text = re.sub(r"^[A-Z]\d+_", "", text, flags=re.IGNORECASE)

    # 匹配所有非字母数字、非中文、非下划线的字符，替换为下划线
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_]", "_", text)
    text = re.sub(r"_+", "_", text)  # 合并多个下划线
    text = text.strip("_")  # 移除开头和结尾 of 的下划线
    return text.lower()


def split_markdown_file_into_subdocuments(input_filepath, output_base_dir):
    """
    根据Markdown一级标题（#）拆分文件，
    每个一级标题及其下的内容作为一个独立的子文档。
    同时会继承父文档头部的 Front Matter。
    """
    try:
        with open(input_filepath, "r", encoding="utf-8-sig") as f:
            full_text = f.read()
    except Exception as e:
        print(f"读取文件失败 {input_filepath}: {e}")
        return

    # 提取 Front Matter
    front_matter = ""
    content_text = full_text
    if full_text.startswith("---"):
        parts = full_text.split("---", 2)
        if len(parts) >= 3:
            front_matter = f"---{parts[1]}---\n"
            content_text = parts[2]

    lines = content_text.splitlines(keepends=True)

    # 确保基础输出目录存在
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
        print(f"创建输出目录: {output_base_dir}")

    # 获取并清理父文档名
    base_name = os.path.basename(input_filepath)
    main_title, _ = os.path.splitext(base_name)
    output_subdir_name = slugify(main_title)

    # 创建父文档命名的子目录
    output_dir = os.path.join(output_base_dir, output_subdir_name)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建子目录: {output_dir}")

    subdocuments = []
    current_subdocument = []
    current_title = ""

    # 处理引言部分（第一个一级标题之前的内容）
    first_heading_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            first_heading_index = i
            break

    if first_heading_index > 0:
        intro_content = "".join(lines[:first_heading_index]).strip()
        if intro_content:
            intro_filename = os.path.join(
                output_dir,
                f"{output_subdir_name}_introduction.md",
            )
            with open(intro_filename, "w", encoding="utf-8") as f:
                f.write(f"{front_matter}# {main_title} Introduction\n\n{intro_content}")
            print(f"创建引言文件: {intro_filename}")
        lines = lines[first_heading_index:]
    elif first_heading_index == -1:
        # 如果完全没找到标题
        if lines:
            filename = os.path.join(output_dir, f"{output_subdir_name}.md")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(front_matter + "".join(lines))
            print(f"已将整个文件保存为: {filename}")
        return

    for line in lines:
        if line.strip().startswith("# "):
            if current_subdocument:
                subdocuments.append(
                    {"title": current_title, "content": "".join(current_subdocument)}
                )
            current_title = line.strip()[2:].strip()
            current_subdocument = [line]
        elif current_subdocument:
            current_subdocument.append(line)

    if current_subdocument:
        subdocuments.append(
            {"title": current_title, "content": "".join(current_subdocument)}
        )

    for subdoc in subdocuments:
        title = subdoc["title"]
        content = subdoc["content"]
        # 使用 "父文档_子标题" 作为文件名
        filename_slug = slugify(title)
        output_filename = os.path.join(
            output_dir, f"{output_subdir_name}_{filename_slug}.md"
        )
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(front_matter + content)
        print(f"创建文件: {output_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="自动化批量拆分Markdown文件（根据一级标题）。"
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        default="tutorial/cleaned_parents",
        help="待拆分的Markdown文件路径或包含Markdown文件的目录",
    )
    parser.add_argument(
        "--output_base_dir",
        type=str,
        default="tutorial/chunks",
        help="输出子文档的基础根目录",
    )

    args = parser.parse_args()

    input_path = args.input
    output_base = args.output_base_dir

    if os.path.isfile(input_path):
        split_markdown_file_into_subdocuments(input_path, output_base)
    elif os.path.isdir(input_path):
        print(f"开始批量处理目录: {input_path}")
        md_files = glob.glob(os.path.join(input_path, "*.md"))
        if not md_files:
            print(f"在目录 {input_path} 中未找到任何 .md 文件。")
        else:
            for md_file in md_files:
                print(f"\n处理文件: {md_file}")
                split_markdown_file_into_subdocuments(md_file, output_base)
    else:
        print(f"错误: 输入路径 '{input_path}' 不存在。")
