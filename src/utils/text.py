from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

from telebot.formatting import escape_html

from src.models.coffee import (
    BREW_METHODS,
    CLARITY_LABELS,
    EQUIPMENT_KINDS,
    EXTRACTION_LABELS,
    BrewField,
)
from src.utils.parsing import today_utc


def _e(value: Any) -> str:
    return escape_html(str(value))


def format_value(value: Optional[float], field: BrewField) -> str:
    if value is None:
        return "—"
    shown = value / field.scale
    if field.unit == "s" and shown >= 60:
        return f"{int(shown // 60)}:{int(shown % 60):02d}"
    return f"{shown:g}{field.unit if field.unit in ('g', 's', 'h') else ' ' + field.unit}"


def roast_age(roast_date: Optional[str]) -> Optional[str]:
    if not roast_date:
        return None
    try:
        roasted = date.fromisoformat(roast_date)
    except ValueError:
        return _e(roast_date)
    days = (today_utc() - roasted).days
    when = f"{roasted.day} {roasted:%b %Y}" if roasted.year != today_utc().year else f"{roasted.day} {roasted:%b}"
    if days < 0:
        return f"roasted {when}"
    return f"roasted {when} ({days} day{'s' if days != 1 else ''} ago)"


def bean_label(bean: Mapping[str, Any]) -> str:
    """Short plain-text label, safe for button text."""
    label = bean.get("name") or "Unnamed beans"
    return f"{label} · {bean['roaster']}" if bean.get("roaster") else label


class WelcomeText:
    @staticmethod
    def greeting(user: object | None) -> str:
        first_name = getattr(user, "first_name", None) or "there"
        return (
            f"Hey {_e(first_name)}! ☕ I'll help you log brews and dial in your coffee.\n\n"
            "1. /setup: register your grinder, espresso machine and dripper\n"
            "2. /newbean: snap a photo of a new bag\n"
            "3. /brew: log a brew\n\n"
            "Use /help to see everything."
        )

    @staticmethod
    def cancelled() -> str:
        return "Cancelled."


class HelpText:
    @staticmethod
    def help_message() -> str:
        return (
            "Available commands:\n"
            "- /brew: log a brew (suggests your grind from history)\n"
            "- /newbean: add a bag of beans from a photo or text\n"
            "- /beans: list and archive your beans\n"
            "- /history: your recent brews\n"
            "- /setup: register your grinder, espresso machine and dripper\n"
            "- /cancel: cancel the current operation\n"
            "- /ping: check bot health"
        )


class SetupText:
    @staticmethod
    def overview(defaults: Mapping[str, Any]) -> str:
        lines = ["⚙️ <b>Your setup</b>", ""]
        for kind, label in EQUIPMENT_KINDS.items():
            item = defaults.get(kind)
            lines.append(f"{label}: <b>{_e(item.name)}</b>" if item else f"{label}: —")
        lines += ["", "These are used for every /brew. Tap one to change it."]
        return "\n".join(lines)

    @staticmethod
    def pick(kind: str, has_items: bool) -> str:
        label = EQUIPMENT_KINDS[kind]
        if not has_items:
            return f"<b>{label}</b>\n\nNothing registered yet. Add one."
        return f"<b>{label}</b>\n\nPick your default, or add a new one."

    @staticmethod
    def ask_name(kind: str) -> str:
        examples = {"grinder": "DF54", "espresso_machine": "Gaggia Classic Pro", "dripper": "Hario V60 02"}
        return f"Send the name of your {EQUIPMENT_KINDS[kind].lower()} (e.g. <i>{examples[kind]}</i>)."


class BeanText:
    FIELD_LABELS: dict[str, str] = {
        "name": "Name",
        "roaster": "Roaster",
        "origin": "Origin",
        "process": "Process",
        "varietal": "Varietal",
        "roast_level": "Roast level",
        "roast_date": "Roast date",
        "tasting_notes": "Tasting notes",
    }

    @staticmethod
    def card(bean: Mapping[str, Any], *, header: Optional[str] = None) -> str:
        lines = [header, ""] if header else []
        lines.append(f"<b>{_e(bean.get('name') or 'Unnamed beans')}</b>")
        if bean.get("roaster"):
            lines.append(_e(bean["roaster"]))
        details = [bean.get(k) for k in ("origin", "process", "varietal") if bean.get(k)]
        if details:
            lines.append(" · ".join(_e(d) for d in details))
        roast = [bean.get("roast_level") and f"{_e(bean['roast_level'])} roast", roast_age(bean.get("roast_date"))]
        roast_text = ", ".join(r for r in roast if r)
        if roast_text:
            lines.append(roast_text[0].upper() + roast_text[1:])
        notes = bean.get("tasting_notes") or []
        if notes:
            lines.append(f"Notes: <i>{_e(', '.join(notes))}</i>")
        return "\n".join(lines)

    @staticmethod
    def capture_prompt(extraction_enabled: bool) -> str:
        if extraction_enabled:
            return (
                "📷 Send a photo of the bag and I'll read the label.\n"
                "Or type the details, e.g. <i>Onyx Geometry, washed Ethiopia, light, roasted 2 Oct, "
                "notes: peach, jasmine</i>."
            )
        return (
            "Send a photo of the bag (label reading is off, so you'll fill in the details), "
            "or type the bean's name."
        )

    @staticmethod
    def reading() -> str:
        return "🔎 Reading the label…"

    @staticmethod
    def extraction_failed() -> str:
        return "I couldn't read the label, so please fill in the details below."

    @staticmethod
    def manual_header() -> str:
        return "Fill in the details with the buttons below:"

    @staticmethod
    def review_header() -> str:
        return "Here's what I've got. Check it, especially the roast date:"

    @staticmethod
    def ask_field(field: str) -> str:
        hints = {
            "roast_date": "e.g. <i>2026-10-02</i> or <i>2 Oct</i>",
            "tasting_notes": "comma-separated, e.g. <i>peach, jasmine, black tea</i>",
            "roast_level": "e.g. <i>light</i>, <i>medium</i>, <i>dark</i>",
        }
        hint = hints.get(field)
        text = f"Send the new <b>{BeanText.FIELD_LABELS[field].lower()}</b>"
        return f"{text} ({hint}), or <code>-</code> to clear it." if hint else f"{text}, or <code>-</code> to clear it."

    @staticmethod
    def bad_date() -> str:
        return "I couldn't read that date. Try <i>2026-10-02</i> or <i>2 Oct</i>."

    @staticmethod
    def saved(bean: Mapping[str, Any]) -> str:
        return f"✅ Saved <b>{_e(bean_label(bean))}</b>. It'll be suggested on your next /brew."

    @staticmethod
    def list_header(count: int) -> str:
        if not count:
            return "No beans yet. Add a bag with /newbean."
        return f"☕ <b>Your beans</b> ({count})\n\nTap one to see it. Add more with /newbean."


class BrewText:
    @staticmethod
    def _bean_line(bean: Mapping[str, Any]) -> str:
        age = roast_age(bean.get("roast_date"))
        return f"<b>{_e(bean_label(bean))}</b>" + (f"\n<i>{age}</i>" if age else "")

    @staticmethod
    def confirm_bean(bean: Mapping[str, Any]) -> str:
        return f"☕ <b>New brew</b>\n\nBeans: {BrewText._bean_line(bean)}\n\nUse these?"

    @staticmethod
    def pick_bean() -> str:
        return "Which beans?"

    @staticmethod
    def pick_method(bean: Mapping[str, Any]) -> str:
        return f"Beans: {BrewText._bean_line(bean)}\n\nBrew method?"

    @staticmethod
    def grind(draft: Mapping[str, Any], ctx: Mapping[str, Any], reason: str, *, has_options: bool) -> str:
        method = BREW_METHODS[draft["method"]]
        grinder = (ctx["equipment"].get("grinder") or {}).get("name", "grinder")
        brewer = ctx["equipment"].get(method.equipment_kind or "")
        gear = _e(grinder) + (f" · {_e(brewer['name'])}" if brewer else "")
        missing = ""
        if method.equipment_kind and not brewer:
            missing = f"\n<i>No {EQUIPMENT_KINDS[method.equipment_kind].lower()} set. Add one in /setup.</i>"
        return (
            f"<b>{method.label}</b> · {gear}{missing}\n\n"
            f"🎚 <b>Grind setting</b> (lower = finer)\n{_e(reason)}"
            + ("\n\nTap one or type a value." if has_options else "")
        )

    @staticmethod
    def param(field: BrewField, has_options: bool) -> str:
        prompt = f"<b>{field.label}</b> ({field.unit})?"
        if field.unit == "s":
            prompt += " Seconds or m:ss."
        return f"{prompt}\n\n{'Tap a suggestion or type' if has_options else 'Type'} a value."

    @staticmethod
    def photo() -> str:
        return "Brew away ☕\n\nWhen you're done, send a photo of it, or tap Skip."

    @staticmethod
    def extraction() -> str:
        return (
            "How did it extract?\n\n"
            "<i>Under: sour, salty, thin, fast\n"
            "Over: bitter, dry, hollow, harsh</i>"
        )

    @staticmethod
    def clarity() -> str:
        return "How was the clarity? Could you pick out distinct flavours?"

    @staticmethod
    def notes(selected: list[str]) -> str:
        picked = f"\n\nPicked: <i>{_e(', '.join(selected))}</i>" if selected else ""
        return (
            "👅 What did you taste? Tap to toggle. The first ones are from the bag.\n"
            f"Type to add your own (comma-separated).{picked}"
        )

    @staticmethod
    def rating() -> str:
        return "Overall, how was it?"

    @staticmethod
    def comment() -> str:
        return "Anything else to remember? Type it, or tap Skip."

    @staticmethod
    def summary(draft: Mapping[str, Any], ctx: Mapping[str, Any], *, header: str) -> str:
        method = BREW_METHODS[draft["method"]]
        bean = next((b for b in ctx["beans"] if b["id"] == draft["bean_id"]), {})
        lines = [header, "", f"<b>{method.label}</b> · {_e(bean_label(bean))}"]
        gear = " · ".join(_e(g) for g in (draft.get("grinder_name"), draft.get("brewer_name")) if g)
        grind = draft.get("grind_setting")
        if grind is not None:
            lines.append(f"Grind <b>{grind:g}</b>" + (f" · {gear}" if gear else ""))
        elif gear:
            lines.append(gear)
        params = [f"{f.label} {format_value(draft.get(f.column), f)}" for f in method.fields if draft.get(f.column) is not None]
        if params:
            lines.append(" · ".join(params))
        ratio = BrewText.ratio(draft)
        if ratio:
            lines.append(f"Ratio {ratio}")
        lines.append("")
        if draft.get("extraction"):
            lines.append(EXTRACTION_LABELS[draft["extraction"]])
        if draft.get("clarity"):
            lines.append(f"Clarity: {CLARITY_LABELS[draft['clarity']]}")
        if draft.get("tasting_notes"):
            lines.append(f"Notes: <i>{_e(', '.join(draft['tasting_notes']))}</i>")
        if draft.get("rating"):
            lines.append("★" * draft["rating"] + "☆" * (5 - draft["rating"]))
        if draft.get("comment"):
            lines.append(f"💬 {_e(draft['comment'])}")
        return "\n".join(lines)

    @staticmethod
    def ratio(draft: Mapping[str, Any]) -> Optional[str]:
        dose = draft.get("dose_g")
        out = draft.get("yield_g") or draft.get("water_g")
        if not dose or not out:
            return None
        return f"1:{out / dose:.1f}"

    @staticmethod
    def saved() -> str:
        return "💾 <b>Brew saved</b>"

    @staticmethod
    def discarded() -> str:
        return "🗑 Brew discarded."

    @staticmethod
    def stale() -> str:
        return "That brew has ended. Start a new one with /brew."

    @staticmethod
    def needs_grinder() -> str:
        return "Register your grinder first with /setup. I use it to suggest grind settings."

    @staticmethod
    def needs_beans() -> str:
        return "Add a bag of beans first with /newbean."

    @staticmethod
    def history(brews: list[Any]) -> str:
        if not brews:
            return "No brews yet. Start one with /brew."
        lines = ["📒 <b>Recent brews</b>", ""]
        for brew in brews:
            method = BREW_METHODS.get(brew.method)
            when = date.fromisoformat(brew.created_at[:10])
            parts = [f"{when.day} {when:%b}", method.label if method else brew.method, _e(brew.bean_name or "?")]
            if brew.grind_setting is not None:
                parts.append(f"grind {brew.grind_setting:g}")
            ratio = BrewText.ratio({"dose_g": brew.dose_g, "yield_g": brew.yield_g, "water_g": brew.water_g})
            if ratio:
                parts.append(ratio)
            if brew.extraction:
                parts.append(brew.extraction)
            if brew.rating:
                parts.append("★" * brew.rating)
            lines.append(" · ".join(parts))
            if brew.tasting_notes:
                lines.append(f"   <i>{_e(', '.join(brew.tasting_notes))}</i>")
        return "\n".join(lines)


__all__ = [
    "BeanText",
    "BrewText",
    "HelpText",
    "SetupText",
    "WelcomeText",
    "bean_label",
    "format_value",
    "roast_age",
]
