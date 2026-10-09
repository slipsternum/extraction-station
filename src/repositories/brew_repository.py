from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from src.models.coffee import BREW_COLUMNS, Brew
from src.repositories.async_sqlite_adapter import AsyncSQLiteAdapter


class BrewRepository:
    """Data access for logged brews."""

    def __init__(self, db: AsyncSQLiteAdapter) -> None:
        self.db = db

    async def add(self, user_id: int, values: Mapping[str, Any]) -> int:
        params = {column: values.get(column) for column in BREW_COLUMNS}
        params["tasting_notes"] = json.dumps(values.get("tasting_notes") or [])
        params["user_id"] = user_id
        columns = ", ".join(params)
        placeholders = ", ".join(f":{column}" for column in params)
        row = await self.db.execute(
            f"INSERT INTO brews ({columns}) VALUES ({placeholders}) RETURNING id",
            params,
            fetchone=True,
        )
        return row["id"]

    async def latest_per_group(self, user_id: int) -> list[Brew]:
        """Return the most recent brew for every (bean, method, grinder) combination."""
        rows = await self.db.execute(
            """
            SELECT brews.*, brew_advice.advice AS ai_advice FROM brews
            LEFT JOIN brew_advice ON brew_advice.brew_id = brews.id
            WHERE brews.id IN (
                SELECT MAX(id) FROM brews WHERE user_id = ?
                GROUP BY bean_id, method, grinder_id
            )
            ORDER BY brews.id DESC
            """,
            (user_id,),
            fetchall=True,
        )
        return [Brew.from_row(row) for row in rows]

    async def history(self, user_id: int, bean_id: int, method: str, limit: int = 6) -> list[Brew]:
        """Most recent brews of one bean with one method, newest first, with their advice."""
        rows = await self.db.execute(
            """
            SELECT brews.*, brew_advice.advice AS ai_advice FROM brews
            LEFT JOIN brew_advice ON brew_advice.brew_id = brews.id
            WHERE brews.user_id = ? AND brews.bean_id = ? AND brews.method = ?
            ORDER BY brews.id DESC LIMIT ?
            """,
            (user_id, bean_id, method, limit),
            fetchall=True,
        )
        return [Brew.from_row(row) for row in rows]

    async def save_advice(self, brew_id: int, advice: Mapping[str, Any], model: Optional[str]) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO brew_advice (brew_id, advice, model) VALUES (?, ?, ?)",
            (brew_id, json.dumps(advice), model),
        )

    async def recent(self, user_id: int, limit: int = 10) -> list[Brew]:
        rows = await self.db.execute(
            """
            SELECT brews.*, beans.name AS bean_name FROM brews
            JOIN beans ON beans.id = brews.bean_id
            WHERE brews.user_id = ?
            ORDER BY brews.id DESC LIMIT ?
            """,
            (user_id, limit),
            fetchall=True,
        )
        return [Brew.from_row(row) for row in rows]


__all__ = ["BrewRepository"]
