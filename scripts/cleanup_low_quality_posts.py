# -*- coding: utf-8 -*-
"""
低质量帖子清理脚本

用于排查和删除没有实际内容的帖子，例如：
- 标题很短
- 没有内容
- 内容只有标点符号

使用方法：
    python scripts/cleanup_low_quality_posts.py
"""

import asyncio
import logging
import sys
import os
from typing import Optional, List, Dict, Any
from sqlalchemy import text

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.database import AsyncSessionLocal

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


class LowQualityPostCleaner:
    """低质量帖子清理器"""

    def __init__(self):
        self.config = {
            "title_max_length": 5,  # 标题最大长度（小于等于此值视为短标题）
            "content_min_length": 5,  # 内容最小长度（小于此值视为无内容）
            "limit": 20,  # 每次查询返回的最大数量
            "content_preview_length": 150,  # 内容预览长度
        }
        self.pending_deletes: List[Dict[str, Any]] = []  # 待删除的帖子列表
        self.last_results: List[Dict[str, Any]] = []  # 上次查询结果

    def print_config(self):
        """打印当前配置"""
        print("\n📋 当前配置:")
        print(f"  - 短标题阈值: ≤ {self.config['title_max_length']} 字符")
        print(f"  - 最小内容长度: {self.config['content_min_length']} 字符")
        print(f"  - 每页显示数量: {self.config['limit']}")
        print(f"  - 内容预览长度: {self.config['content_preview_length']}")

    async def find_short_title_posts(
        self, max_length: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """查找标题很短的帖子"""
        max_len = max_length or self.config["title_max_length"]
        limit = self.config["limit"]

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT 
                        thread_id,
                        thread_name,
                        author_name,
                        category_name,
                        created_at,
                        guild_id,
                        content,
                        LENGTH(thread_name) as title_length,
                        LENGTH(content) as content_length
                    FROM forum.forum_threads
                    WHERE LENGTH(thread_name) <= :max_length
                    ORDER BY LENGTH(thread_name) ASC, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"max_length": max_len, "limit": limit},
            )
            rows = result.fetchall()
            self.last_results = [dict(row._mapping) for row in rows]
            return self.last_results

    async def find_empty_content_posts(
        self, min_length: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """查找内容为空或很短的帖子"""
        min_len = min_length or self.config["content_min_length"]
        limit = self.config["limit"]

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT 
                        thread_id,
                        thread_name,
                        author_name,
                        category_name,
                        created_at,
                        guild_id,
                        LENGTH(thread_name) as title_length,
                        LENGTH(content) as content_length,
                        content
                    FROM forum.forum_threads
                    WHERE content IS NULL OR LENGTH(TRIM(content)) < :min_length
                    ORDER BY LENGTH(content) ASC NULLS FIRST, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"min_length": min_len, "limit": limit},
            )
            rows = result.fetchall()
            self.last_results = [dict(row._mapping) for row in rows]
            return self.last_results

    async def find_punctuation_only_posts(self) -> List[Dict[str, Any]]:
        """查找内容只有标点符号的帖子"""
        limit = self.config["limit"]

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT 
                        thread_id,
                        thread_name,
                        author_name,
                        category_name,
                        created_at,
                        guild_id,
                        LENGTH(thread_name) as title_length,
                        LENGTH(content) as content_length,
                        content
                    FROM forum.forum_threads
                    WHERE content IS NOT NULL 
                        AND LENGTH(TRIM(content)) > 0
                        AND LENGTH(REGEXP_REPLACE(content, '[^\\w\\u4e00-\\u9fff]', '', 'g')) = 0
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            rows = result.fetchall()
            self.last_results = [dict(row._mapping) for row in rows]
            return self.last_results

    async def find_by_custom_query(
        self, title_pattern: Optional[str] = None, content_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """使用自定义模式查找帖子"""
        limit = self.config["limit"]

        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if title_pattern:
            conditions.append("thread_name LIKE :title_pattern")
            params["title_pattern"] = f"%{title_pattern}%"

        if content_pattern:
            conditions.append("content LIKE :content_pattern")
            params["content_pattern"] = f"%{content_pattern}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT 
                        thread_id,
                        thread_name,
                        author_name,
                        category_name,
                        created_at,
                        guild_id,
                        LENGTH(thread_name) as title_length,
                        LENGTH(content) as content_length,
                        content
                    FROM forum.forum_threads
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            rows = result.fetchall()
            self.last_results = [dict(row._mapping) for row in rows]
            return self.last_results

    async def get_post_by_id(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取帖子详情"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT 
                        thread_id,
                        thread_name,
                        author_name,
                        author_id,
                        category_name,
                        created_at,
                        guild_id,
                        content,
                        LENGTH(thread_name) as title_length,
                        LENGTH(content) as content_length
                    FROM forum.forum_threads
                    WHERE thread_id = :thread_id
                    """
                ),
                {"thread_id": thread_id},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None

    async def delete_post(self, thread_id: int) -> bool:
        """删除指定帖子"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM forum.forum_threads WHERE thread_id = :thread_id"),
                {"thread_id": thread_id},
            )
            await session.commit()
            return True

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        async with AsyncSessionLocal() as session:
            # 总数
            total_result = await session.execute(
                text("SELECT COUNT(*) FROM forum.forum_threads")
            )
            total = total_result.scalar()

            # 短标题数量
            short_title_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM forum.forum_threads WHERE LENGTH(thread_name) <= :max_len"
                ),
                {"max_len": self.config["title_max_length"]},
            )
            short_title_count = short_title_result.scalar()

            # 空内容数量
            empty_content_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM forum.forum_threads WHERE content IS NULL OR LENGTH(TRIM(content)) < :min_len"
                ),
                {"min_len": self.config["content_min_length"]},
            )
            empty_content_count = empty_content_result.scalar()

            return {
                "total": total,
                "short_title_count": short_title_count,
                "empty_content_count": empty_content_count,
            }

    def print_post_list(
        self,
        posts: List[Dict[str, Any]],
        show_content: bool = True,
        show_index: bool = True,
    ):
        """打印帖子列表"""
        if not posts:
            print("\n❌ 没有找到符合条件的帖子")
            return

        preview_len = self.config["content_preview_length"]
        print(f"\n✅ 找到 {len(posts)} 条帖子:")
        print("=" * 80)

        for i, post in enumerate(posts, 1):
            thread_id = post.get("thread_id", "N/A")
            thread_name = post.get("thread_name", "未知标题")
            author_name = post.get("author_name", "未知作者")
            category_name = post.get("category_name", "未知分类")
            created_at = post.get("created_at")
            guild_id = post.get("guild_id", "N/A")
            title_length = post.get("title_length", 0)
            content_length = post.get("content_length", 0)

            # 格式化时间
            if created_at:
                if isinstance(created_at, str):
                    created_str = created_at[:19]
                else:
                    created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_str = "N/A"

            # 构建链接
            if guild_id and thread_id:
                thread_url = f"https://discord.com/channels/{guild_id}/{thread_id}"
            else:
                thread_url = "N/A"

            # 索引号（用于快速操作）
            if show_index:
                print(f"\n[{i}] ID: {thread_id}")
            else:
                print(f"\n📌 ID: {thread_id}")

            print(f"  📖 标题 ({title_length}字): {thread_name}")
            print(f"  👤 作者: {author_name} | 📂 分类: {category_name}")
            print(
                f"  📅 时间: {created_str} | 📝 内容: {content_length if content_length else 0}字"
            )
            print(f"  🔗 {thread_url}")

            if show_content:
                content = post.get("content", "")
                if content:
                    # 显示预览
                    preview = content[:preview_len].replace("\n", " ")
                    if len(content) > preview_len:
                        preview += "..."
                    print(f"  📄 内容: {preview}")
                else:
                    print("  📄 内容: (空)")

            print("-" * 80)

    def add_to_pending(self, post: Dict[str, Any]):
        """添加到待删除列表"""
        thread_id = post.get("thread_id")
        if thread_id and not any(
            p.get("thread_id") == thread_id for p in self.pending_deletes
        ):
            self.pending_deletes.append(post)
            print(f"  ✅ 已添加到待删除列表: {thread_id}")
        else:
            print(f"  ⚠️ 帖子 {thread_id} 已在待删除列表中")

    def add_to_pending_by_index(self, index: int) -> bool:
        """通过索引添加到待删除列表"""
        if not self.last_results:
            print("  ⚠️ 没有可用的查询结果，请先执行查询命令")
            return False
        if index < 1 or index > len(self.last_results):
            print(f"  ⚠️ 无效的索引: {index} (有效范围: 1-{len(self.last_results)})")
            return False
        post = self.last_results[index - 1]
        self.add_to_pending(post)
        return True

    def print_pending_deletes(self):
        """打印待删除列表"""
        if not self.pending_deletes:
            print("\n📋 待删除列表为空")
            return

        print(f"\n📋 待删除列表 ({len(self.pending_deletes)} 条):")
        print("=" * 60)
        for i, post in enumerate(self.pending_deletes, 1):
            thread_id = post.get("thread_id")
            thread_name = post.get("thread_name", "未知")
            content_len = post.get("content_length", 0)
            print(f"  {i}. [{thread_id}] {thread_name[:25]}... ({content_len}字)")
        print("=" * 60)

    async def execute_pending_deletes(self):
        """执行待删除列表中的所有删除操作"""
        if not self.pending_deletes:
            print("\n⚠️ 待删除列表为空")
            return

        print(f"\n⚠️ 即将删除 {len(self.pending_deletes)} 条帖子:")
        self.print_pending_deletes()

        confirm = input("\n确认删除? (输入 'yes' 确认): ").strip().lower()
        if confirm != "yes":
            print("❌ 已取消删除")
            return

        deleted = 0
        failed = 0
        for post in self.pending_deletes:
            thread_id = post.get("thread_id")
            if thread_id is None:
                continue
            try:
                await self.delete_post(thread_id)
                deleted += 1
                print(f"  ✅ 已删除: {thread_id}")
            except Exception as e:
                failed += 1
                print(f"  ❌ 删除失败: {thread_id} - {e}")

        self.pending_deletes = []
        print(f"\n✅ 删除完成: 成功 {deleted} 条, 失败 {failed} 条")

    async def interactive_review(self, posts: List[Dict[str, Any]]):
        """交互式审核帖子"""
        if not posts:
            return

        self.print_post_list(posts, show_content=True, show_index=True)
        print(
            f"\n💡 提示: 输入序号(1-{len(posts)})添加到待删除列表，输入 'a' 添加全部，'q' 退出审核"
        )

        while True:
            try:
                choice = input("\n选择操作 > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break

            if choice == "q":
                break
            elif choice == "a":
                for post in posts:
                    self.add_to_pending(post)
                print(f"\n✅ 已添加 {len(posts)} 条帖子到待删除列表")
                break
            else:
                try:
                    index = int(choice)
                    self.add_to_pending_by_index(index)
                except ValueError:
                    print("  ⚠️ 无效输入，请输入序号、'a' 或 'q'")


def print_help():
    """打印帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        低质量帖子清理工具                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 查询命令:                                                                     ║
║   /short [长度]         - 查找标题很短的帖子 (默认 ≤5 字符)                     ║
║   /empty [长度]         - 查找内容为空的帖子 (默认 <5 字符)                     ║
║   /punctuation          - 查找内容只有标点符号的帖子                            ║
║   /find <标题> [内容]    - 使用自定义模式查找帖子                               ║
║   /view <thread_id>     - 查看帖子完整内容                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 删除操作:                                                                     ║
║   /del <thread_id>      - 直接删除指定帖子                                     ║
║   /add <thread_id|序号> - 添加帖子到待删除列表                                  ║
║   /addall               - 将上次查询结果全部添加到待删除列表                     ║
║   /pending              - 查看待删除列表                                        ║
║   /clear                - 清空待删除列表                                        ║
║   /execute              - 执行待删除列表中的所有删除                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 其他命令:                                                                     ║
║   /stats                - 查看统计信息                                          ║
║   /config               - 查看当前配置                                          ║
║   /set <参数> <值>      - 修改配置参数                                          ║
║   /help                 - 显示此帮助信息                                        ║
║   /quit 或 /exit        - 退出程序                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 可配置参数:                                                                   ║
║   title_max_length      - 短标题阈值 (默认: 5)                                  ║
║   content_min_length    - 最小内容长度 (默认: 5)                                ║
║   limit                 - 每页显示数量 (默认: 20)                               ║
║   content_preview_length- 内容预览长度 (默认: 150)                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


async def main():
    """主函数"""
    print("\n🚀 低质量帖子清理工具")
    print("=" * 50)

    cleaner = LowQualityPostCleaner()

    # 检查数据库连接
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        print("  ✅ 数据库连接正常")
    except Exception as e:
        print(f"  ❌ 数据库连接失败: {e}")
        return

    cleaner.print_config()
    print_help()

    while True:
        try:
            user_input = input("\n🔧 请输入命令 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见!")
            break

        if not user_input:
            continue

        # 解析命令
        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0].lower()

            if cmd in ["/quit", "/exit"]:
                if cleaner.pending_deletes:
                    print(f"⚠️ 还有 {len(cleaner.pending_deletes)} 条帖子待删除")
                    confirm = input("确认退出? (输入 'yes' 确认): ").strip().lower()
                    if confirm != "yes":
                        continue
                print("👋 再见!")
                break

            elif cmd == "/help":
                print_help()

            elif cmd == "/config":
                cleaner.print_config()

            elif cmd == "/stats":
                stats = await cleaner.get_stats()
                print("\n📊 统计信息:")
                print(f"  - 帖子总数: {stats['total']}")
                print(f"  - 短标题帖子数: {stats['short_title_count']}")
                print(f"  - 空内容帖子数: {stats['empty_content_count']}")

            elif cmd == "/set":
                if len(parts) < 3:
                    print("⚠️ 用法: /set <参数> <值>")
                    continue
                param = parts[1]
                try:
                    value = int(parts[2])
                    if param in cleaner.config:
                        cleaner.config[param] = value
                        print(f"✅ 已设置 {param} = {value}")
                    else:
                        print(f"⚠️ 未知参数: {param}")
                except ValueError:
                    print(f"⚠️ 无效的值: {parts[2]}")

            elif cmd == "/short":
                max_length = None
                if len(parts) >= 2:
                    try:
                        max_length = int(parts[1])
                    except ValueError:
                        print(f"⚠️ 无效的长度: {parts[1]}")
                        continue
                posts = await cleaner.find_short_title_posts(max_length)
                await cleaner.interactive_review(posts)

            elif cmd == "/empty":
                min_length = None
                if len(parts) >= 2:
                    try:
                        min_length = int(parts[1])
                    except ValueError:
                        print(f"⚠️ 无效的长度: {parts[1]}")
                        continue
                posts = await cleaner.find_empty_content_posts(min_length)
                await cleaner.interactive_review(posts)

            elif cmd == "/punctuation":
                posts = await cleaner.find_punctuation_only_posts()
                await cleaner.interactive_review(posts)

            elif cmd == "/find":
                if len(parts) < 2:
                    print("⚠️ 用法: /find <标题关键词> [内容关键词]")
                    continue
                title_pattern = parts[1]
                content_pattern = parts[2] if len(parts) >= 3 else None
                posts = await cleaner.find_by_custom_query(
                    title_pattern, content_pattern
                )
                await cleaner.interactive_review(posts)

            elif cmd == "/view":
                if len(parts) < 2:
                    print("⚠️ 用法: /view <thread_id>")
                    continue
                try:
                    thread_id = int(parts[1])
                    post = await cleaner.get_post_by_id(thread_id)
                    if post:
                        cleaner.print_post_list(
                            [post], show_content=True, show_index=False
                        )
                        # 显示完整内容
                        content = post.get("content", "")
                        if content:
                            print(f"\n📄 完整内容:\n{'-' * 40}")
                            print(content)
                            print("-" * 40)
                    else:
                        print(f"❌ 未找到帖子: {thread_id}")
                except ValueError:
                    print(f"⚠️ 无效的 thread_id: {parts[1]}")

            elif cmd == "/del":
                if len(parts) < 2:
                    print("⚠️ 用法: /del <thread_id>")
                    continue
                try:
                    thread_id = int(parts[1])
                    post = await cleaner.get_post_by_id(thread_id)
                    if not post:
                        print(f"❌ 未找到帖子: {thread_id}")
                        continue

                    print("\n⚠️ 即将删除以下帖子:")
                    cleaner.print_post_list([post], show_content=True, show_index=False)
                    confirm = input("确认删除? (输入 'yes' 确认): ").strip().lower()
                    if confirm == "yes":
                        await cleaner.delete_post(thread_id)
                        print(f"✅ 已删除帖子: {thread_id}")
                    else:
                        print("❌ 已取消删除")
                except ValueError:
                    print(f"⚠️ 无效的 thread_id: {parts[1]}")

            elif cmd == "/add":
                if len(parts) < 2:
                    print("⚠️ 用法: /add <thread_id|序号>")
                    continue
                try:
                    # 尝试作为序号处理
                    index = int(parts[1])
                    if 1 <= index <= len(cleaner.last_results):
                        cleaner.add_to_pending_by_index(index)
                    else:
                        # 作为 thread_id 处理
                        post = await cleaner.get_post_by_id(index)
                        if post:
                            cleaner.add_to_pending(post)
                        else:
                            print(f"❌ 未找到帖子: {index}")
                except ValueError:
                    print(f"⚠️ 无效的值: {parts[1]}")

            elif cmd == "/addall":
                if not cleaner.last_results:
                    print("⚠️ 没有可用的查询结果，请先执行查询命令")
                    continue
                for post in cleaner.last_results:
                    cleaner.add_to_pending(post)
                print(f"\n✅ 已添加 {len(cleaner.last_results)} 条帖子到待删除列表")

            elif cmd == "/pending":
                cleaner.print_pending_deletes()

            elif cmd == "/clear":
                cleaner.pending_deletes = []
                print("✅ 已清空待删除列表")

            elif cmd == "/execute":
                await cleaner.execute_pending_deletes()

            else:
                print(f"⚠️ 未知命令: {cmd}")
                print("   输入 /help 查看可用命令")

        else:
            print("⚠️ 请使用 / 开头的命令")
            print("   输入 /help 查看可用命令")


if __name__ == "__main__":
    asyncio.run(main())
