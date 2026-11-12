import json

from my_llm_app.agent.nodes import collect_sources
from my_llm_app.agent.prompts import respond_user

STATE = {
    "request": "マーキュリーについて調べて",
    "target_summary": "水星は太陽系の惑星。",
    "summary_url": "https://ja.wikipedia.org/wiki/水星",
    "known": [
        {"text": "直径は約 4,880 km", "source": "https://example.com/a"},
        {"text": "公転周期は 88 日", "source": "https://ja.wikipedia.org/wiki/水星"},
        {"text": "根拠のない記述", "source": ""},
        {"text": "表面はクレーターに覆われている", "source": "https://example.com/a"},
    ],
    "pages": {"https://ja.wikipedia.org/wiki/水星": "Wikipedia: 水星", "https://example.com/a": "A"},
}


def test_collect_sources_orders_summary_first_without_duplicates():
    sources = collect_sources(STATE)
    assert [s["url"] for s in sources] == ["https://ja.wikipedia.org/wiki/水星", "https://example.com/a"]
    assert sources[0]["title"] == "Wikipedia: 水星"


def test_respond_input_numbers_each_fact_by_its_own_source():
    data = json.loads(respond_user(STATE, collect_sources(STATE)))
    assert data["対象の概要"].endswith("[1]")
    assert data["わかったこと"] == [
        "直径は約 4,880 km [2]",
        "公転周期は 88 日 [1]",
        "根拠のない記述 [出典なし]",
        "表面はクレーターに覆われている [2]",
    ]
