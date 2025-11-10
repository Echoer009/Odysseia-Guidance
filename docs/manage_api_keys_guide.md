# API 密钥管理脚本使用指南 (`manage_api_keys.py`)

## 概述

`manage_api_keys.py` 是一个命令行工具，旨在帮助您管理存储在 `.env` 文件中的 Google API 密钥。它与 `key_reputations.json` 文件协同工作，允许您根据密钥的信誉分数来维护一个健康的密钥池，同时提供了添加和格式化密钥的便捷功能。

## 依赖文件

为了使脚本正常工作，请确保以下文件存在且路径正确：

1.  **`.env` 文件**: 位于项目根目录。此文件必须包含一个名为 `GOOGLE_API_KEYS_LIST` 的变量，其格式如下：
    ```env
    GOOGLE_API_KEYS_LIST="key1,key2,key3"
    ```
    或为了提高可读性（推荐）：
    ```env
    GOOGLE_API_KEYS_LIST="
    key1,
    key2,
    key3
    "
    ```

2.  **`data/key_reputations.json`**: 位于项目根目录下的 `data` 文件夹中。此文件由应用程序在运行时自动生成和更新，记录了每个API密钥的信誉分数。一个典型的条目如下：
    ```json
    {
      "YOUR_API_KEY_HERE": {
        "reputation": 100,
        "last_used": "2025-11-10T07:10:28Z"
      }
    }
    ```

---

## 核心功能与使用方法

您可以从项目根目录通过以下命令运行此脚本：

```bash
python scripts/manage_api_keys.py [command]
```

### 1. 移除低信誉分数的密钥 (默认操作)

如果您在运行时**不提供任何命令**，脚本将进入默认的交互式移除模式。

**功能描述**:
此模式会读取 `key_reputations.json` 文件，并提示您输入一个信誉分数阈值。所有低于该阈值的密钥都将从 `.env` 文件中被移除。这对于自动清理那些可能已被Google标记或限制的“不健康”密钥非常有用。

**如何使用**:

1.  打开终端，确保您位于项目根目录下。
2.  运行命令:
    ```bash
    python scripts/manage_api_keys.py
    ```
3.  脚本会首先显示当前密钥的分数分布情况。
4.  然后，它会提示您输入一个分数阈值 (例如, `10`)。
5.  脚本将列出所有分数低于该阈值的密钥，并请求您确认 (`y/n`)。
6.  确认后，这些密钥将从 `.env` 文件中被永久删除。

### 2. 检查密钥状态 (`status`)

**功能描述**:
此命令会扫描您的 `.env` 文件和信誉文件，然后显示一个关于当前密钥池健康状况的摘要，按信誉分数对密钥进行分组计数。

**如何使用**:

```bash
python scripts/manage_api_keys.py status
```

**示例输出**:
```
--- 当前密钥分数分布 ---
  - 分数: 0, 密钥数量: 2
  - 分数: 50, 密钥数量: 5
  - 分数: 100, 密钥数量: 20
-------------------------
```

### 3. 添加新密钥 (`add`)

**功能描述**:
此命令允许您安全地向 `.env` 文件中添加一个新的或多个API密钥。脚本会自动处理格式问题，并确保不会添加任何重复的密钥。

**如何使用**:

1.  运行命令:
    ```bash
    python scripts/manage_api_keys.py add
    ```
2.  脚本会提示您输入或粘贴新的密钥。您可以一次性粘贴多个密钥，它们可以由逗号、空格或换行符分隔。
3.  输入完成后，在新的一行按 `Ctrl+Z` (Windows) 或 `Ctrl+D` (Linux/macOS) 来结束输入。
4.  脚本会自动将这些新密钥添加到 `GOOGLE_API_KEYS_LIST` 中。

### 4. 重新格式化密钥 (`reformat`)

**功能描述**:
如果您的 `.env` 文件中的 `GOOGLE_API_KEYS_LIST` 是一长串单行文本，此命令可以将其重新格式化为多行，每个密钥占一行，以提高可读性。

**如何使用**:

```bash
python scripts/manage_api_keys.py reformat
```

**效果**:
*前:*
`GOOGLE_API_KEYS_LIST="key1,key2,key3,key4,key5"`

*后:*
```env
GOOGLE_API_KEYS_LIST="
key1,
key2,
key3,
key4,
key5
"
```

---

## 高级用法

### 指定不同的 `.env` 文件

如果您想对一个不位于项目根目录的特定 `.env` 文件执行操作，您可以使用 `--env-file` 标志。

**语法**:
```bash
python scripts/manage_api_keys.py [command] --env-file /path/to/your/.env
```

**示例**:
对位于 `../backup/.env.bak` 的文件执行状态检查：
```bash
python scripts/manage_api_keys.py status --env-file ../backup/.env.bak