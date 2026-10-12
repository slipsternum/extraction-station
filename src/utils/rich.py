from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional, Sequence

from telebot import types

from src.models.coffee import BREW_METHODS, CLARITY_LABELS, EXTRACTION_LABELS, BrewField
from src.utils.text import EXTRACTION_EMOJI, BrewText, bean_label, format_value, roast_age, started_label

RichText = Any
Block = types.InputRichBlock

B = types.RichTextBold
I = types.RichTextItalic


def _p(*parts: RichText) -> Block:
    return types.InputRichBlockParagraph(list(parts) if len(parts) > 1 else parts[0])


def _heading(text: RichText, size: int = 3) -> Block:
    return types.InputRichBlockSectionHeading(text, size)


def _cell(text: RichText, *, header: bool = False) -> types.RichBlockTableCell:
    return types.RichBlockTableCell(align="left", valign="middle", text=text, is_header=header or None)


def _table(header: Optional[Sequence[str]], rows: Sequence[Sequence[RichText]]) -> Block:
    cells = [[_cell(h, header=True) for h in header]] if header else []
    cells += [[_cell(value) for value in row] for row in rows]
    return types.InputRichBlockTable(cells, is_striped=True, is_compact=True)


def _list(items: Sequence[RichText]) -> Block:
    return types.InputRichBlockList([types.InputRichBlockListItem([_p(item)]) for item in items])


def _details(summary: RichText, blocks: list[Block], *, is_open: bool = False) -> Block:
    return types.InputRichBlockDetails(summary, blocks, is_open=is_open or None)


def _message(blocks: list[Block]) -> types.InputRichMessage:
    return types.InputRichMessage(blocks=blocks, skip_entity_detection=True)


def _stars(rating: int) -> str:
    return "★" * rating + "☆" * (5 - rating)


def _field(method_key: str, column: str) -> Optional[BrewField]:
    return next((f for f in BREW_METHODS[method_key].fields if f.column == column), None)


def _verdict(draft: Mapping[str, Any]) -> list[Block]:
    """Extraction, clarity and rating on one line, then tasting notes and the comment."""
    parts = []
    if draft.get("extraction"):
        parts.append(f"{EXTRACTION_EMOJI[draft['extraction']]} {EXTRACTION_LABELS[draft['extraction']]}")
    if draft.get("clarity"):
        parts.append(f"{CLARITY_LABELS[draft['clarity']]} cup")
    if draft.get("rating"):
        parts.append(_stars(draft["rating"]))
    blocks = [_p(" · ".join(parts))] if parts else []
    if draft.get("tasting_notes"):
        blocks.append(_p("👅 ", I(", ".join(draft["tasting_notes"][:12]))))
    if draft.get("comment"):
        blocks.append(_p(f"💬 {draft['comment'][:500]}"))
    return blocks


def _bean_blocks(bean: Mapping[str, Any], title: RichText) -> list[Block]:
    blocks = [_p(title)]
    age = roast_age(bean.get("roast_date"))
    if age:
        blocks.append(_p(I(age)))
    return blocks


def _photo_block(photos: Sequence[str]) -> Optional[Block]:
    items = [types.InputRichBlockPhoto(types.InputMediaPhoto(photo)) for photo in photos]
    if len(items) > 1:
        return types.InputRichBlockCollage(items)
    return items[0] if items else None


class BrewRich:
    @staticmethod
    def card(
        draft: Mapping[str, Any], ctx: Mapping[str, Any], *, header: str, footer: Optional[str] = None
    ) -> types.InputRichMessage:
        """A brew's recipe as a table under the method and beans, then the tasting verdict."""
        method = BREW_METHODS[draft["method"]]
        bean = next((b for b in ctx["beans"] if b["id"] == draft["bean_id"]), {})
        blocks = [_heading(header), *_bean_blocks(bean, [B(method.label), f" · {bean_label(bean)}"])]
        rows: list[list[RichText]] = []
        if draft.get("grind_setting") is not None:
            rows.append(["Grind", f"{draft['grind_setting']:g}"])
        for label, key in (("Grinder", "grinder_name"), ("Brewer", "brewer_name")):
            if draft.get(key):
                rows.append([label, draft[key]])
        rows += [[f.label, format_value(draft[f.column], f)] for f in method.fields if draft.get(f.column) is not None]
        ratio = BrewText.ratio(draft)
        if ratio:
            rows.append(["Ratio", ratio])
        if rows:
            blocks.append(_table(None, rows))
        blocks += _verdict(draft)
        if footer:
            blocks.append(types.InputRichBlockFooter(footer))
        return _message(blocks)

    @staticmethod
    def history(brews: Sequence[Any], brewing: Sequence[Any] = ()) -> types.InputRichMessage:
        """Brews in progress as a list, recent brews as a table, tasting notes collapsed."""
        blocks: list[Block] = []
        if brewing:
            blocks.append(_heading("⏳ Brewing"))
            items = []
            for brew in brewing:
                method = BREW_METHODS.get(brew.method)
                label = method.label if method else brew.method
                items.append([B(label), f" · {brew.bean_name or '?'} · ", I(started_label(brew.created_at))])
            blocks.append(_list(items))
        if brews:
            blocks.append(_heading("📒 Recent brews"))
            rows = []
            notes = []
            for brew in brews:
                method = BREW_METHODS.get(brew.method)
                label = method.label if method else brew.method
                day = date.fromisoformat(brew.created_at[:10])
                when = f"{day.day} {day:%b}"
                ratio = BrewText.ratio({"dose_g": brew.dose_g, "yield_g": brew.yield_g, "water_g": brew.water_g})
                result = " ".join(
                    part
                    for part in (
                        EXTRACTION_EMOJI.get(brew.extraction or "", ""),
                        "★" * brew.rating if brew.rating else "",
                    )
                    if part
                )
                grind = f"{brew.grind_setting:g}" if brew.grind_setting is not None else "—"
                rows.append([when, label, _short(brew.bean_name or "?", 18), grind, ratio or "—", result or "—"])
                if brew.tasting_notes:
                    notes.append([B(f"{when} · {label}: "), ", ".join(brew.tasting_notes)])
            blocks.append(_table(("Date", "Method", "Beans", "Grind", "Ratio", "Result"), rows))
            if notes:
                blocks.append(_details("👅 Tasting notes", [_list(notes)]))
        return _message(blocks)

    @staticmethod
    def advice(advice: Mapping[str, Any], draft: Mapping[str, Any]) -> types.InputRichMessage:
        """Diagnosis, the one change, this brew vs the suggested recipe, other levers collapsed."""
        method_key = draft["method"]
        blocks = [_heading("🤖 Next brew")]
        if advice.get("diagnosis"):
            blocks.append(_p(I(advice["diagnosis"])))
        blocks.append(_p(B("➡️ Try: "), advice["primary_change"]))
        recipe = advice.get("next_brew") or {}
        rows = []
        if recipe.get("grind_setting") is not None:
            now = draft.get("grind_setting")
            rows.append(["Grind", f"{now:g}" if now is not None else "—", f"{recipe['grind_setting']:g}"])
        for field in BREW_METHODS[method_key].fields:
            if recipe.get(field.column) is not None:
                rows.append([field.label, format_value(draft.get(field.column), field), format_value(recipe[field.column], field)])
        if rows:
            blocks.append(_table(("", "This brew", "Next"), _bold_changes(rows, changed=2, against=1)))
        if advice.get("alternatives"):
            blocks.append(_details("Other ways in", [_list(advice["alternatives"])]))
        if advice.get("taste_for"):
            blocks.append(_p(B("👅 Taste for: "), advice["taste_for"]))
        blocks.append(types.InputRichBlockFooter("I'll bring this up on your next /brew with these beans."))
        return _message(blocks)


class ProgressRich:
    @staticmethod
    def card(
        draft: Mapping[str, Any],
        ctx: Mapping[str, Any],
        *,
        attempt: int,
        previous: Any = None,
        photos: Sequence[str] = (),
    ) -> types.InputRichMessage:
        """Progress post: photos as a collage, then this attempt against the last one."""
        method = BREW_METHODS[draft["method"]]
        bean = next((b for b in ctx["beans"] if b["id"] == draft["bean_id"]), {})
        blocks: list[Block] = []
        photo = _photo_block(photos)
        if photo:
            blocks.append(photo)
        blocks.append(_heading(f"{method.label} · attempt {attempt}"))
        blocks += _bean_blocks(bean, f"☕ {bean_label(bean)}")

        def show(values: Mapping[str, Any], column: str) -> Optional[str]:
            if column == "grind_setting":
                value = values.get(column)
                return f"{value:g}" if value is not None else None
            if column == "ratio":
                return BrewText.ratio(values)
            field = _field(draft["method"], column)
            return format_value(values[column], field) if field and values.get(column) is not None else None

        before = {
            column: getattr(previous, column, None)
            for column in ("grind_setting", "dose_g", "yield_g", "water_g", "temp_c", "time_s")
        }
        labels = {f.column: f.label for f in method.fields}
        rows = []
        for column, label in (("grind_setting", "Grind"), ("dose_g", "Dose"), ("ratio", "Ratio"),
                              ("time_s", labels.get("time_s")), ("temp_c", labels.get("temp_c"))):
            now = show(draft, column)
            if label and now is not None:
                rows.append([label, now] + ([show(before, column) or "—"] if previous else []))
        if rows:
            header = ("", "This brew", "Last time") if previous else ("", "This brew")
            blocks.append(_table(header, _bold_changes(rows, changed=1, against=2) if previous else rows))
        if draft.get("grinder_name"):
            blocks.append(_p(f"⚙️ {draft['grinder_name']}"))
        blocks += _verdict({**draft, "comment": _short(draft.get("comment") or "", 200)})
        return _message(blocks)


def _bold_changes(rows: list[list[RichText]], *, changed: int, against: int) -> list[list[RichText]]:
    """Bold the ``changed`` column wherever it differs from a known value in the ``against`` column."""
    marked = []
    for row in rows:
        row = list(row)
        if row[against] not in (row[changed], "—"):
            row[changed] = B(row[changed])
        marked.append(row)
    return marked


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


__all__ = ["BrewRich", "ProgressRich"]
