"""Wikidata / Wikipedia の公式 API（Tier 2。SearXNG 経由にせず直接呼ぶ。設計書 6.6 G-2）。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from my_llm_app.config import USER_AGENT

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_HEADERS = {"User-Agent": USER_AGENT}


@dataclass
class Entity:
    id: str
    label: str
    description: str

    @property
    def url(self) -> str:
        return f"https://www.wikidata.org/wiki/{self.id}"


@dataclass
class WikiSummary:
    title: str
    extract: str
    url: str


def search_entities(query: str, languages: tuple[str, ...] = ("ja", "en"), limit: int = 10,
                    timeout: float = 30.0) -> list[Entity]:
    """同名の候補を探す。

    「マーキュリー」で日本語だけを検索すると惑星（日本語名は「水星」）が出てこないため、
    複数の言語で検索して ID で重複を除く。説明文はできるだけ日本語で受け取る。
    """
    seen: dict[str, Entity] = {}
    for lang in languages:
        r = httpx.get(
            WIKIDATA_API,
            params={"action": "wbsearchentities", "search": query, "language": lang,
                    "uselang": "ja", "limit": limit, "format": "json"},
            headers=_HEADERS,
            timeout=timeout,
        )
        r.raise_for_status()
        for item in r.json().get("search", []):
            if item["id"] not in seen:
                seen[item["id"]] = Entity(
                    id=item["id"],
                    label=item.get("label", ""),
                    description=item.get("description", ""),
                )
    return list(seen.values())


def get_entities(ids: list[str], timeout: float = 30.0) -> dict[str, Entity]:
    """ID から項目の名前と説明を取る（日本語優先、なければ英語）。"""
    if not ids:
        return {}
    r = httpx.get(
        WIKIDATA_API,
        params={"action": "wbgetentities", "ids": "|".join(ids[:50]), "props": "labels|descriptions",
                "languages": "ja|en", "format": "json"},
        headers=_HEADERS,
        timeout=timeout,
    )
    r.raise_for_status()

    def pick(d: dict) -> str:
        return (d.get("ja") or d.get("en") or {}).get("value", "")

    return {
        eid: Entity(id=eid, label=pick(e.get("labels", {})), description=pick(e.get("descriptions", {})))
        for eid, e in r.json().get("entities", {}).items()
        if "missing" not in e
    }


def summary_for_entity(entity_id: str, timeout: float = 30.0) -> WikiSummary | None:
    """Wikidata の項目に対応する Wikipedia 記事の冒頭（日本語優先、なければ英語）を返す。"""
    r = httpx.get(
        WIKIDATA_API,
        params={"action": "wbgetentities", "ids": entity_id, "props": "sitelinks",
                "sitefilter": "jawiki|enwiki", "format": "json"},
        headers=_HEADERS,
        timeout=timeout,
    )
    r.raise_for_status()
    sitelinks = r.json().get("entities", {}).get(entity_id, {}).get("sitelinks", {})
    for site, lang in (("jawiki", "ja"), ("enwiki", "en")):
        if site not in sitelinks:
            continue
        title = sitelinks[site]["title"]
        s = httpx.get(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}",
            headers=_HEADERS,
            timeout=timeout,
        )
        if s.status_code != 200:
            continue
        data = s.json()
        return WikiSummary(
            title=data.get("title", title),
            extract=data.get("extract", ""),
            url=data.get("content_urls", {}).get("desktop", {}).get("page",
                f"https://{lang}.wikipedia.org/wiki/{quote(title)}"),
        )
    return None
