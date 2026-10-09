from __future__ import annotations

from typing import Optional

from src.models.coffee import Equipment
from src.repositories.async_sqlite_adapter import AsyncSQLiteAdapter


class EquipmentRepository:
    """Data access for registered grinders, machines and drippers."""

    def __init__(self, db: AsyncSQLiteAdapter) -> None:
        self.db = db

    async def list_for_user(self, user_id: int, kind: Optional[str] = None) -> list[Equipment]:
        query = "SELECT * FROM equipment WHERE user_id = ?"
        params: list[object] = [user_id]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        rows = await self.db.execute(query + " ORDER BY id", params, fetchall=True)
        return [Equipment.from_row(row) for row in rows]

    async def defaults(self, user_id: int) -> dict[str, Equipment]:
        rows = await self.db.execute(
            "SELECT * FROM equipment WHERE user_id = ? AND is_default = 1",
            (user_id,),
            fetchall=True,
        )
        return {row["kind"]: Equipment.from_row(row) for row in rows}

    async def add_as_default(self, user_id: int, kind: str, name: str) -> int:
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE equipment SET is_default = 0 WHERE user_id = ? AND kind = ?",
                (user_id, kind),
            )
            cursor = await conn.execute(
                "INSERT INTO equipment (user_id, kind, name, is_default) VALUES (?, ?, ?, 1)",
                (user_id, kind, name),
            )
            return cursor.lastrowid

    async def set_default(self, user_id: int, equipment_id: int) -> Optional[Equipment]:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "SELECT * FROM equipment WHERE id = ? AND user_id = ?",
                (equipment_id, user_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            await conn.execute(
                "UPDATE equipment SET is_default = 0 WHERE user_id = ? AND kind = ?",
                (user_id, row["kind"]),
            )
            await conn.execute("UPDATE equipment SET is_default = 1 WHERE id = ?", (equipment_id,))
        return Equipment.from_row({**dict(row), "is_default": 1})


__all__ = ["EquipmentRepository"]
