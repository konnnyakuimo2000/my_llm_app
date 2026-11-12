"""LLM サーバー (OpenAI 互換 API) の呼び出し。"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI

from my_llm_app.config import Settings

# 研究室サーバーは共有で同時処理数 4。こちらからの同時リクエストはそれ以下に抑える
_MAX_CONCURRENCY = 2
_semaphore = threading.Semaphore(_MAX_CONCURRENCY)
# 研究室サーバーが一時的に応答しなくなることがあるため、間隔を広げながらやり直す
_RETRY_WAITS = (10, 30, 60)

log = logging.getLogger(__name__)


class LLM:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.llm_model
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout,
        )

    def _create(self, messages: list[dict], **kwargs: Any) -> str:
        for attempt in range(len(_RETRY_WAITS) + 1):
            started = time.perf_counter()
            try:
                with _semaphore:
                    r = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        # 思考モード OFF（応答速度を優先）
                        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                        **kwargs,
                    )
            except (APIConnectionError, APITimeoutError, InternalServerError) as e:
                if attempt == len(_RETRY_WAITS):
                    raise
                wait = _RETRY_WAITS[attempt]
                log.warning("LLM に接続できません（%s）。%d 秒後にやり直します", type(e).__name__, wait)
                time.sleep(wait)
                continue
            usage = r.usage
            log.info("llm: %.1fs (prompt %s, completion %s tokens)", time.perf_counter() - started,
                     usage.prompt_tokens if usage else "?", usage.completion_tokens if usage else "?")
            return r.choices[0].message.content or ""
        raise RuntimeError("unreachable")

    def chat_json(self, system: str, user: str, schema: dict, temperature: float = 0.2) -> dict:
        """JSON スキーマに沿った出力を返す。壊れた JSON なら 1 回だけやり直す。"""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response_format = {"type": "json_schema", "json_schema": {"name": "output", "schema": schema}}
        last_error: Exception | None = None
        for _ in range(2):
            text = self._create(messages, response_format=response_format, temperature=temperature)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = e
        raise ValueError(f"LLM の出力が JSON になりませんでした: {last_error}")

    def chat_text(self, system: str, user: str, temperature: float = 0.5) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return self._create(messages, temperature=temperature)
