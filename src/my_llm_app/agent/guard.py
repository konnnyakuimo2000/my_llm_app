"""LLM が選んだ行動をプログラムで検査する。

横の判断（回数・上限・状態の数え上げ）はプログラムが担当する（設計書 3 章）。
特に「対象が決まらないまま答えてしまう」（例 A のパターン 2）を、ここで止める。
"""

from __future__ import annotations

from my_llm_app.agent.state import MAX_CANDIDATES, MAX_QUESTIONS, MAX_STEPS, AgentState, Decision


def build_question(state: AgentState) -> str:
    """候補から、選択肢付きの質問文をプログラムで作る（設計書 5.2 Q-2）。"""
    if state.get("questions_asked", 0) == 0:
        lines = [f"「{state.get('request', '')}」について、どれのことを指していますか？"]
    else:
        lines = ["回答に当てはまるものが複数あります。どれのことですか？"]
    for i, c in enumerate(state.get("candidates", [])[:MAX_CANDIDATES], 1):
        desc = f"（{c['description']}）" if c.get("description") else ""
        lines.append(f"{i}. {c['label']}{desc}")
    lines.append("番号か、具体的な内容で答えてください。上にない場合はその内容を書いてください。")
    return "\n".join(lines)


def is_ambiguous(state: AgentState) -> bool:
    return not state.get("target") and len(state.get("candidates", [])) >= 2


def check_decision(state: AgentState, decision: Decision) -> Decision:
    """LLM の選択を検査し、必要なら変える。変えた場合は guard に理由を入れる。"""
    d: Decision = dict(decision)  # type: ignore[assignment]
    action = d.get("action")
    asked = state.get("questions_asked", 0)

    # 上限: 行動の回数を使い切ったら、わかった範囲で答える
    if state.get("steps", 0) >= MAX_STEPS and action != "respond":
        return {**d, "action": "respond", "guard": "行動の上限に達したため、わかった範囲で応答する"}

    target = state.get("target")
    if action == "respond" and target and target.get("id") and not state.get("target_summary"):
        # 対象が決まったのに、その対象自体をまだ調べていない（聞き返しの回答で決まった場合など）
        query = target["label"]
        if query not in state.get("searched", []):
            return {**d, "action": "search", "query": query, "names": [target["label"]],
                    "guard": "対象が決まったので、応答の前にその対象を調べる"}

    if action == "respond" and is_ambiguous(state) and asked < MAX_QUESTIONS:
        # 例 A のパターン 2（適当な対象で答える・全部を平たく述べる）を防ぐ
        return {**d, "action": "ask_user", "question": build_question(state),
                "guard": "対象が特定できていないため、応答ではなく聞き返す"}

    if action == "ask_user":
        if asked >= MAX_QUESTIONS:
            return {**d, "action": "respond", "guard": "質問の上限に達したため、前提を明示して応答する"}
        if not state.get("searched"):
            # 調べればわかることは聞かない（設計書 5.2 Q-3）。まず調べる
            return {**d, "action": "search", "query": " ".join(d.get("names") or [state.get("request", "")]),
                    "guard": "まだ何も調べていないため、聞き返す前に調べる"}
        if is_ambiguous(state):
            # 質問文は候補一覧からプログラムが作る（選択肢を必ず付ける）
            d = {**d, "question": build_question(state)}
        if not d.get("question"):
            return {**d, "action": "respond", "guard": "質問する内容がないため応答する"}
        if d["question"] == state.get("last_question"):
            return {**d, "action": "respond", "guard": "同じ質問の繰り返しを防ぐため、前提を明示して応答する"}

    if action == "search":
        query = (d.get("query") or "").strip() or state.get("request", "")
        if query in state.get("searched", []):
            fallback = "ask_user" if is_ambiguous(state) and asked < MAX_QUESTIONS else "respond"
            extra = {"question": build_question(state)} if fallback == "ask_user" else {}
            return {**d, **extra, "action": fallback, "guard": f"同じ検索（{query}）の繰り返しを防ぐ"}
        d["query"] = query

    return d
