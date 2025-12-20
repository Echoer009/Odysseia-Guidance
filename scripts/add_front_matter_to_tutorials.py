import os

# 定义文件名到元数据的映射
# 分类方案：社区指南, 安装部署, 酒馆使用, API与模型, 高级技巧, 故障排查
metadata_map = {
    "1. 社区核心规则.md": {"category": "社区指南", "tags": ["规则", "红线", "入门"]},
    "2. 社区行政与分级.md": {
        "category": "社区指南",
        "tags": ["规则", "行政", "身份组"],
    },
    "3. 缓冲区与道馆挑战.md": {
        "category": "社区指南",
        "tags": ["准入", "验证", "规则"],
    },
    "4. 答疑区规则与规范.md": {
        "category": "社区指南",
        "tags": ["答疑", "规则", "规范"],
    },
    "5. 类脑社区频道.md": {"category": "社区指南", "tags": ["Discord", "频道", "基础"]},
    "6.社区基础技巧.md": {"category": "社区指南", "tags": ["Discord", "回顶", "下载"]},
    "7. Windows 本地部署.md": {
        "category": "安装部署",
        "tags": ["Windows", "Git", "本地"],
    },
    "8. 移动端本地部署.md": {
        "category": "安装部署",
        "tags": ["安卓", "Termux", "一键脚本"],
    },
    "9. 云端与 iOS 方案.md": {"category": "安装部署", "tags": ["云端", "iOS", "VPS"]},
    "10. 数据管理.md": {
        "category": "酒馆使用",
        "tags": ["数据", "备份", "config.yaml"],
    },
    "11. 初始运行设置.md": {"category": "酒馆使用", "tags": ["设置", "API", "新手"]},
    "12. UI 与个性化.md": {"category": "酒馆使用", "tags": ["UI", "主题", "个性化"]},
    "13. API 核心概念.md": {"category": "API与模型", "tags": ["API", "提示词", "对比"]},
    "14. DeepSeek 专项指南.md": {
        "category": "API与模型",
        "tags": ["DeepSeek", "API", "中国大陆"],
    },
    "15. Gemini API 申请.md": {
        "category": "API与模型",
        "tags": ["Gemini", "Google", "API"],
    },
    "16. Gemini 网络配置.md": {
        "category": "API与模型",
        "tags": ["Gemini", "代理", "TUN"],
    },
    "17. Claude API 专项.md": {
        "category": "API与模型",
        "tags": ["Claude", "API", "Cookie"],
    },
    "18. 反向代理 - Cli 篇.md": {
        "category": "API与模型",
        "tags": ["Gemini", "Cli", "反向代理"],
    },
    "19. 反向代理 - Build 篇.md": {
        "category": "API与模型",
        "tags": ["Gemini", "Build", "反向代理"],
    },
    "20. 角色卡管理.md": {"category": "酒馆使用", "tags": ["角色卡", "管理", "导入"]},
    "21. 预设管理.md": {"category": "高级技巧", "tags": ["预设", "参数", "破限"]},
    "22. 世界书制作入门.md": {
        "category": "高级技巧",
        "tags": ["世界书", "WI", "关键词"],
    },
    "23. 世界书逻辑进阶.md": {
        "category": "高级技巧",
        "tags": ["世界书", "逻辑", "进阶"],
    },
    "24. 酒馆宏指令系统.md": {
        "category": "高级技巧",
        "tags": ["宏指令", "变量", "自动化", "宏"],
    },
    "25. 正则表达式系统.md": {
        "category": "高级技巧",
        "tags": ["正则", "过滤", "文本处理"],
    },
    "26. 对话管理与消息编辑.md": {
        "category": "酒馆使用",
        "tags": ["对话", "管理", "存档"],
    },
    "27. 长文本总结与上下文.md": {
        "category": "酒馆使用",
        "tags": ["总结", "上下文", "Token"],
    },
    "28. 排障对照表.md": {"category": "故障排查", "tags": ["报错", "问题", "解决"]},
    "29. Odysseia-Protect 资源管理.md": {
        "category": "酒馆使用",
        "tags": ["插件", "资源", "下载"],
    },
}

target_dir = "tutorial/refined_v2"


def add_front_matter():
    for filename, meta in metadata_map.items():
        file_path = os.path.join(target_dir, filename)
        if not os.path.exists(file_path):
            print(f"Skipping: {filename} (Not found)")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if content.startswith("---"):
            print(f"Skipping: {filename} (Already has front matter)")
            continue

        # 构建 Front Matter
        tags_str = ", ".join([f'"{t}"' for t in meta["tags"]])
        front_matter = f'---\ncategory: "{meta["category"]}"\ntags: [{tags_str}]\n---\n'

        new_content = front_matter + content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Processed: {filename}")


if __name__ == "__main__":
    add_front_matter()
