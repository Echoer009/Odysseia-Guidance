-- =================================================================
--  向量数据库专用初始化脚本 (最终版)
--  Schema: world_book_vectors, forum_vectors
--  数据类型: halfvec(3072) for storage efficiency
--  索引: HNSW + Cosine Similarity for semantic search
-- =================================================================

-- 1. 确保插件已启用
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 为不同来源的向量创建独立的 Schemas
CREATE SCHEMA IF NOT EXISTS world_book_vectors; -- 存放通用知识和社区成员
CREATE SCHEMA IF NOT EXISTS forum_vectors;      -- 存放论坛帖子数据


-- =================================================================
--  库 1: 世界书向量 (World Book Vectors)
--  源: data/chroma_db -> collection "world_book"
-- =================================================================

DROP TABLE IF EXISTS world_book_vectors.vectors CASCADE;

CREATE TABLE world_book_vectors.vectors (
    id VARCHAR(255) PRIMARY KEY,
    document TEXT,
    metadata JSONB,
    embedding halfvec(3072)
);

-- 使用半精度浮点数和余弦相似度创建 HNSW 索引
-- m = 16, ef_construction = 64 是推荐的通用参数
CREATE INDEX ON world_book_vectors.vectors 
USING HNSW (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);


-- =================================================================
--  库 2: 论坛向量 (Forum Vectors)
--  源: data/forum_chroma_db -> collection "forum_threads"
-- =================================================================

DROP TABLE IF EXISTS forum_vectors.vectors CASCADE;

CREATE TABLE forum_vectors.vectors (
    id VARCHAR(255) PRIMARY KEY,
    document TEXT,
    metadata JSONB,
    embedding halfvec(3072)
);

-- 使用相同的优化参数
CREATE INDEX ON forum_vectors.vectors 
USING HNSW (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);
