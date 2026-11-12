from unittest.mock import patch

from my_llm_app.agent.guard import check_decision
from my_llm_app.agent.nodes import Nodes, dominant, rank

FUJI = {"id": "Q39231", "label": "富士山", "description": "静岡県・山梨県にある山", "sitelinks": 146}
FUJI_GUNMA = {"id": "Q1", "label": "富士山", "description": "群馬県桐生市にある山", "sitelinks": 8}
FUJI_SHIP = {"id": "Q2", "label": "富士山", "description": "軍艦", "sitelinks": 5}
NO_LABEL = {"id": "Q3", "label": "", "description": "", "sitelinks": 1}
PYTHON = {"id": "Q28865", "label": "Python", "description": "プログラミング言語", "sitelinks": 164}
SNAKE = {"id": "Q4", "label": "ニシキヘビ科", "description": "爬虫類の科", "sitelinks": 79}


class FakeLLM:
    def __init__(self, matched_ids):
        self.matched_ids = matched_ids

    def chat_json(self, system, user, schema, temperature=0.2):
        return {"matched_ids": self.matched_ids}


def ask(state, answer, matched_ids):
    nodes = Nodes(settings=None, llm=FakeLLM(matched_ids))
    with patch("my_llm_app.agent.nodes.interrupt", return_value=answer):
        return nodes.ask_user({**state, "decision": {"action": "ask_user", "question": "Q?\n1. ..."}})


def test_rank_drops_unlabeled_and_sorts_by_sitelinks():
    assert [c["id"] for c in rank([FUJI_SHIP, NO_LABEL, FUJI])] == ["Q39231", "Q2"]


def test_dominant():
    assert dominant([FUJI_GUNMA, FUJI, FUJI_SHIP]) == FUJI      # 146 >= 4 * 8
    assert dominant([PYTHON, SNAKE]) is None                    # 164 < 4 * 79
    assert dominant([FUJI]) is None


def test_text_answer_resolves_target_immediately():
    # Python のケース: 「プログラミング言語」と答えたら、その場で対象を決める
    out = ask({"request": "Pythonについて調べて", "candidates": [PYTHON, SNAKE]}, "プログラミング言語", ["Q28865"])
    assert out["target"] == PYTHON
    assert out["questions_asked"] == 1


def test_ambiguous_answer_narrows_candidates():
    # 「山です」に合う候補が複数で、偏りがない → 候補を絞り、対象は決めない
    gunma2 = {**FUJI_GUNMA, "id": "Q5", "description": "茨城県の山", "sitelinks": 6}
    out = ask({"request": "富士山について調べて", "candidates": [FUJI_GUNMA, gunma2, FUJI_SHIP]}, "山です",
              ["Q1", "Q5"])
    assert [c["id"] for c in out["candidates"]] == ["Q1", "Q5"]
    assert "target" not in out


def test_ambiguous_answer_with_dominant_candidate_picks_it_with_assumption():
    out = ask({"request": "富士山について調べて", "candidates": [FUJI, FUJI_GUNMA, FUJI_SHIP]}, "山です",
              ["Q39231", "Q1"])
    assert out["target"] == FUJI
    assert "一般に" in out["assumptions"][0]


def test_answer_outside_choices_leaves_target_open():
    out = ask({"request": "アマゾンについて調べて", "candidates": [PYTHON, SNAKE]}, "川のほうです", [])
    assert "target" not in out
    assert out["clarifications"] == ["川のほうです"]


def test_same_question_is_not_repeated():
    state = {"request": "富士山について調べて", "searched": ["富士山"], "candidates": [FUJI_GUNMA, FUJI_SHIP],
             "target": None, "questions_asked": 1, "steps": 3}
    from my_llm_app.agent.guard import build_question
    state["last_question"] = build_question(state)
    d = check_decision(state, {"action": "ask_user", "reason": ""})
    assert d["action"] == "respond"
