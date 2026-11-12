import uuid

from my_llm_app.agent.graph import build_graph
from my_llm_app.agent.nodes import infeasible_report
from my_llm_app.config import Settings

SETTINGS = Settings(llm_base_url="http://unused/v1", llm_model="m", llm_api_key="k", searxng_url="http://unused")

NO = {
    "verdict": "no",
    "reason": "研究室内のミーティングの写真は公開されていないため",
    "infeasible_parts": ["昨日の研究室のミーティングのホワイトボードの写真"],
    "suggestions": ["出席者に写真が残っていないか確認する"],
}


class FakeLLM:
    """check_feasibility の判定だけを返す。それ以外の呼び出しがあればテスト失敗。"""

    def __init__(self, verdict: dict):
        self.verdict = verdict
        self.calls = []

    def chat_json(self, system, user, schema, temperature=0.2):
        self.calls.append(system[:20])
        if "verdict" in schema["properties"]:
            return self.verdict
        raise AssertionError("調べられない依頼で、判定以外の LLM 呼び出しが行われた")

    def chat_text(self, system, user, temperature=0.5):
        raise AssertionError("調べられない依頼で、回答の生成が行われた")


def run(verdict: dict, request: str) -> dict:
    llm = FakeLLM(verdict)
    graph = build_graph(SETTINGS, llm)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    graph.invoke({"request": request}, config)
    return graph.get_state(config).values, llm


def test_infeasible_request_is_reported_without_searching():
    state, llm = run(NO, "昨日の研究室のミーティングのホワイトボードの写真を探して")
    assert len(llm.calls) == 1                       # 判定の 1 回だけ。検索も回答生成もしない
    assert "公開されている情報からは調べられない" in state["answer"]
    assert "出席者に写真が残っていないか確認する" in state["answer"]
    assert [t["node"] for t in state["trace"]] == ["check_feasibility", "report_infeasible"]


def test_report_lists_parts_reason_attempts_and_suggestions():
    text = infeasible_report("依頼", NO)
    for heading in ("### 調べられないこと", "### 理由", "### 試したこと", "### 代わりにできること"):
        assert heading in text
    assert "検索は行っていません" in text


def test_report_without_parts_falls_back_to_request():
    text = infeasible_report("来年の日経平均の終値", {"verdict": "no", "reason": "未来の事実", "infeasible_parts": [],
                                                  "suggestions": []})
    assert "- 来年の日経平均の終値" in text
    assert "代わりにできること" not in text


def test_unsure_goes_on_to_research():
    from my_llm_app.agent.nodes import route_feasibility
    for verdict in ("yes", "partial", "unsure"):
        assert route_feasibility({"feasibility": {"verdict": verdict}}) == "decide"
    assert route_feasibility({"feasibility": {"verdict": "no"}}) == "report_infeasible"
