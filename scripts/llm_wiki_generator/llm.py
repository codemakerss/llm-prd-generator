from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import Settings


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.available = all(
            [
                settings.llm_provider == "openai_compatible",
                settings.llm_base_url,
                settings.llm_api_key,
                settings.llm_model,
            ]
        )
        self.client = None
        if self.available:
            self.client = OpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                timeout=settings.llm_timeout,
            )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.available or self.client is None:
            raise RuntimeError("LLM is not configured")

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Model did not return JSON")
        return json.loads(content[start : end + 1])

    def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self.available or self.client is None:
            raise RuntimeError("LLM is not configured")

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
