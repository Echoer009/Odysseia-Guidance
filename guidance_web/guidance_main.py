# ### (学习后可删除) ###
# 这行注释告诉 Python 解释器，这个文件应该使用 UTF-8 编码来解析。
# UTF-8 是一个通用的字符编码，可以表示几乎所有的字符，避免出现乱码问题。
# -*- coding: utf-8 -*-

# ### (学习后可删除) ###
# --- 模块导入区 ---
# `logging`: Python 内置的日志库，用于在程序运行时记录信息、警告或错误。
# `FastAPI`: 我们用来构建 API 的核心框架。
# `Depends`: FastAPI 的依赖注入函数，帮助我们管理像数据库连接这样的共享资源。
# `Session`: SQLAlchemy 库中的一个类，代表与数据库的一次会话（连接）。
import logging
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# 这是一个被注释掉的导入语句，它提示我们未来需要一个管理数据库连接的文件。
# from .database.manager import get_db_session

# 从我们项目内部的其他文件中导入我们自己编写的类。
# `GuidanceRepository`: 数据仓库类，负责直接与数据库进行交互（增删改查）。
# `GuidanceService`: 服务类，负责处理业务逻辑。它会调用 Repository 来操作数据。
from guidance_web.database.repository import GuidanceRepository
from guidance_web.services.guidance_service import GuidanceService

# --- FastAPI 应用初始化 ---
# ### (学习后可删除) ###
# `app = FastAPI(...)` 创建了我们整个后端服务的核心实例。
# 我们可以为它提供一些元数据（metadata），比如标题、描述和版本号。
# 这些信息会自动显示在 FastAPI 生成的 API 文档页面中（例如 /docs）。
app = FastAPI(
    title="Guidance Web Service",
    description="为网页版引导功能提供后端API服务。",
    version="0.1.0",
)

# ### (学习后可删除) ###
# --- 日志配置 ---
# `logging.basicConfig(...)` 是一个快速配置日志基本设置的方法。
# `level=logging.INFO` 表示只有级别为 INFO 或更高级别（如 WARNING, ERROR）的日志才会被显示。
# `log = logging.getLogger(__name__)` 获取一个日志记录器实例。
# 使用 `__name__` (当前模块的名称) 是一个好习惯，可以让我们知道日志是从哪个文件里打印出来的。
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# ### (学习后可删除) ###
# --- 依赖注入 (Dependency Injection) ---
# 依赖注入是 FastAPI 的一个强大功能。简单来说，就是把一个函数所依赖的对象（比如数据库连接）
# 作为参数“传递”给它，而不是在函数内部去创建这个对象。
# 这样做的好处是代码解耦，更容易测试和维护。


# 这个函数 `get_db_session` 是一个依赖项提供者（Dependency Provider）。
# 它的作用是提供一个数据库会话。
def get_db_session():
    # ### (学习后可删除) ###
    # 这段代码目前是一个“占位符”，它并没有真正地连接到数据库。
    # `db = None` 初始化了一个空变量。
    # `try...finally` 结构确保了无论中间发生什么，`finally` 块中的代码总会被执行。
    # `yield db` 是关键。它将 `db` 的值（目前是 None）“产出”给需要它的函数。
    # 当请求处理完毕后，代码会回到这里继续执行 `finally` 块。
    # 这是一个标准的资源管理模式，确保像数据库连接这样的资源在使用完毕后能被正确关闭。
    db = None
    try:
        log.info("（占位）获取数据库会话。")
        yield db
    finally:
        if db:
            log.info("（占位）关闭数据库会话。")
            db.close()


def get_guidance_repository(
    # ### (学习后可删除) ###
    # `db: Session = Depends(get_db_session)` 这行代码告诉 FastAPI：
    # 1. `get_guidance_repository` 函数依赖于一个数据库会话 `db`。
    # 2. 要获取这个 `db`，请调用 `get_db_session` 函数。
    # 3. FastAPI 会自动执行 `get_db_session`，并将 `yield` 出来的值赋给 `db`。
    # `-> GuidanceRepository`: 这是一个类型提示，表示这个函数会返回一个 `GuidanceRepository` 类的实例。
    db: Session = Depends(get_db_session),
) -> GuidanceRepository:
    """依赖项：创建 GuidanceRepository 实例。"""
    # 这里我们用从依赖注入中获得的数据库会话 `db` 来创建一个 `GuidanceRepository` 实例。
    return GuidanceRepository(db)


def get_guidance_service(
    # ### (学习后可删除) ###
    # 这是一个链式依赖。
    # `get_guidance_service` 依赖于 `repo`。
    # 要获取 `repo`，FastAPI 会调用 `get_guidance_repository`。
    # 而 `get_guidance_repository` 又依赖于 `get_db_session`。
    # FastAPI 会自动处理这个依赖链，确保所有依赖项都按正确的顺序被创建和注入。
    repo: GuidanceRepository = Depends(get_guidance_repository),
) -> GuidanceService:
    """依赖项：创建 GuidanceService 实例。"""
    # 用注入的 `repo` 实例来创建 `GuidanceService` 实例。
    # 这就是分层架构的体现：Service 层依赖于 Repository 层。
    return GuidanceService(repo)


# --- API 路由定义 ---
# ### (学习后可删除) ###
# `@app.on_event(...)` 是一个事件处理器。
# FastAPI 应用在生命周期中有两个主要事件："startup" (启动时) 和 "shutdown" (关闭时)。
@app.on_event("startup")
async def startup_event():
    # 这个函数会在 FastAPI 服务启动时被调用一次。
    # 通常用于执行一些初始化操作，比如检查数据库连接、加载配置等。
    log.info("Guidance Web Service 正在启动...")
    # 被注释掉的代码 `await database.connect()` 是一个例子，展示了如何在这里连接数据库。


@app.on_event("shutdown")
async def shutdown_event():
    # 这个函数会在 FastAPI 服务正常关闭时被调用一次。
    # 通常用于执行清理操作，比如断开数据库连接。
    log.info("Guidance Web Service 正在关闭...")


@app.get("/")
# ### (学习后可删除) ###
# `@app.get("/")` 是一个路径操作装饰器（Path Operation Decorator）。
# 它告诉 FastAPI，当收到一个指向根路径 `/` 的 HTTP GET 请求时，
# 应该调用下面的 `read_root` 函数来处理它。
# `async def` 表示这是一个异步函数，适合处理 I/O 密集型任务（如网络请求）。
async def read_root():
    """根路径，用于健康检查。"""
    # 这个函数返回一个 JSON 对象。FastAPI 会自动将其转换为正确的 HTTP 响应。
    # 这个路径通常用来检查服务是否正在正常运行。
    return {"status": "ok", "message": "Welcome to the Guidance Web Service!"}


# ### (学习后可删除) ###
# 这些注释是写给开发者的提示，说明了未来应该在哪里添加新的 API 代码。
# --- 在这里添加与引导功能相关的 API 路由 ---
# 例如:
#
# @app.get("/api/progress/{user_id}")
# async def get_user_progress(
#     user_id: int,
#     service: GuidanceService = Depends(get_guidance_service)
# ):
#     """获取指定用户的引导进度。"""
#     progress = await service.get_guidance_status_for_user(user_id)
#     return progress

# --- 认证相关的路由将在这里添加 ---
# 例如:
# @app.post("/api/token")
# ...
