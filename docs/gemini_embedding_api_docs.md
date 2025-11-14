# Gemini API Embeddings 文档

## 概述

Embeddings（嵌入）是将文本输入转换为数值表示形式（向量）的技术。这种数值表示形式可用于多种场景，例如：

*   **信息检索 (Retrieval)**：通过比较查询向量和文档向量的相似度来查找相关信息。
*   **聚类 (Clustering)**：将相似的文本分组。
*   **相似度衡量 (Similarity Measurement)**：计算两个文本片段在语义上的接近程度。

与生成新内容的模型不同，Gemini Embedding 模型专门用于将输入数据转换为数值表示。

**使用策略**：用户需要对输入的数据和生成的嵌入内容负责，并应遵守 Google 的《使用限制政策》和《服务条款》。

---

## API 方法

Gemini API 提供了三种主要的方法来生成文本嵌入：

1.  **`models.embedContent`**：为单个输入内容生成嵌入（同步）。
2.  **`models.batchEmbedContents`**：为一批输入内容生成嵌入（同步）。
3.  **`models.asyncBatchEmbedContent`**：异步处理一批嵌入请求，适用于大规模数据处理。

### 1. `models.embedContent` (单个嵌入)

此方法用于从单个输入 `Content` 生成文本嵌入向量。

*   **端点**: `POST https://generativelanguage.googleapis.com/v1beta/{model=models/*}:embedContent`
*   **路径参数**:
    *   `model` (string, 必需): 模型的资源名称，例如 `models/embedding-001`。
*   **请求正文 (JSON)**:
    ```json
    {
      "content": {
        "parts": [
          {
            "text": "你的文本内容"
          }
        ]
      },
      "taskType": "RETRIEVAL_DOCUMENT",
      "title": "你的文本标题",
      "outputDimensionality": 256
    }
    ```
*   **关键字段**:
    *   `content` (Content, 必需): 要嵌入的内容。
    *   `taskType` (TaskType, 可选): 嵌入的预期用途。这是非常重要的参数，可以显著提升特定场景下的嵌入质量。
    *   `title` (string, 可选): 文本的标题。**仅在 `taskType` 为 `RETRIEVAL_DOCUMENT` 时适用**，提供 `title` 可以获得更高质量的检索嵌入。
    *   `outputDimensionality` (integer, 可选): 指定输出嵌入的维度。如果设置，向量会从末尾被截断。
*   **响应正文**:
    *   返回一个 `EmbedContentResponse` 对象，其中包含 `embedding` 字段。

---

### 2. `models.batchEmbedContents` (同步批量嵌入)

此方法用于一次性为多个输入内容生成嵌入向量。

*   **端点**: `POST https://generativelanguage.googleapis.com/v1beta/{model=models/*}:batchEmbedContents`
*   **请求正文 (JSON)**:
    ```json
    {
      "requests": [
        {
          "model": "models/embedding-001",
          "content": { "parts": [{ "text": "文本1" }] }
        },
        {
          "model": "models/embedding-001",
          "content": { "parts": [{ "text": "文本2" }] }
        }
      ]
    }
    ```
*   **关键字段**:
    *   `requests` (array, 必需): 一个 `EmbedContentRequest` 对象的数组。
*   **响应正文**:
    *   返回一个包含 `embeddings` 数组的对象，数组中的每个 `ContentEmbedding` 对象与请求中的顺序一一对应。

---

### 3. `models.asyncBatchEmbedContent` (异步批量嵌入)

将一批嵌入请求加入队列进行异步处理。这适用于不需要立即获得结果的大规模数据处理任务。

*   **端点**: `POST https://generativelanguage.googleapis.com/v1beta/{batch.model=models/*}:asyncBatchEmbedContent`
*   **请求正文**: 包含批处理的配置，例如用户定义的名称 (`displayName`) 和输入配置 (`inputConfig`)。
*   **响应正文**:
    *   如果成功，会立即返回一个 `Operation` 实例，你可以用它来跟踪批处理任务的状态。

---

## 关键数据结构

### `ContentEmbedding`

表示一个嵌入向量。

*   **JSON 结构**:
    ```json
    {
      "values": [ 0.01, 0.02, ... ]
    }
    ```
*   **字段**:
    *   `values` (array of numbers): 包含嵌入值的浮点数列表。

### `TaskType` (任务类型)

这是一个枚举类型，用于指定嵌入将用于何种任务，以优化其性能。

*   **常用值**:
    *   `RETRIEVAL_QUERY`: 用于**检索查询**的文本。
    *   `RETRIEVAL_DOCUMENT`: 用于被检索的**文档**。
    *   `SEMANTIC_SIMILARITY`: 用于语义相似度比较 (STS)。
    *   `CLASSIFICATION`: 用于文本分类。
    *   `CLUSTERING`: 用于文本聚类。
    *   `QUESTION_ANSWERING`: 用于问答。

**注意**: 正确设置 `TaskType` 对于获得高质量的嵌入至关重要，尤其是在构建检索系统（如RAG）时，应明确区分查询和文档。