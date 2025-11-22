# -*- coding: utf-8 -*-
import json
import os

# 脚本将查找与自身位于同一父目录下的 `chroma_rescue_final.jsonl` 文件
script_dir = os.path.dirname(__file__)
file_path = os.path.join(script_dir, "..", "chroma_rescue_final.jsonl")

print(f"--- 正在检查文件: {os.path.abspath(file_path)} ---")

if not os.path.exists(file_path):
    print(f"错误: 找不到文件 '{file_path}'")
    exit()

with open(file_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
            metadata = data.get("metadata", "Metadata field is missing!")

            # 使用 ensure_ascii=False 以正确显示中文字符
            metadata_str = json.dumps(metadata, ensure_ascii=False)

            print(f"记录 {i} | ID: {data.get('id')} | Metadata: {metadata_str}")

            # 精确检查元数据是否为空字典
            if isinstance(metadata, dict) and not metadata:
                print("  -> 警告: 此元数据为空字典 {}，这将导致程序崩溃。")

        except Exception as e:
            print(f"记录 {i} | 解析失败: {e}")
