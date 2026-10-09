from __future__ import annotations

from typing import Any, Optional

from telebot.async_telebot import AsyncTeleBot

from src.core.logging import logger
from src.models.coffee import Bean
from src.repositories.bean_repository import BeanRepository
from src.services.llm_service import LLMService
from src.utils.parsing import parse_date, today_utc

BEAN_FIELDS: tuple[str, ...] = (
    "name",
    "roaster",
    "origin",
    "process",
    "varietal",
    "roast_level",
    "roast_date",
    "tasting_notes",
)

_LABEL_PROMPT = """You read labels on bags of specialty coffee beans.
Extract the details and reply with ONLY a JSON object with these keys:
- "name": the coffee's name as printed (farm, lot or blend name), or null
- "roaster": the roastery, or null
- "origin": country and region, e.g. "Ethiopia, Guji", or null
- "process": e.g. "washed", "natural", "honey", "anaerobic natural", or null
- "varietal": e.g. "Heirloom", "Gesha, Caturra", or null
- "roast_level": one of "light", "medium-light", "medium", "medium-dark", "dark", or null
- "roast_date": the roast date as YYYY-MM-DD, or null if not shown. Today is {today}; if the
  year is missing, use the most recent such date that is not after today. Ignore best-before dates.
- "tasting_notes": a list of the tasting notes as printed, as short lowercase phrases
Use null for anything you cannot read. Do not guess."""


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class BeanService:
    """Bean bag CRUD and LLM-backed label extraction."""

    def __init__(self, bot: AsyncTeleBot, repository: BeanRepository, llm: LLMService) -> None:
        self.bot = bot
        self.repository = repository
        self.llm = llm

    @property
    def extraction_enabled(self) -> bool:
        return self.llm.enabled

    async def extract_from_photo(self, file_id: str, hint: Optional[str] = None) -> dict[str, Any]:
        file_info = await self.bot.get_file(file_id)
        image = await self.bot.download_file(file_info.file_path)
        content: list[dict[str, Any]] = [{"type": "text", "text": hint or "Here is the bag."}]
        content.append(LLMService.image_part(image))
        return await self._extract(content)

    async def extract_from_text(self, text: str) -> dict[str, Any]:
        return await self._extract([{"type": "text", "text": text}])

    async def _extract(self, content: list[dict[str, Any]]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": _LABEL_PROMPT.format(today=today_utc().isoformat())},
            {"role": "user", "content": content},
        ]
        raw = await self.llm.complete_json(messages)
        logger.debug("Bean label extraction: %s", raw)
        return self.normalise(raw)

    @staticmethod
    def normalise(raw: dict[str, Any]) -> dict[str, Any]:
        draft: dict[str, Any] = {key: _clean(raw.get(key)) for key in BEAN_FIELDS if key != "tasting_notes"}
        roast_date = parse_date(draft["roast_date"]) if draft["roast_date"] else None
        draft["roast_date"] = roast_date.isoformat() if roast_date else None
        notes = raw.get("tasting_notes") or []
        if isinstance(notes, str):
            notes = notes.split(",")
        draft["tasting_notes"] = [str(n).strip().lower() for n in notes if str(n).strip()][:10]
        return draft

    async def save_draft(self, user_id: int, draft: dict[str, Any]) -> Bean:
        bean = Bean(
            id=None,
            user_id=user_id,
            name=draft.get("name") or draft.get("origin") or "Unnamed beans",
            roaster=draft.get("roaster"),
            origin=draft.get("origin"),
            process=draft.get("process"),
            varietal=draft.get("varietal"),
            roast_level=draft.get("roast_level"),
            roast_date=draft.get("roast_date"),
            tasting_notes=list(draft.get("tasting_notes") or []),
            photo_file_id=draft.get("photo_file_id"),
        )
        bean.id = await self.repository.add(bean)
        return bean

    async def get(self, user_id: int, bean_id: int) -> Optional[Bean]:
        return await self.repository.get(user_id, bean_id)

    async def list_active(self, user_id: int) -> list[Bean]:
        return await self.repository.list_active(user_id)

    async def set_archived(self, user_id: int, bean_id: int, archived: bool) -> None:
        await self.repository.set_archived(user_id, bean_id, archived)


__all__ = ["BEAN_FIELDS", "BeanService"]
