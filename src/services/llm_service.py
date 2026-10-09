from __future__ import annotations

import base64
import json
import re
from typing import Any, Optional

from openai import AsyncOpenAI

from src.core.logging import logger

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class LLMService:
    """Thin wrapper over an OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        *,
        model: Optional[str],
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.client: Optional[AsyncOpenAI] = None
        if model:
            self.client = AsyncOpenAI(api_key=api_key or "unused", base_url=base_url, timeout=timeout)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    @staticmethod
    def image_part(data: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        encoded = base64.b64encode(data).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        if self.client is None:
            raise RuntimeError("LLM is not configured; set OPENAI_MODEL.")
        response = await self.client.chat.completions.create(model=self.model, messages=messages, **kwargs)
        return response.choices[0].message.content or ""

    async def complete_json(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Return the first JSON object in the reply, tolerating code fences and prose."""
        content = await self.complete(messages, **kwargs)
        match = _JSON_BLOCK.search(content)
        if not match:
            raise ValueError("LLM reply contained no JSON object")
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            logger.debug("Unparseable LLM reply: %s", content)
            raise ValueError("LLM reply contained invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("LLM reply JSON is not an object")
        return value

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()


__all__ = ["LLMService"]
