from __future__ import annotations

from datetime import date
from typing import Any, Optional

from src.core.logging import logger
from src.models.coffee import BREW_COLUMNS, BREW_METHODS, CLARITY_LABELS, Brew, BrewMethod
from src.repositories.brew_repository import BrewRepository
from src.services.brew_service import BrewService
from src.services.llm_service import LLMService
from src.utils.parsing import today_utc

_SYSTEM_PROMPT = """You are an experienced barista coaching a home brewer who is dialling in.
You get the beans, the equipment, the brew just made and earlier brews of the same beans and
method (newest first), each with the brewer's tasting feedback and any advice given at the time.

Work out what the cup is telling you, then plan the next brew.
- Read the flavour feedback, not just the extraction verdict. Sour, salty, thin or hollow usually
  means under-extraction; bitter, harsh or drying usually means over-extraction. Astringency
  together with sourness, or a muddy cup, often points to uneven extraction (channelling, fines,
  puck prep, pouring) rather than simply the grind.
- Consider every lever: grind, dose, ratio (yield or water), temperature, time, roast age/rest,
  and technique (distribution, tamping, bloom, pour structure, agitation).
- Recommend ONE primary change, with concrete numbers, so the brewer learns what it does. Offer
  other reasonable ways in as alternatives.
- Learn from the history: if earlier advice was followed, judge whether it helped, and avoid
  swinging back and forth.
- Grind numbers belong to the brewer's grinder, where lower is finer. Keep grind changes in
  proportion to the steps in their history (usually 0.5-2 steps for espresso).
- If the cup was good and well rated, say what to keep and suggest at most a small refinement.
- The rule-of-thumb grind is only a baseline; override it when the feedback says otherwise.

Reply with ONLY a JSON object:
{
  "diagnosis": "1-2 sentences on what this cup says",
  "primary_change": "the one change to make next, with numbers, and why",
  "next_brew": {"grind_setting": n, "dose_g": n, "yield_g": n, "water_g": n, "temp_c": n, "time_s": n},
  "alternatives": ["up to 3 other levers worth trying, one short sentence each"],
  "taste_for": "what to pay attention to in the next cup"
}
"next_brew" is the full recipe for the next brew in grams, °C and seconds; use null for values
that don't apply to the method. Keep each string under 200 characters. Use British English."""

_MAX_TEXT = 300
_UNITS = {"dose_g": " g", "yield_g": " g", "water_g": " g", "temp_c": " °C", "time_s": " s"}


def _num(value: Optional[float], unit: str = "") -> Optional[str]:
    return None if value is None else f"{value:g}{unit}"


def _clean_text(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text[:_MAX_TEXT] or None


class AdviceService:
    """Asks the LLM how to improve the next brew, from this brew and its history."""

    def __init__(self, llm: LLMService, brews: BrewRepository) -> None:
        self.llm = llm
        self.brews = brews

    @property
    def enabled(self) -> bool:
        return self.llm.enabled

    async def advise(
        self, user_id: int, brew_id: int, draft: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any]:
        history = await self.brews.history(user_id, draft["bean_id"], draft["method"])
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": self.build_brief(brew_id, draft, ctx, history)},
        ]
        raw = await self.llm.complete_json(messages)
        advice = self.normalise(raw, draft["method"])
        if not advice.get("primary_change"):
            raise ValueError("LLM advice had no primary_change")
        await self.brews.save_advice(brew_id, advice, self.llm.model)
        logger.debug("Brew %s advice: %s", brew_id, advice)
        return advice

    @staticmethod
    def build_brief(brew_id: int, draft: dict[str, Any], ctx: dict[str, Any], history: list[Brew]) -> str:
        method = BREW_METHODS[draft["method"]]
        bean = BrewService.find_bean(ctx, draft["bean_id"]) or {}
        lines = [f"Method: {method.label}"]
        gear = f"Grinder: {draft.get('grinder_name') or 'unknown'} (lower = finer)"
        if draft.get("brewer_name"):
            gear += f". Brewer: {draft['brewer_name']}"
        lines.append(gear)

        details = [bean.get(k) for k in ("origin", "process", "varietal") if bean.get(k)]
        if bean.get("roast_level"):
            details.append(f"{bean['roast_level']} roast")
        if bean.get("roast_date"):
            try:
                days = (today_utc() - date.fromisoformat(bean["roast_date"])).days
                details.append(f"roasted {bean['roast_date']} ({days} days ago)")
            except ValueError:
                details.append(f"roasted {bean['roast_date']}")
        roaster = f" by {bean['roaster']}" if bean.get("roaster") else ""
        lines.append(f"Beans: {bean.get('name', 'unknown')}{roaster}. {'; '.join(details)}")
        if bean.get("tasting_notes"):
            lines.append(f"Bag tasting notes: {', '.join(bean['tasting_notes'])}")

        nudged, _ = BrewService.nudge_grind(draft.get("grind_setting"), draft.get("extraction"))
        if nudged is not None:
            lines.append(f"Rule-of-thumb grind for next time: {nudged:g}")

        lines += ["", f"Brew just made (#{brew_id}):", AdviceService._describe(draft, method)]
        earlier = [b for b in history if b.id != brew_id]
        if earlier:
            lines += ["", "Earlier brews, newest first:"]
            for brew in earlier:
                values = {column: getattr(brew, column) for column in BREW_COLUMNS}
                lines.append(f"#{brew.id} {brew.created_at[:10]}: {AdviceService._describe(values, method)}")
                if brew.ai_advice and brew.ai_advice.get("primary_change"):
                    lines.append(f"  Advice given after it: {brew.ai_advice['primary_change']}")
        return "\n".join(lines)

    @staticmethod
    def _describe(values: dict[str, Any], method: BrewMethod) -> str:
        recipe = [f"grind {_num(values.get('grind_setting')) or '?'}"]
        for field in method.fields:
            value = values.get(field.column)
            if value is not None:
                recipe.append(f"{field.label.lower()} {_num(value, _UNITS[field.column])}")
        dose = values.get("dose_g")
        out = values.get("yield_g") or values.get("water_g")
        if dose and out:
            recipe.append(f"ratio 1:{out / dose:.1f}")
        feedback = [f"extraction {values.get('extraction') or 'not rated'}"]
        if values.get("clarity"):
            feedback.append(f"clarity {CLARITY_LABELS.get(values['clarity'], values['clarity']).lower()}")
        if values.get("rating"):
            feedback.append(f"rating {values['rating']}/5")
        if values.get("tasting_notes"):
            feedback.append(f"tasted {', '.join(values['tasting_notes'])}")
        text = f"{', '.join(recipe)} | {', '.join(feedback)}"
        if values.get("comment"):
            text += f' | comment: "{values["comment"]}"'
        return text

    @staticmethod
    def normalise(raw: dict[str, Any], method_key: str) -> dict[str, Any]:
        """Keep only expected keys, trimmed strings and positive numbers for this method's fields."""
        allowed = {"grind_setting", *(f.column for f in BREW_METHODS[method_key].fields)}
        recipe: dict[str, float] = {}
        for key, value in (raw.get("next_brew") or {}).items():
            if key not in allowed:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number > 0:
                recipe[key] = round(number, 2)
        alternatives = raw.get("alternatives") or []
        if isinstance(alternatives, str):
            alternatives = [alternatives]
        return {
            "diagnosis": _clean_text(raw.get("diagnosis")),
            "primary_change": _clean_text(raw.get("primary_change")),
            "next_brew": recipe,
            "alternatives": [t for t in (_clean_text(a) for a in alternatives) if t][:3],
            "taste_for": _clean_text(raw.get("taste_for")),
        }


__all__ = ["AdviceService"]
