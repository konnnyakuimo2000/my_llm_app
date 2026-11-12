from my_llm_app.agent.guard import build_question, check_decision
from my_llm_app.agent.state import MAX_QUESTIONS, MAX_STEPS

CANDIDATES = [
    {"id": "Q308", "label": "水星", "description": "太陽系の惑星"},
    {"id": "Q925", "label": "水銀", "description": "元素"},
    {"id": "Q613883", "label": "マーキュリー", "description": "フォードの自動車ブランド"},
]


def ambiguous_state(**kw):
    return {"request": "マーキュリーについて調べて", "searched": ["マーキュリー"],
            "candidates": CANDIDATES, "target": None, "questions_asked": 0, "steps": 2, **kw}


def test_first_step_ask_is_turned_into_search():
    state = {"request": "マーキュリーについて調べて", "searched": [], "steps": 0}
    d = check_decision(state, {"action": "ask_user", "reason": "", "question": "どれ？"})
    assert d["action"] == "search"
    assert d["query"] == "マーキュリーについて調べて"


def test_respond_while_ambiguous_becomes_ask_user():
    # 例 A のパターン 2（適当に答える）を止める
    d = check_decision(ambiguous_state(), {"action": "respond", "reason": "全部説明する"})
    assert d["action"] == "ask_user"
    assert "guard" in d
    assert "1. 水星" in d["question"]


def test_respond_allowed_after_question_limit():
    d = check_decision(ambiguous_state(questions_asked=MAX_QUESTIONS), {"action": "respond", "reason": ""})
    assert d["action"] == "respond"


def test_ask_user_after_limit_becomes_respond():
    d = check_decision(ambiguous_state(questions_asked=MAX_QUESTIONS), {"action": "ask_user", "reason": ""})
    assert d["action"] == "respond"


def test_respond_allowed_when_target_resolved():
    state = ambiguous_state(target=CANDIDATES[0])
    d = check_decision(state, {"action": "respond", "reason": ""})
    assert d["action"] == "respond"
    assert "guard" not in d


def test_duplicate_search_is_blocked():
    d = check_decision(ambiguous_state(), {"action": "search", "reason": "", "query": "マーキュリー"})
    assert d["action"] == "ask_user"


def test_step_limit_forces_respond():
    d = check_decision(ambiguous_state(steps=MAX_STEPS), {"action": "search", "reason": "", "query": "Mercury"})
    assert d["action"] == "respond"


def test_question_lists_candidates_with_numbers():
    q = build_question(ambiguous_state())
    assert "1. 水星（太陽系の惑星）" in q
    assert "3. マーキュリー（フォードの自動車ブランド）" in q


def test_pick_candidate_by_number():
    from my_llm_app.agent.nodes import pick_candidate
    assert pick_candidate("2", CANDIDATES)["label"] == "水銀"
    assert pick_candidate("２番", CANDIDATES)["label"] == "水銀"
    assert pick_candidate("9", CANDIDATES) is None
    assert pick_candidate("水星についてです", CANDIDATES) is None
