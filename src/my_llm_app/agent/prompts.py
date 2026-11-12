"""各ノードで LLM に渡す指示（プロンプト）とスキーマ。"""

from __future__ import annotations

import json

from my_llm_app.agent.state import AgentState

FEASIBILITY_SYSTEM = """あなたは、調査の依頼が「公開されている情報（Web・百科事典・公的機関・論文など）」で調べられるかを、
調査を始める前に判定する役です。

verdict:
- no: 依頼の中心が、公開情報では原理的に調べられないもの。例:
  - 公開されていない私的・内部の情報（特定の個人の私生活、家族の情報、社内や研究室の非公開の資料・会議の記録や写真、個人のメールやアカウントの中身）
  - まだ起きていない事実（将来の株価の終値、試合の結果、くじの当選番号）。ただし予報・予定・予測の記事が公開されているもの（天気予報、発売予定日など）は調べられる
  - 依頼者本人にしかわからないこと（依頼者の持ち物、依頼者の過去の行動）
- partial: 依頼の一部は調べられるが、一部は上の理由で調べられない
- unsure: 判断がつかない（調べてみないとわからない、マイナーなだけで公開されている可能性がある）
- yes: 公開情報で調べられる

ルール:
- マイナー・情報が少なそう、というだけでは no にしない（unsure か yes）。迷ったら unsure にする
- 実在する人物でも、公人や研究者の公開された経歴・業績は調べられる（yes）。私生活や非公開の情報は no
- infeasible_parts には、調べられない部分を短く書く（yes / unsure なら空）
- suggestions には、利用者が代わりにできることを 1〜3 個書く（例: 「出席者に写真が残っていないか確認する」「手元の資料を渡してもらえれば内容を整理できる」）。yes なら空"""

FEASIBILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["yes", "partial", "no", "unsure"]},
        "reason": {"type": "string"},
        "infeasible_parts": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": ["verdict", "reason", "infeasible_parts", "suggestions"],
}

DECIDE_SYSTEM = """あなたは調査エージェントの「次の行動」を決める役です。
利用者の依頼と、これまでにわかったこと・わからないことを見て、次の行動を 1 つ選びます。

行動:
- search: Web と百科事典を調べる。query に Web 検索の言葉を入れる
- ask_user: 利用者に聞き返す。question に質問を入れる
- respond: 調査結果を利用者に伝えて終わる

ルール:
- まだ何も調べていなければ、まず search する
- names には、どの行動を選んだときも必ず、依頼の対象を表す名前（百科事典で引く短い名前）を 1〜3 個入れる。カタカナ語や外国由来の言葉は原語（英語など）も入れる（例: ["マーキュリー", "Mercury"]）。対象が決まったら、その対象の正式な名前を入れる（例: ["水星"]）
- 依頼の対象に複数の意味があり、利用者がどれを指しているかわからないときは ask_user する。推測で 1 つに決めない
- 対象が決まったら、その対象について search して内容を集め、十分なら respond する
- 同じ検索の言葉を繰り返さない"""

DECIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["search", "ask_user", "respond"]},
        "reason": {"type": "string"},
        "query": {"type": "string"},
        "names": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "question": {"type": "string"},
    },
    "required": ["action", "reason", "names"],
}

UPDATE_SYSTEM = """あなたは調査エージェントの「状態を更新する」役です。
依頼・利用者の回答・現在の状態・新しい検索結果を読み、状態を更新して返します。

- known: わかったこと。text に短い文（60 文字以内）、source にその根拠の URL（Web 検索の結果の url、または Wikidata の項目の url）を 1 つ入れる。
  検索結果に書かれていないことは入れない。依頼や利用者の回答の言い換えは入れない
- unknown: まだわからないこと（例:「利用者がどの意味のマーキュリーを指しているか」）
- candidate_ids: 依頼の言葉が指しうる対象の候補を、Wikidata の項目の id（Q 番号）で返す。
  入力にある id だけを使い、書き写すときに番号を変えないこと。一般によく知られているもの（天体・元素・神話など）を先に、最大 8 件
- target_id: 利用者の回答などから対象が 1 つに決まった場合だけ、その候補の id。決まらなければ空文字

推測で target_id を決めないこと。利用者が答えていない段階で、複数の意味があるなら target_id は空文字にする。
「特定できた対象」がすでにある場合は、その id を target_id に入れる。
target_id が決まったら、known には target についての事実だけを残す（他の意味の説明は消す）。known は重要なものから最大 8 件。"""

UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "known": {"type": "array", "maxItems": 8, "items": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "source": {"type": "string"}},
            "required": ["text", "source"],
        }},
        "unknown": {"type": "array", "items": {"type": "string"}},
        "candidate_ids": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "target_id": {"type": "string"},
    },
    "required": ["known", "unknown", "candidate_ids", "target_id"],
}

MATCH_SYSTEM = """あなたは、利用者の回答が選択肢のどれを指しているかを判定する役です。
- 回答が明らかに指している選択肢の id を matched_ids に入れる
- 回答に当てはまる選択肢が複数あれば、すべて入れる（例: 回答が「山です」で、山の選択肢が 3 つあれば 3 つとも）
- 回答が選択肢にないものを指している場合（例: 選択肢に川がないのに「川のほうです」）は空にする。近いものを無理に選ばない"""

MATCH_SCHEMA = {
    "type": "object",
    "properties": {"matched_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["matched_ids"],
}


def match_user(question: str, answer: str, candidates: list) -> str:
    return json.dumps({
        "質問": question.splitlines()[0],
        "選択肢": [{"id": c["id"], "名前": c["label"], "説明": c["description"]} for c in candidates],
        "利用者の回答": answer,
    }, ensure_ascii=False, indent=1)


RESPOND_SYSTEM = """あなたは調査結果を利用者に伝える役です。
与えられた材料（対象の概要・わかったこと・出典）だけを使って、日本語で答えます。

- 材料にないことは書かない。推測で補わない
- 材料の各項目の末尾にある出典番号（[1] など）を、その事実を書いた文の後ろにそのまま付ける。番号を変えたり、別の事実に付け替えたりしない
- [出典なし] の項目は使わない
- 「置いた前提」がある場合は、冒頭にその文をそのまま書く
- 対象が特定できていない場合は、冒頭でそのことと、置いた前提を正直に書く
- 対象が特定できている場合は、その対象についてだけ書く。同名の別の意味の説明は書かない
- 「公開情報では調べられない部分」がある場合は、最後に「調べられなかったこと」としてその部分と理由を書く
- わからなかったことがあれば、最後に「わからなかったこと」として書く
- 出典一覧そのものは書かない（プログラムが付ける）"""


def _state_view(state: AgentState) -> dict:
    return {
        "依頼": state.get("request", ""),
        "利用者の回答": state.get("clarifications", []),
        "わかったこと": state.get("known", []),
        "わからないこと": state.get("unknown", []),
        "候補": state.get("candidates", []),
        "特定できた対象": state.get("target"),
        "実行した検索": state.get("searched", []),
        "質問した回数": state.get("questions_asked", 0),
        "公開情報では調べられない部分（調べない）": (state.get("feasibility") or {}).get("infeasible_parts", []),
    }


def decide_user(state: AgentState) -> str:
    return json.dumps(_state_view(state), ensure_ascii=False, indent=1)


def update_user(state: AgentState, query: str, entities: list, web: list) -> str:
    return json.dumps({
        "現在の状態": _state_view(state),
        "今回の検索の言葉": query,
        "Wikidata の項目": [{"id": e.id, "label": e.label, "description": e.description, "url": e.url}
                           for e in entities],
        "Web 検索の結果": [{"title": w.title, "url": w.url, "snippet": w.snippet[:200]} for w in web],
    }, ensure_ascii=False, indent=1)


def respond_user(state: AgentState, sources: list[dict]) -> str:
    """sources は出典番号の順。わかったことには、プログラムが出典番号を付けて渡す。"""
    number = {s["url"]: i for i, s in enumerate(sources, 1)}
    summary = state.get("target_summary", "")
    summary_url = state.get("summary_url", "")
    facts = [f"{k['text']} [{number[k['source']]}]" if k.get("source") in number else f"{k['text']} [出典なし]"
             for k in state.get("known", [])]
    return json.dumps({
        "依頼": state.get("request", ""),
        "利用者の回答": state.get("clarifications", []),
        "特定できた対象": state.get("target"),
        "置いた前提": state.get("assumptions", []),
        "公開情報では調べられない部分": (state.get("feasibility") or {}).get("infeasible_parts", []),
        "対象の概要": f"{summary} [{number[summary_url]}]" if summary and summary_url in number else "",
        "わかったこと": facts,
        "わからないこと": state.get("unknown", []),
    }, ensure_ascii=False, indent=1)
