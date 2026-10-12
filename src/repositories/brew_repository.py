from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from src.models.coffee import BREW_COLUMNS, Brew
from src.repositories.async_sqlite_adapter import AsyncSQLiteAdapter

_NOW = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


def _params(values: Mapping[str, Any]) -> dict[str, Any]:
    params = {column: values.get(column) for column in BREW_COLUMNS}
    params["tasting_notes"] = json.dumps(values.get("tasting_notes") or [])
    return params


class BrewRepository:
    """Data access for logged brews; only finished ('done') brews count as history."""

    def __init__(self, db: AsyncSQLiteAdapter) -> None:
        self.db = db

    async def add(self, user_id: int, values: Mapping[str, Any], *, status: str = "done") -> int:
        params = {**_params(values), "user_id": user_id, "status": status}
        columns = ", ".join(params)
        placeholders = ", ".join(f":{column}" for column in params)
        finished = _NOW if status == "done" else "NULL"
        row = await self.db.execute(
            f"INSERT INTO brews ({columns}, finished_at) VALUES ({placeholders}, {finished}) RETURNING id",
            params,
            fetchone=True,
        )
        return row["id"]

    async def update_open(
        self, user_id: int, brew_id: int, values: Mapping[str, Any], *, status: str
    ) -> Optional[int]:
        """Update a brew that is still brewing; returns None if it is gone or already finished."""
        params = {**_params(values), "status": status}
        assignments = ", ".join(f"{column} = :{column}" for column in params)
        finished = _NOW if status == "done" else "NULL"
        row = await self.db.execute(
            f"""
            UPDATE brews SET {assignments}, finished_at = {finished}
            WHERE id = :id AND user_id = :user_id AND status = 'brewing'
            RETURNING id
            """,
            {**params, "id": brew_id, "user_id": user_id},
            fetchone=True,
        )
        return row["id"] if row else None

    async def open_brews(self, user_id: int) -> list[Brew]:
        """Brews started but not finished, oldest first, with bean and equipment names."""
        rows = await self.db.execute(
            """
            SELECT brews.*, beans.name AS bean_name,
                   grinder.name AS grinder_name, brewer.name AS brewer_name
            FROM brews
            JOIN beans ON beans.id = brews.bean_id
            LEFT JOIN equipment AS grinder ON grinder.id = brews.grinder_id
            LEFT JOIN equipment AS brewer ON brewer.id = brews.brewer_id
            WHERE brews.user_id = ? AND brews.status = 'brewing'
            ORDER BY brews.id
            """,
            (user_id,),
            fetchall=True,
        )
        return [Brew.from_row(row) for row in rows]

    async def delete_open(self, user_id: int, brew_id: int) -> None:
        await self.db.execute(
            "DELETE FROM brews WHERE id = ? AND user_id = ? AND status = 'brewing'",
            (brew_id, user_id),
        )

    async def latest_per_group(self, user_id: int) -> list[Brew]:
        """Return the most recent brew for every (bean, method, grinder) combination."""
        rows = await self.db.execute(
            """
            SELECT brews.*, brew_advice.advice AS ai_advice FROM brews
            LEFT JOIN brew_advice ON brew_advice.brew_id = brews.id
            WHERE brews.id IN (
                SELECT MAX(id) FROM brews WHERE user_id = ? AND status = 'done'
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
            WHERE brews.user_id = ? AND brews.bean_id = ? AND brews.method = ? AND brews.status = 'done'
            ORDER BY brews.id DESC LIMIT ?
            """,
            (user_id, bean_id, method, limit),
            fetchall=True,
        )
        return [Brew.from_row(row) for row in rows]

    async def count(self, user_id: int, bean_id: int, method: str) -> int:
        row = await self.db.execute(
            """
            SELECT COUNT(*) AS n FROM brews
            WHERE user_id = ? AND bean_id = ? AND method = ? AND status = 'done'
            """,
            (user_id, bean_id, method),
            fetchone=True,
        )
        return row["n"]

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
            WHERE brews.user_id = ? AND brews.status = 'done'
            ORDER BY brews.id DESC LIMIT ?
            """,
            (user_id, limit),
            fetchall=True,
        )
        return [Brew.from_row(row) for row in rows]


__all__ = ["BrewRepository"]
