"""SearXNG による Web 検索（候補を広く集める入り口。設計書 6.6）。"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from my_llm_app.config import USER_AGENT


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str
    engines: list[str]


@dataclass
class WebSearchResponse:
    results: list[WebResult]
    suggestions: list[str] = field(default_factory=list)
    # 応答しなかったエンジン（報告で申告するために記録する。設計書 G-5, G-6）
    unresponsive: list[str] = field(default_factory=list)


def parse_response(data: dict, limit: int) -> WebSearchResponse:
    results = [
        WebResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=(r.get("content") or "").strip(),
            engines=r.get("engines", []),
        )
        for r in data.get("results", [])[:limit]
        if r.get("url")
    ]
    return WebSearchResponse(
        results=results,
        suggestions=data.get("suggestions", []),
        unresponsive=[e[0] if isinstance(e, list) else str(e) for e in data.get("unresponsive_engines", [])],
    )


def web_search(base_url: str, query: str, limit: int = 8, timeout: float = 30.0) -> WebSearchResponse:
    r = httpx.get(
        f"{base_url}/search",
        params={"q": query, "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    r.raise_for_status()
    return parse_response(r.json(), limit)
