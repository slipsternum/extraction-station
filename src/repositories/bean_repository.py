from __future__ import annotations

import json
from typing import Optional

from src.models.coffee import Bean
from src.repositories.async_sqlite_adapter import AsyncSQLiteAdapter


class BeanRepository:
    """Data access for bags of beans."""

    def __init__(self, db: AsyncSQLiteAdapter) -> None:
        self.db = db

    async def add(self, bean: Bean) -> int:
        row = await self.db.execute(
            """
            INSERT INTO beans (user_id, name, roaster, origin, process, varietal,
                               roast_level, roast_date, tasting_notes, photo_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                bean.user_id,
                bean.name,
                bean.roaster,
                bean.origin,
                bean.process,
                bean.varietal,
                bean.roast_level,
                bean.roast_date,
                json.dumps(bean.tasting_notes),
                bean.photo_file_id,
            ),
            fetchone=True,
        )
        return row["id"]

    async def get(self, user_id: int, bean_id: int) -> Optional[Bean]:
        row = await self.db.execute(
            "SELECT * FROM beans WHERE id = ? AND user_id = ?",
            (bean_id, user_id),
            fetchone=True,
        )
        return Bean.from_row(row) if row else None

    async def list_active(self, user_id: int) -> list[Bean]:
        rows = await self.db.execute(
            "SELECT * FROM beans WHERE user_id = ? AND archived = 0 ORDER BY id DESC",
            (user_id,),
            fetchall=True,
        )
        return [Bean.from_row(row) for row in rows]

    async def set_archived(self, user_id: int, bean_id: int, archived: bool) -> None:
        await self.db.execute(
            "UPDATE beans SET archived = ? WHERE id = ? AND user_id = ?",
            (int(archived), bean_id, user_id),
        )


__all__ = ["BeanRepository"]
