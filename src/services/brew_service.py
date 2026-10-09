from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from src.models.coffee import BASIC_NOTES, BREW_COLUMNS, Brew, BrewField
from src.repositories.bean_repository import BeanRepository
from src.repositories.brew_repository import BrewRepository
from src.repositories.equipment_repository import EquipmentRepository

GRIND_STEP = 1.0


def _fmt(value: float) -> str:
    return f"{value:g}"


class BrewService:
    """Loads the /brew context once per brew, derives suggestions from it and saves the result."""

    def __init__(
        self,
        beans: BeanRepository,
        brews: BrewRepository,
        equipment: EquipmentRepository,
    ) -> None:
        self.beans = beans
        self.brews = brews
        self.equipment = equipment

    async def load_context(self, user_id: int) -> dict[str, Any]:
        beans = await self.beans.list_active(user_id)
        defaults = await self.equipment.defaults(user_id)
        recent = await self.brews.latest_per_group(user_id)
        return {
            "beans": [asdict(bean) for bean in beans],
            "equipment": {kind: {"id": e.id, "name": e.name} for kind, e in defaults.items()},
            "recent": [asdict(brew) for brew in recent],
        }

    async def recent(self, user_id: int, limit: int = 10) -> list[Brew]:
        return await self.brews.recent(user_id, limit)

    async def save(self, user_id: int, draft: dict[str, Any]) -> int:
        return await self.brews.add(user_id, {column: draft.get(column) for column in BREW_COLUMNS})

    @staticmethod
    def find_bean(ctx: dict[str, Any], bean_id: Optional[int]) -> Optional[dict[str, Any]]:
        return next((bean for bean in ctx["beans"] if bean["id"] == bean_id), None)

    @staticmethod
    def default_bean(ctx: dict[str, Any]) -> Optional[dict[str, Any]]:
        """The bean from the most recent brew if still active, else the newest bag."""
        active = {bean["id"] for bean in ctx["beans"]}
        for brew in ctx["recent"]:
            if brew["bean_id"] in active:
                return BrewService.find_bean(ctx, brew["bean_id"])
        return ctx["beans"][0] if ctx["beans"] else None

    @staticmethod
    def _last(ctx: dict[str, Any], *, method: str, column: str, bean_id=None, grinder_id=None, match_grinder=False):
        for brew in ctx["recent"]:
            if brew["method"] != method or brew.get(column) is None:
                continue
            if bean_id is not None and brew["bean_id"] != bean_id:
                continue
            if match_grinder and brew["grinder_id"] != grinder_id:
                continue
            return brew
        return None

    @classmethod
    def suggest_grind(cls, ctx: dict[str, Any], bean_id: int, method: str) -> tuple[Optional[float], str]:
        """Suggest a grind setting from history, nudged by the last extraction verdict."""
        grinder_id = (ctx["equipment"].get("grinder") or {}).get("id")
        lookup = dict(method=method, column="grind_setting", grinder_id=grinder_id, match_grinder=True)
        same = cls._last(ctx, bean_id=bean_id, **lookup)
        if same:
            last = same["grind_setting"]
            if same["extraction"] == "under":
                return last - GRIND_STEP, f"Last time with these beans: {_fmt(last)}, under-extracted. Try finer."
            if same["extraction"] == "over":
                return last + GRIND_STEP, f"Last time with these beans: {_fmt(last)}, over-extracted. Try coarser."
            return last, f"Last time with these beans: {_fmt(last)}."
        other = cls._last(ctx, **lookup)
        if other:
            return other["grind_setting"], f"First time with these beans. Your last one used {_fmt(other['grind_setting'])}."
        return None, "No history yet. Type your grind setting."

    @classmethod
    def suggest_values(
        cls, ctx: dict[str, Any], draft: dict[str, Any], field: BrewField
    ) -> list[tuple[str, float]]:
        """Return (button label, value in entry units) suggestions for a numeric field."""
        method = draft["method"]
        last = cls._last(ctx, method=method, column=field.column, bean_id=draft["bean_id"])
        last = last or cls._last(ctx, method=method, column=field.column)
        options: list[tuple[str, float]] = []
        if last:
            value = round(last[field.column] / field.scale, 2)
            options.append((f"{_fmt(value)} (last)", value))
        dose = draft.get("dose_g")
        if field.ratio_of_dose and dose:
            value = round(dose * field.ratio_of_dose, 1)
            if all(existing != value for _, existing in options):
                options.append((f"{_fmt(value)} (1:{_fmt(field.ratio_of_dose)})", value))
        return options

    @staticmethod
    def note_options(ctx: dict[str, Any], bean_id: int) -> list[str]:
        """Bag notes, then notes tasted last time with this bean, then the basics."""
        bean = BrewService.find_bean(ctx, bean_id) or {}
        previous = next((b for b in ctx["recent"] if b["bean_id"] == bean_id), None)
        candidates = [*bean.get("tasting_notes", []), *(previous or {}).get("tasting_notes", []), *BASIC_NOTES]
        options: list[str] = []
        for note in candidates:
            if note.lower() not in options:
                options.append(note.lower())
        return options[:16]


__all__ = ["BrewService", "GRIND_STEP"]
