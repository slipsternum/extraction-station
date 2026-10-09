from __future__ import annotations

from typing import Optional

from src.models.coffee import Equipment
from src.repositories.equipment_repository import EquipmentRepository


class SetupService:
    """Manages the user's registered equipment and which piece is the default per kind."""

    def __init__(self, repository: EquipmentRepository) -> None:
        self.repository = repository

    async def defaults(self, user_id: int) -> dict[str, Equipment]:
        return await self.repository.defaults(user_id)

    async def list_kind(self, user_id: int, kind: str) -> list[Equipment]:
        return await self.repository.list_for_user(user_id, kind)

    async def add(self, user_id: int, kind: str, name: str) -> int:
        return await self.repository.add_as_default(user_id, kind, name)

    async def set_default(self, user_id: int, equipment_id: int) -> Optional[Equipment]:
        return await self.repository.set_default(user_id, equipment_id)


__all__ = ["SetupService"]
