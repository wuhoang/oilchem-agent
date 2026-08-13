"""
数据库管理端点。

通过 FastAPI 依赖注入使用 SQLAlchemy 异步会话，
对 Experiment / Sample / Device 三张业务表提供 CRUD 操作。
所有数据持久化到 SQLite，进程重启不丢失。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.tables import Experiment, Sample, Device

router = APIRouter(tags=["db"])

# 表名 → ORM 模型映射
_TABLE_MAP: dict[str, type] = {
    "experiments": Experiment,
    "samples": Sample,
    "devices": Device,
}

# 每个表的主键字段名
_PK_MAP: dict[str, str] = {
    "experiments": "id",
    "samples": "code",
    "devices": "id",
}


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    q: str | None = Field(default=None, description="搜索关键字（对 name/operator 等文本列做包含匹配）")
    limit: int = Field(default=200, ge=1, le=1000, description="返回行数上限")


class InsertRequest(BaseModel):
    row: dict[str, Any] = Field(..., description="要插入的一行数据")


class UpdateRequest(BaseModel):
    row: dict[str, Any] = Field(..., description="要更新的一行数据（需包含主键字段）")


class GenericResponse(BaseModel):
    success: bool = True
    table: str
    data: Any = None
    message: str = ""


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _resolve_model(table: str):
    """根据表名解析 ORM 模型，不存在时抛 404。"""
    model = _TABLE_MAP.get(table)
    if model is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown table: {table}. Available: {list(_TABLE_MAP.keys())}",
        )
    return model


def _get_pk_field(table: str) -> str:
    return _PK_MAP.get(table, "id")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """将 ORM 实例转为其公开列的字典。"""
    if row is None:
        return {}
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
    }


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.get("/db/tables")
async def list_tables(db: AsyncSession = Depends(get_db)) -> dict:
    """列出所有业务表及其当前行数。"""
    tables = []
    for name, model in _TABLE_MAP.items():
        result = await db.execute(select(model))
        count = len(result.scalars().all())
        tables.append({"name": name, "count": count})
    logger.bind(component="db").debug("Listed {} tables", len(tables))
    return {"tables": tables}


@router.post("/db/{table}/query")
async def query_table(
    table: str,
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericResponse:
    """查询指定表的数据，支持关键词搜索。"""
    model = _resolve_model(table)
    pk = _get_pk_field(table)

    stmt = select(model)
    rows_orm = (await db.execute(stmt)).scalars().all()

    rows = [_row_to_dict(r) for r in rows_orm]

    # 关键词搜索：所有文本字段包含匹配
    if req.q:
        q_lower = req.q.lower()
        rows = [
            r for r in rows
            if any(q_lower in str(v).lower() for v in r.values())
        ]

    logger.bind(component="db").info(
        "Query table={} q={} matched={}", table, req.q, len(rows)
    )
    return GenericResponse(
        table=table,
        data=rows[: req.limit],
        message=f"Returned {min(len(rows), req.limit)} rows",
    )


@router.post("/db/{table}/insert")
async def insert_row(
    table: str,
    req: InsertRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericResponse:
    """向指定表插入一行数据，持久化到数据库。"""
    model = _resolve_model(table)
    pk = _get_pk_field(table)

    new_row = dict(req.row)

    # 检查主键是否已存在
    if pk in new_row and new_row[pk]:
        existing = await db.get(model, new_row[pk])
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Row with {pk}={new_row[pk]} already exists in {table}",
            )

    instance = model(**new_row)
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    logger.bind(component="db").info(
        "Inserted row into {}: pk={}", table, getattr(instance, pk, "?")
    )
    return GenericResponse(
        table=table,
        data=_row_to_dict(instance),
        message="Row inserted successfully",
    )


@router.post("/db/{table}/update")
async def update_row(
    table: str,
    req: UpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericResponse:
    """按主键更新一行数据。"""
    model = _resolve_model(table)
    pk = _get_pk_field(table)
    row_data = dict(req.row)

    pk_value = row_data.get(pk)
    if pk_value is None:
        raise HTTPException(
            status_code=400,
            detail=f"Missing primary key field '{pk}' in request body",
        )

    instance = await db.get(model, pk_value)
    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Row with {pk}={pk_value} not found in {table}",
        )

    for key, value in row_data.items():
        if hasattr(instance, key):
            setattr(instance, key, value)

    await db.commit()
    await db.refresh(instance)

    logger.bind(component="db").info(
        "Updated row in {}: pk={}", table, pk_value
    )
    return GenericResponse(
        table=table,
        data=_row_to_dict(instance),
        message="Row updated successfully",
    )


@router.delete("/db/{table}/delete")
async def delete_row(
    table: str,
    id_value: str,
    db: AsyncSession = Depends(get_db),
) -> GenericResponse:
    """按主键删除一行。"""
    model = _resolve_model(table)
    pk = _get_pk_field(table)

    instance = await db.get(model, id_value)
    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Row with {pk}={id_value} not found in {table}",
        )

    await db.delete(instance)
    await db.commit()

    logger.bind(component="db").warning(
        "Deleted row from {}: pk={}", table, id_value
    )
    return GenericResponse(
        table=table,
        data=None,
        message=f"Row {id_value} deleted from {table}",
    )


__all__ = ["router"]
