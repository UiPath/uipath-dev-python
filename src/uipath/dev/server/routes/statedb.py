"""State database explorer API routes."""

from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

try:
    import msgpack  # type: ignore[import-untyped]

    _has_msgpack = True
except ImportError:
    _has_msgpack = False

router = APIRouter(tags=["statedb"])

DB_PATH = Path.cwd() / "__uipath" / "state.db"


def _quote_ident(name: str) -> str:
    """Quote a SQLite identifier safely using double quotes."""
    return '"' + name.replace('"', '""') + '"'


def _db_uri() -> str:
    """Return a read-only SQLite URI for the state database."""
    # Forward slashes required for SQLite URI on all platforms
    return f"file:{DB_PATH.as_posix()}?mode=ro"


def _try_decode_blob(val: bytes) -> Any:
    """Try to decode a BLOB using common serialization formats.

    Attempts (in order): JSON, msgpack, zlib+JSON, zlib+msgpack,
    UTF-8 string, base64 fallback.
    """
    # 1. Raw JSON
    try:
        return json.loads(val)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # 2. msgpack
    if _has_msgpack:
        try:
            return msgpack.unpackb(val, raw=False)
        except Exception:
            pass

    # 3. zlib + JSON
    try:
        decompressed = zlib.decompress(val)
        return json.loads(decompressed)
    except Exception:
        pass

    # 4. zlib + msgpack
    if _has_msgpack:
        try:
            decompressed = zlib.decompress(val)
            return msgpack.unpackb(decompressed, raw=False)
        except Exception:
            pass

    # 5. UTF-8 string
    try:
        return val.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 6. base64 fallback
    return f"base64:{base64.b64encode(val).decode('ascii')}"


def _deep_sanitize(val: Any) -> Any:
    """Recursively make a value JSON-serializable.

    Handles bytes (via blob decoder), msgpack ExtType, and nested
    dicts/lists that may contain non-serializable leaves.
    """
    if isinstance(val, bytes):
        decoded = _try_decode_blob(val)
        # The decoded result may itself contain non-serializable values
        return _deep_sanitize(decoded) if not isinstance(decoded, str) else decoded
    if isinstance(val, dict):
        return {str(k): _deep_sanitize(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_deep_sanitize(v) for v in val]
    # msgpack ExtType or any other unknown type → try blob decode on its data
    if _has_msgpack and isinstance(val, msgpack.ExtType):
        decoded = _try_decode_blob(val.data)
        return _deep_sanitize(decoded) if not isinstance(decoded, str) else decoded
    # Primitives (str, int, float, bool, None) pass through
    if isinstance(val, (str, int, float, bool, type(None))):
        return val
    # Catch-all for unexpected types
    return str(val)


def _sanitize_rows(rows: Any) -> list[list[Any]]:
    """Sanitize all cell values in a list of rows."""
    return [[_deep_sanitize(cell) for cell in row] for row in rows]


async def _connect() -> aiosqlite.Connection:
    """Open a read-only connection to the state database."""
    if not DB_PATH.is_file():
        raise HTTPException(status_code=404, detail="state.db not found")
    return await aiosqlite.connect(_db_uri(), uri=True)


@router.get("/statedb/status")
async def statedb_status() -> dict[str, bool]:
    """Check whether the state database file exists."""
    return {"exists": DB_PATH.is_file()}


@router.get("/statedb/tables")
async def statedb_tables() -> list[dict[str, Any]]:
    """List all tables with their row counts."""
    db = await _connect()
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = await cursor.fetchall()
        result: list[dict[str, Any]] = []
        for (name,) in tables:
            cnt = await db.execute(f"SELECT COUNT(*) FROM {_quote_ident(name)}")  # noqa: S608
            cnt_row = await cnt.fetchone()
            row_count = cnt_row[0] if cnt_row else 0
            result.append({"name": name, "row_count": row_count})
        return result
    finally:
        await db.close()


@router.get("/statedb/tables/{table}")
async def statedb_table_data(
    table: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return paginated rows for a single table."""
    db = await _connect()
    try:
        # Verify table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Table '{table}' not found")

        # Total row count
        quoted = _quote_ident(table)

        cnt = await db.execute(f"SELECT COUNT(*) FROM {quoted}")  # noqa: S608
        cnt_row = await cnt.fetchone()
        total = cnt_row[0] if cnt_row else 0

        # Column info
        pragma = await db.execute(f"PRAGMA table_info({quoted})")
        cols_raw = await pragma.fetchall()
        columns = [{"name": row[1], "type": row[2] or "TEXT"} for row in cols_raw]

        # Data
        data = await db.execute(
            f"SELECT * FROM {quoted} LIMIT ? OFFSET ?",  # noqa: S608
            (limit, offset),
        )
        rows = _sanitize_rows(await data.fetchall())

        return {"columns": columns, "rows": rows, "total": total}
    finally:
        await db.close()


class QueryBody(BaseModel):
    """Request body for custom SQL queries."""

    sql: str
    limit: int | None = Field(default=None, ge=1, le=10000)


@router.post("/statedb/query")
async def statedb_query(body: QueryBody) -> dict[str, Any]:
    """Execute a read-only SQL query against the state database."""
    # Normalize: trim whitespace and strip trailing semicolons
    sql = body.sql.strip().rstrip("; \t\r\n")
    upper_sql = sql.upper()
    # Allow common read-only forms: SELECT, WITH (CTEs), and EXPLAIN
    allowed_prefixes = ("SELECT", "WITH", "EXPLAIN")
    if not upper_sql.startswith(allowed_prefixes):
        raise HTTPException(
            status_code=400, detail="Only read-only SQL statements are allowed"
        )

    limit = min(body.limit or 500, 10000)
    # Wrap in LIMIT if the user didn't include one
    if "LIMIT" not in upper_sql:
        sql = f"{sql} LIMIT {limit}"

    db = await _connect()
    try:
        cursor = await db.execute(sql)
        desc = cursor.description
        columns: list[dict[str, str]] = [
            {"name": d[0], "type": "TEXT"} for d in (desc if desc else [])
        ]
        rows = _sanitize_rows(await cursor.fetchall())
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await db.close()
