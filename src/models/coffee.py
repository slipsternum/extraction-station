from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

EQUIPMENT_KINDS: dict[str, str] = {
    "grinder": "Grinder",
    "espresso_machine": "Espresso machine",
    "dripper": "Dripper",
}

EXTRACTION_LABELS: dict[str, str] = {
    "under": "Under-extracted",
    "good": "Well extracted",
    "over": "Over-extracted",
}

CLARITY_LABELS: dict[str, str] = {
    "muddy": "Muddy",
    "balanced": "Balanced",
    "clean": "Clean",
}

BASIC_NOTES: tuple[str, ...] = ("sweet", "sour", "bitter", "astringent", "watery")


@dataclass(frozen=True)
class BrewField:
    """A numeric brew parameter; ``scale`` converts the entered unit to the stored one."""

    column: str
    label: str
    unit: str
    scale: float = 1.0
    ratio_of_dose: Optional[float] = None


@dataclass(frozen=True)
class BrewMethod:
    key: str
    label: str
    equipment_kind: Optional[str]
    fields: tuple[BrewField, ...]


_DOSE = BrewField("dose_g", "Dose", "g")

BREW_METHODS: dict[str, BrewMethod] = {
    "espresso": BrewMethod(
        "espresso",
        "Espresso",
        "espresso_machine",
        (
            _DOSE,
            BrewField("yield_g", "Yield", "g", ratio_of_dose=2.0),
            BrewField("time_s", "Shot time", "s"),
        ),
    ),
    "pour_over": BrewMethod(
        "pour_over",
        "Pour-over",
        "dripper",
        (
            _DOSE,
            BrewField("water_g", "Water", "g", ratio_of_dose=16.0),
            BrewField("temp_c", "Water temp", "°C"),
            BrewField("time_s", "Brew time", "s"),
        ),
    ),
    "cold_brew": BrewMethod(
        "cold_brew",
        "Cold brew",
        None,
        (
            _DOSE,
            BrewField("water_g", "Water", "g", ratio_of_dose=8.0),
            BrewField("time_s", "Steep time", "h", scale=3600.0),
        ),
    ),
}

BREW_COLUMNS: tuple[str, ...] = (
    "bean_id",
    "method",
    "grinder_id",
    "brewer_id",
    "grind_setting",
    "dose_g",
    "yield_g",
    "water_g",
    "temp_c",
    "time_s",
    "extraction",
    "clarity",
    "tasting_notes",
    "rating",
    "comment",
    "photo_file_id",
)


def _notes(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(n) for n in raw]
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(n) for n in value] if isinstance(value, list) else []


def _advice(raw: Any) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


@dataclass(slots=True)
class Equipment:
    id: int
    user_id: int
    kind: str
    name: str
    is_default: bool

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Equipment":
        return cls(row["id"], row["user_id"], row["kind"], row["name"], bool(row["is_default"]))


@dataclass(slots=True)
class Bean:
    id: Optional[int]
    user_id: int
    name: str
    roaster: Optional[str] = None
    origin: Optional[str] = None
    process: Optional[str] = None
    varietal: Optional[str] = None
    roast_level: Optional[str] = None
    roast_date: Optional[str] = None
    tasting_notes: list[str] = field(default_factory=list)
    photo_file_id: Optional[str] = None
    archived: bool = False
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Bean":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            roaster=row["roaster"],
            origin=row["origin"],
            process=row["process"],
            varietal=row["varietal"],
            roast_level=row["roast_level"],
            roast_date=row["roast_date"],
            tasting_notes=_notes(row["tasting_notes"]),
            photo_file_id=row["photo_file_id"],
            archived=bool(row["archived"]),
            created_at=row["created_at"],
        )


@dataclass(slots=True)
class Brew:
    id: int
    user_id: int
    bean_id: int
    method: str
    grinder_id: Optional[int]
    brewer_id: Optional[int]
    grind_setting: Optional[float]
    dose_g: Optional[float]
    yield_g: Optional[float]
    water_g: Optional[float]
    temp_c: Optional[float]
    time_s: Optional[float]
    extraction: Optional[str]
    clarity: Optional[str]
    tasting_notes: list[str]
    rating: Optional[int]
    comment: Optional[str]
    photo_file_id: Optional[str]
    created_at: str
    bean_name: Optional[str] = None
    ai_advice: Optional[dict[str, Any]] = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Brew":
        keys = row.keys()
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            bean_id=row["bean_id"],
            method=row["method"],
            grinder_id=row["grinder_id"],
            brewer_id=row["brewer_id"],
            grind_setting=row["grind_setting"],
            dose_g=row["dose_g"],
            yield_g=row["yield_g"],
            water_g=row["water_g"],
            temp_c=row["temp_c"],
            time_s=row["time_s"],
            extraction=row["extraction"],
            clarity=row["clarity"],
            tasting_notes=_notes(row["tasting_notes"]),
            rating=row["rating"],
            comment=row["comment"],
            photo_file_id=row["photo_file_id"],
            created_at=row["created_at"],
            bean_name=row["bean_name"] if "bean_name" in keys else None,
            ai_advice=_advice(row["ai_advice"]) if "ai_advice" in keys else None,
        )


__all__ = [
    "BASIC_NOTES",
    "BREW_COLUMNS",
    "BREW_METHODS",
    "CLARITY_LABELS",
    "EQUIPMENT_KINDS",
    "EXTRACTION_LABELS",
    "Bean",
    "Brew",
    "BrewField",
    "BrewMethod",
    "Equipment",
]
