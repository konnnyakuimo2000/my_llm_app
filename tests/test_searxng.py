from my_llm_app.tools.searxng import parse_response


def test_parse_response():
    data = {
        "results": [
            {"title": "水星 - Wikipedia", "url": "https://ja.wikipedia.org/wiki/水星",
             "content": " 太陽系の惑星 ", "engines": ["brave", "google cse"]},
            {"title": "URL なし", "content": "x"},
            {"title": "3件目", "url": "https://example.com/3", "content": None, "engines": []},
        ],
        "suggestions": ["水星 温度"],
        "unresponsive_engines": [["duckduckgo", "timeout"]],
    }
    r = parse_response(data, limit=10)
    assert [w.url for w in r.results] == ["https://ja.wikipedia.org/wiki/水星", "https://example.com/3"]
    assert r.results[0].snippet == "太陽系の惑星"
    assert r.results[1].snippet == ""
    assert r.suggestions == ["水星 温度"]
    assert r.unresponsive == ["duckduckgo"]
