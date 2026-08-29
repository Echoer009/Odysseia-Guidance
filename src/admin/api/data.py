import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import JSON, BigInteger, Integer, SmallInteger, Text, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnClause

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.utils.database import chat_db_manager
from src.database import models
from src.database.database import AsyncSessionLocal

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])


@dataclass
class FieldSpec:
    name: str
    label: str
    ftype: str
    editable: bool = False
    as_str: bool = False
    eq_int: bool = False


@dataclass
class ResourceSpec:
    name: str
    label: str
    backend: str
    model: Any = None
    table: str = ""
    pk: str = "id"
    fields: List[FieldSpec] = field(default_factory=list)
    searchable: List[str] = field(default_factory=list)
    numeric_search: List[str] = field(default_factory=list)
    sortable: List[str] = field(default_factory=list)
    default_sort: str = "id"
    default_order: str = "asc"
    delete_mode: str = "hard"
    soft_flag: str = ""
    read_only: bool = False

    @property
    def field_map(self) -> Dict[str, FieldSpec]:
        return {f.name: f for f in self.fields}

    def editable_fields(self) -> List[FieldSpec]:
        return [f for f in self.fields if f.editable]


def _pg_col_type(col: ColumnClause) -> str:
    if isinstance(col.type, (BigInteger, Integer, SmallInteger)):
        return "int"
    from sqlalchemy import DateTime

    if isinstance(col.type, DateTime):
        return "datetime"
    if isinstance(col.type, JSON):
        return "json"
    if isinstance(col.type, Text):
        return "text"
    return "string"


def _pg_resource(
    name: str,
    label: str,
    model: Any,
    labels: Dict[str, str],
    editable: Tuple[str, ...] = (),
    bool_cols: Tuple[str, ...] = (),
    datetime_editable: Tuple[str, ...] = (),
    searchable: Tuple[str, ...] = (),
    numeric_search: Tuple[str, ...] = (),
    sortable: Optional[Tuple[str, ...]] = None,
    default_sort: str = "id",
    default_order: str = "asc",
    delete_mode: str = "hard",
    soft_flag: str = "",
    read_only: bool = False,
) -> ResourceSpec:
    fields: List[FieldSpec] = []
    pk_name = "id"
    for col in model.__table__.columns:
        if "embedding" in col.name.lower():
            continue
        if col.primary_key:
            pk_name = col.name
        ftype = _pg_col_type(col)
        if col.name in bool_cols:
            ftype = "bool"
        is_editable = (not col.primary_key) and (col.name in editable)
        if ftype == "datetime" and col.name not in datetime_editable:
            is_editable = False
        fields.append(
            FieldSpec(
                name=col.name or "",
                label=str(labels.get(col.name) or col.name or ""),
                ftype=ftype,
                editable=is_editable,
                as_str=bool(col.primary_key) or isinstance(col.type, BigInteger),
                eq_int=isinstance(col.type, (BigInteger, Integer, SmallInteger)),
            )
        )
    if sortable is None:
        sortable = ("id", "created_at", "updated_at")
    valid_sortable = tuple(s for s in sortable if s in {f.name for f in fields})
    if not valid_sortable:
        valid_sortable = (pk_name,)
    return ResourceSpec(
        name=name,
        label=label,
        backend="pg",
        model=model,
        pk=pk_name,
        fields=fields,
        searchable=list(searchable),
        numeric_search=list(numeric_search),
        sortable=list(valid_sortable),
        default_sort=default_sort if default_sort in valid_sortable else pk_name,
        default_order=default_order,
        delete_mode=delete_mode,
        soft_flag=soft_flag,
        read_only=read_only,
    )


WORK_EVENT_FIELDS: List[FieldSpec] = [
    FieldSpec(name="event_id", label="ID", ftype="int", as_str=True, eq_int=True),
    FieldSpec(name="event_type", label="类型", ftype="string", editable=True),
    FieldSpec(name="name", label="名称", ftype="string", editable=True),
    FieldSpec(name="description", label="描述", ftype="text", editable=True),
    FieldSpec(name="reward_range_min", label="最小奖励", ftype="int", editable=True, eq_int=True),
    FieldSpec(name="reward_range_max", label="最大奖励", ftype="int", editable=True, eq_int=True),
    FieldSpec(name="good_event_description", label="好事件描述", ftype="text", editable=True),
    FieldSpec(name="good_event_modifier", label="好事件修正", ftype="float", editable=True),
    FieldSpec(name="bad_event_description", label="坏事件描述", ftype="text", editable=True),
    FieldSpec(name="bad_event_modifier", label="坏事件修正", ftype="float", editable=True),
    FieldSpec(name="is_enabled", label="启用", ftype="bool", editable=True),
    FieldSpec(name="custom_event_by", label="投稿者ID", ftype="int", as_str=True, eq_int=True),
]

REGISTRY: Dict[str, ResourceSpec] = {
    spec.name: spec
    for spec in [
        _pg_resource(
            "member_profiles",
            "成员档案",
            models.CommunityMemberProfile,
            {
                "id": "ID",
                "external_id": "外部ID",
                "discord_id": "Discord ID",
                "title": "头衔",
                "full_text": "档案全文",
                "source_metadata": "来源元数据",
                "created_at": "创建时间",
                "updated_at": "更新时间",
                "personal_summary": "个人记忆",
                "history": "对话历史",
                "personal_message_count": "个人消息数",
            },
            editable=(
                "external_id",
                "discord_id",
                "title",
                "full_text",
                "source_metadata",
                "personal_summary",
                "history",
                "personal_message_count",
            ),
            searchable=("external_id", "discord_id", "title"),
            numeric_search=("id", "discord_id"),
            sortable=("id", "external_id", "created_at", "updated_at", "personal_message_count"),
        ),
        _pg_resource(
            "memory_notes",
            "记忆笔记",
            models.UserMemoryNote,
            {
                "id": "ID",
                "user_id": "用户ID",
                "category": "类别",
                "content": "内容",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=("user_id", "category", "content"),
            searchable=("content", "category"),
            numeric_search=("id", "user_id"),
            sortable=("id", "user_id", "category", "created_at", "updated_at"),
        ),
        _pg_resource(
            "knowledge_documents",
            "通用知识库",
            models.GeneralKnowledgeDocument,
            {
                "id": "ID",
                "external_id": "外部ID",
                "title": "标题",
                "full_text": "全文",
                "source_metadata": "来源元数据",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=("external_id", "title", "full_text", "source_metadata"),
            searchable=("title", "external_id"),
            numeric_search=("id",),
            sortable=("id", "title", "created_at", "updated_at"),
        ),
        _pg_resource(
            "conversation_blocks",
            "对话记忆块",
            models.ConversationBlock,
            {
                "id": "ID",
                "discord_id": "用户ID",
                "conversation_text": "对话内容",
                "start_time": "开始时间",
                "end_time": "结束时间",
                "message_count": "消息数",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=("discord_id", "conversation_text", "message_count"),
            searchable=("conversation_text",),
            numeric_search=("id", "discord_id"),
            sortable=("id", "discord_id", "start_time", "end_time", "created_at", "updated_at"),
            default_order="desc",
        ),
        _pg_resource(
            "forum_threads",
            "论坛帖子",
            models.ForumThread,
            {
                "id": "ID",
                "thread_id": "帖子ID",
                "thread_name": "标题",
                "content": "内容",
                "author_id": "作者ID",
                "author_name": "作者名",
                "category_name": "分类",
                "channel_id": "频道ID",
                "guild_id": "服务器ID",
                "created_at": "发帖时间",
                "source_metadata": "来源元数据",
                "created_at_db": "入库时间",
                "updated_at": "更新时间",
            },
            editable=("thread_name", "content", "author_name", "category_name", "source_metadata"),
            searchable=("thread_name", "author_name", "category_name"),
            numeric_search=("id", "thread_id", "author_id", "channel_id", "guild_id"),
            sortable=("id", "thread_id", "thread_name", "author_name", "category_name", "created_at", "updated_at"),
        ),
        _pg_resource(
            "user_coins",
            "用户金币",
            models.UserCoins,
            {
                "id": "ID",
                "user_id": "用户ID",
                "balance": "余额",
                "last_daily_message_date": "每日奖励日期",
                "last_red_envelope_date": "红包日期",
                "coffee_effect_expires_at": "咖啡效果到期",
                "has_withered_sunflower": "枯萎向日葵",
                "blocks_thread_replies": "禁止帖子回复",
                "thread_cooldown_seconds": "冷却秒数",
                "thread_cooldown_duration": "冷却时长",
                "thread_cooldown_limit": "冷却次数",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=(
                "balance",
                "last_daily_message_date",
                "last_red_envelope_date",
                "has_withered_sunflower",
                "blocks_thread_replies",
                "thread_cooldown_seconds",
                "thread_cooldown_duration",
                "thread_cooldown_limit",
            ),
            bool_cols=("has_withered_sunflower", "blocks_thread_replies"),
            searchable=(),
            numeric_search=("id", "user_id"),
            sortable=("id", "user_id", "balance", "created_at", "updated_at"),
        ),
        _pg_resource(
            "coin_transactions",
            "金币流水",
            models.CoinTransaction,
            {
                "id": "ID",
                "user_id": "用户ID",
                "amount": "金额",
                "reason": "原因",
                "timestamp": "时间",
            },
            editable=(),
            searchable=("reason",),
            numeric_search=("id", "user_id"),
            sortable=("id", "user_id", "amount", "timestamp"),
            default_order="desc",
            read_only=True,
        ),
        _pg_resource(
            "coin_loans",
            "金币贷款",
            models.CoinLoan,
            {
                "id": "ID",
                "user_id": "用户ID",
                "amount": "金额",
                "status": "状态",
                "created_at": "借款时间",
                "paid_at": "还款时间",
            },
            editable=("status", "paid_at"),
            datetime_editable=("paid_at",),
            searchable=("status",),
            numeric_search=("id", "user_id"),
            sortable=("id", "user_id", "amount", "status", "created_at", "paid_at"),
        ),
        _pg_resource(
            "user_affection",
            "用户好感度",
            models.UserAffection,
            {
                "id": "ID",
                "user_id": "用户ID",
                "affection_points": "好感度",
                "daily_affection_gain": "今日好感增量",
                "last_update_date": "上次更新日期",
                "last_interaction_date": "上次互动日期",
                "last_gift_date": "上次送礼日期",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=("affection_points",),
            searchable=(),
            numeric_search=("id", "user_id"),
            sortable=("id", "user_id", "affection_points", "created_at", "updated_at"),
        ),
        _pg_resource(
            "user_warnings",
            "用户警告",
            models.UserWarningRecord,
            {
                "id": "ID",
                "user_id": "用户ID",
                "guild_id": "服务器ID",
                "warning_count": "警告次数",
                "updated_at": "更新时间",
            },
            editable=(),
            searchable=(),
            numeric_search=("id", "user_id", "guild_id"),
            sortable=("id", "user_id", "warning_count", "updated_at"),
            read_only=True,
        ),
        _pg_resource(
            "shop_items",
            "商店商品",
            models.ShopItem,
            {
                "id": "ID",
                "name": "名称",
                "description": "描述",
                "price": "价格",
                "category": "类别",
                "target": "目标",
                "effect_id": "效果ID",
                "cg_url": "CG链接",
                "is_available": "是否可用",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=(
                "name",
                "description",
                "price",
                "category",
                "target",
                "effect_id",
                "cg_url",
                "is_available",
            ),
            bool_cols=("is_available",),
            searchable=("name", "category"),
            numeric_search=("id",),
            sortable=("id", "name", "price", "category", "is_available", "created_at", "updated_at"),
            delete_mode="soft",
            soft_flag="is_available",
        ),
        ResourceSpec(
            name="work_events",
            label="打工事件",
            backend="sqlite",
            table="work_events",
            pk="event_id",
            fields=WORK_EVENT_FIELDS,
            searchable=["name", "description"],
            numeric_search=["event_id", "custom_event_by"],
            sortable=[
                "event_id",
                "event_type",
                "name",
                "reward_range_min",
                "reward_range_max",
                "is_enabled",
            ],
            default_sort="event_id",
            default_order="asc",
            delete_mode="soft",
            soft_flag="is_enabled",
        ),
        _pg_resource(
            "user_persona_preference",
            "人设偏好",
            models.UserPersonaPreference,
            {
                "id": "ID",
                "user_id": "用户ID",
                "persona_style": "人设风格",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            },
            editable=("persona_style",),
            searchable=("persona_style",),
            numeric_search=("id", "user_id"),
            sortable=("id", "user_id", "persona_style", "created_at", "updated_at"),
        ),
    ]
}


def _get_spec(resource: str) -> ResourceSpec:
    spec = REGISTRY.get(resource)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知的数据资源: {resource}")
    return spec


def _field_meta(spec: ResourceSpec) -> List[Dict[str, Any]]:
    return [
        {"name": f.name, "label": f.label, "type": f.ftype, "editable": f.editable}
        for f in spec.fields
    ]


def _coerce(f: FieldSpec, value: Any) -> Any:
    if value is None:
        return None
    try:
        if f.ftype == "int":
            return int(value)
        if f.ftype == "float":
            return float(value)
        if f.ftype == "bool":
            return int(bool(value))
        if f.ftype == "datetime":
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if f.ftype == "json":
            return value
        return str(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"字段 {f.name} 的取值格式无效")


def _out(f: FieldSpec, value: Any) -> Any:
    if value is None:
        return None
    if f.ftype == "datetime":
        return value.isoformat()
    if f.ftype == "bool":
        return bool(value)
    if f.as_str:
        return str(value)
    return value


def _serialize(spec: ResourceSpec, source: Any) -> Dict[str, Any]:
    if isinstance(source, dict):
        return {f.name: _out(f, source.get(f.name)) for f in spec.fields}
    return {f.name: _out(f, getattr(source, f.name, None)) for f in spec.fields}


def _validate_body(spec: ResourceSpec, body: Dict[str, Any]) -> Dict[str, Any]:
    if spec.read_only:
        raise HTTPException(status_code=400, detail="该资源只读")
    field_map = spec.field_map
    unknown = sorted(k for k in body if k not in field_map)
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"包含未知或不可编辑的字段: {', '.join(unknown)}"
        )
    values: Dict[str, Any] = {}
    for key, value in body.items():
        f = field_map[key]
        if not f.editable:
            raise HTTPException(status_code=400, detail=f"字段不可编辑: {key}")
        values[key] = _coerce(f, value)
    return values


def _parse_id(spec: ResourceSpec, record_id: str) -> int:
    try:
        return int(record_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="记录不存在")


def _sort_col(spec: ResourceSpec, sort: str, order: str):
    name = sort if sort in spec.sortable else spec.default_sort
    direction = "desc" if order == "desc" else spec.default_order
    return name, direction


async def _sqlite_exec(
    query: str, params: Tuple = (), fetch: str = "none", commit: bool = False
):
    return await chat_db_manager._execute(
        chat_db_manager._db_transaction, query, params, fetch=fetch, commit=commit
    )


def _sqlite_where(spec: ResourceSpec, q: str) -> Tuple[str, List[Any]]:
    q = (q or "").strip()
    if not q:
        return "", []
    parts: List[str] = []
    params: List[Any] = []
    like = f"%{q}%"
    field_map = spec.field_map
    for name in spec.searchable:
        parts.append(f"{name} LIKE ?")
        params.append(like)
    if q.isdigit():
        for name in spec.numeric_search:
            f = field_map[name]
            parts.append(f"{name} = ?")
            params.append(int(q) if f.eq_int else q)
    if not parts:
        return "", []
    return " WHERE " + " OR ".join(parts), params


async def _sqlite_list(
    spec: ResourceSpec, q: str, page: int, page_size: int, sort: str, order: str
) -> Tuple[List[Dict[str, Any]], int]:
    cols = ", ".join(f.name for f in spec.fields)
    where, params = _sqlite_where(spec, q)
    count_row = await _sqlite_exec(
        f"SELECT COUNT(*) AS c FROM {spec.table}{where}", tuple(params), fetch="one"
    )
    total = count_row["c"] if count_row else 0
    sort_name, direction = _sort_col(spec, sort, order)
    rows = await _sqlite_exec(
        f"SELECT {cols} FROM {spec.table}{where} ORDER BY {sort_name} {direction.upper()} LIMIT ? OFFSET ?",
        tuple(params + [page_size, (page - 1) * page_size]),
        fetch="all",
    )
    return [_serialize(spec, dict(row)) for row in rows], total


async def _sqlite_get(spec: ResourceSpec, record_id: int) -> Dict[str, Any]:
    cols = ", ".join(f.name for f in spec.fields)
    row = await _sqlite_exec(
        f"SELECT {cols} FROM {spec.table} WHERE {spec.pk} = ?", (record_id,), fetch="one"
    )
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _serialize(spec, dict(row))


def _pg_cols(spec: ResourceSpec) -> List[ColumnClause]:
    return [spec.model.__table__.columns[f.name] for f in spec.fields]


def _pg_conditions(spec: ResourceSpec, q: str):
    q = (q or "").strip()
    if not q:
        return None
    conditions = []
    for name in spec.searchable:
        conditions.append(spec.model.__table__.columns[name].ilike(f"%{q}%"))
    if q.isdigit():
        for name in spec.numeric_search:
            f = spec.field_map[name]
            conditions.append(
                spec.model.__table__.columns[name] == (int(q) if f.eq_int else q)
            )
    return or_(*conditions) if conditions else None


async def _pg_list(
    spec: ResourceSpec, q: str, page: int, page_size: int, sort: str, order: str
) -> Tuple[List[Dict[str, Any]], int]:
    conditions = _pg_conditions(spec, q)
    cols = _pg_cols(spec)
    sort_name, direction = _sort_col(spec, sort, order)
    sort_col = spec.model.__table__.columns[sort_name]
    order_clause = sort_col.desc() if direction == "desc" else sort_col.asc()
    async with AsyncSessionLocal() as session:
        count_stmt = select(func.count()).select_from(spec.model)
        if conditions is not None:
            count_stmt = count_stmt.where(conditions)
        total = (await session.execute(count_stmt)).scalar() or 0
        stmt = select(*cols)
        if conditions is not None:
            stmt = stmt.where(conditions)
        rows = (
            (await session.execute(stmt.order_by(order_clause).offset((page - 1) * page_size).limit(page_size)))
            .mappings()
            .all()
        )
    return [_serialize(spec, dict(row)) for row in rows], total


async def _pg_get_obj(spec: ResourceSpec, session, record_id: int):
    pk_col = spec.model.__table__.columns[spec.pk]
    result = await session.execute(
        select(spec.model).where(pk_col == record_id)
    )
    return result.scalar_one_or_none()


@router.get("/api/data")
async def list_resources():
    return {
        "resources": [
            {"name": s.name, "label": s.label, "read_only": s.read_only}
            for s in REGISTRY.values()
        ]
    }


@router.get("/api/data/{resource}")
async def list_items(
    resource: str,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    sort: str = "",
    order: str = "asc",
):
    spec = _get_spec(resource)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    if order not in ("asc", "desc"):
        order = "asc"
    if spec.backend == "pg":
        items, total = await _pg_list(spec, q, page, page_size, sort, order)
    else:
        items, total = await _sqlite_list(spec, q, page, page_size, sort, order)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "fields": _field_meta(spec),
    }


@router.get("/api/data/{resource}/{record_id}")
async def get_item(resource: str, record_id: str):
    spec = _get_spec(resource)
    rid = _parse_id(spec, record_id)
    if spec.backend == "sqlite":
        return await _sqlite_get(spec, rid)
    async with AsyncSessionLocal() as session:
        obj = await _pg_get_obj(spec, session, rid)
        if obj is None:
            raise HTTPException(status_code=404, detail="记录不存在")
        return _serialize(spec, obj)


@router.post("/api/data/{resource}")
async def create_item(
    resource: str, body: Dict[str, Any], user_id: int = Depends(require_admin)
):
    spec = _get_spec(resource)
    values = _validate_body(spec, body)
    if spec.backend == "sqlite":
        if not values:
            raise HTTPException(status_code=400, detail="请求体不能为空")
        cols = ", ".join(values.keys())
        marks = ", ".join(["?"] * len(values))
        try:
            new_id = await _sqlite_exec(
                f"INSERT INTO {spec.table} ({cols}) VALUES ({marks})",
                tuple(values.values()),
                fetch="lastrowid",
                commit=True,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"创建失败: {e}")
        item = await _sqlite_get(spec, int(new_id))
        await audit_log_service.log(
            user_id, "create", spec.name, str(new_id), {"values": values}
        )
        return item
    obj = spec.model(**values)
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                session.add(obj)
            await session.refresh(obj)
            item = _serialize(spec, obj)
        except SQLAlchemyError as e:
            raise HTTPException(status_code=400, detail=f"创建失败: {getattr(e, 'orig', e)}")
    pk_value = getattr(obj, spec.pk)
    await audit_log_service.log(
        user_id, "create", spec.name, str(pk_value), {"values": values}
    )
    return item


@router.put("/api/data/{resource}/{record_id}")
async def update_item(
    resource: str,
    record_id: str,
    body: Dict[str, Any],
    user_id: int = Depends(require_admin),
):
    spec = _get_spec(resource)
    values = _validate_body(spec, body)
    if not values:
        raise HTTPException(status_code=400, detail="请求体不能为空")
    rid = _parse_id(spec, record_id)
    if spec.backend == "sqlite":
        cols = ", ".join(f"{key} = ?" for key in values.keys())
        rowcount = await _sqlite_exec(
            f"UPDATE {spec.table} SET {cols} WHERE {spec.pk} = ?",
            tuple(list(values.values()) + [rid]),
            fetch="rowcount",
            commit=True,
        )
        if not rowcount:
            raise HTTPException(status_code=404, detail="记录不存在")
        item = await _sqlite_get(spec, rid)
        await audit_log_service.log(
            user_id, "update", spec.name, str(rid), {"values": values}
        )
        return item
    async with AsyncSessionLocal() as session:
        obj = await _pg_get_obj(spec, session, rid)
        if obj is None:
            raise HTTPException(status_code=404, detail="记录不存在")
        diff = {}
        for key, value in values.items():
            old = _out(spec.field_map[key], getattr(obj, key))
            diff[key] = {"old": old, "new": _out(spec.field_map[key], value)}
            setattr(obj, key, value)
        try:
            await session.commit()
            await session.refresh(obj)
            item = _serialize(spec, obj)
        except SQLAlchemyError as e:
            raise HTTPException(status_code=400, detail=f"更新失败: {getattr(e, 'orig', e)}")
    await audit_log_service.log(user_id, "update", spec.name, str(rid), diff)
    return item


@router.delete("/api/data/{resource}/{record_id}")
async def delete_item(
    resource: str, record_id: str, user_id: int = Depends(require_admin)
):
    spec = _get_spec(resource)
    if spec.read_only:
        raise HTTPException(status_code=400, detail="该资源只读")
    rid = _parse_id(spec, record_id)
    if spec.backend == "sqlite":
        if spec.delete_mode == "soft":
            rowcount = await _sqlite_exec(
                f"UPDATE {spec.table} SET {spec.soft_flag} = 0 WHERE {spec.pk} = ? AND {spec.soft_flag} != 0",
                (rid,),
                fetch="rowcount",
                commit=True,
            )
        else:
            rowcount = await _sqlite_exec(
                f"DELETE FROM {spec.table} WHERE {spec.pk} = ?",
                (rid,),
                fetch="rowcount",
                commit=True,
            )
        if not rowcount:
            raise HTTPException(status_code=404, detail="记录不存在")
        await audit_log_service.log(
            user_id, "delete", spec.name, str(rid), {"soft": spec.delete_mode == "soft"}
        )
        return {"success": True}
    async with AsyncSessionLocal() as session:
        obj = await _pg_get_obj(spec, session, rid)
        if obj is None:
            raise HTTPException(status_code=404, detail="记录不存在")
        if spec.delete_mode == "soft":
            setattr(obj, spec.soft_flag, 0)
        else:
            await session.delete(obj)
        try:
            await session.commit()
        except SQLAlchemyError as e:
            raise HTTPException(status_code=400, detail=f"删除失败: {getattr(e, 'orig', e)}")
    await audit_log_service.log(
        user_id, "delete", spec.name, str(rid), {"soft": spec.delete_mode == "soft"}
    )
    return {"success": True}
