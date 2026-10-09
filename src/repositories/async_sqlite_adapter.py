from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Optional, Sequence

import aiosqlite

from src.core import config
from src.models.schemas import load_schema


class AsyncSQLiteAdapter:
    """Async wrapper around sqlite providing schema bootstrap and helpers."""

    def __init__(self, db_path: str, schema_path: str | None = None) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._apply_pragmas()
        await self._create_schema()

    async def _apply_pragmas(self) -> None:
        assert self._conn is not None
        async with self._conn.execute("PRAGMA foreign_keys=ON;"):
            pass
        await self._conn.commit()

    async def _create_schema(self) -> None:
        assert self._conn is not None
        schema = load_schema(self.schema_path)
        await self._conn.executescript(schema)
        await self._conn.commit()

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    @property
    def path(self) -> Path:
        return Path(self.db_path)

    async def execute(
        self,
        query: str,
        params: Sequence[Any] | dict[str, Any] = (),
        *,
        fetchone: bool = False,
        fetchall: bool = False,
        commit: Optional[bool] = None,
    ):
        await self.connect()
        assert self._conn is not None
        should_commit = commit if commit is not None else not query.lstrip().lower().startswith("select")
        async with self._lock:
            cursor = await self._conn.execute(query, params)
            result = None
            if fetchone:
                result = await cursor.fetchone()
            elif fetchall:
                result = await cursor.fetchall()
            if should_commit:
                await self._conn.commit()
            return result

    async def executemany(
        self,
        query: str,
        seq_of_params: Iterable[Sequence[Any] | dict[str, Any]],
    ) -> None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            await self._conn.executemany(query, seq_of_params)
            await self._conn.commit()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            try:
                yield self._conn
                await self._conn.commit()
            except Exception:
                await self._conn.rollback()
                raise


__all__ = ["AsyncSQLiteAdapter"]
