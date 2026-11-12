"""グラフのノード。

- decide:   LLM が次の行動を選び、プログラムが検査する（guard.py）
- search:   Wikidata（同名候補）と SearXNG（Web）を調べ、LLM が状態を更新する
- ask_user: 利用者に聞き返す（interrupt で一時停止）
- respond:  集めた材料から回答を作る
"""

from __future__ import annotations

import logging
import time

from langgraph.types import interrupt

from my_llm_app.agent import prompts
from my_llm_app.agent.guard import check_decision
from my_llm_app.agent.state import AgentState, Candidate, Source
from my_llm_app.config import Settings
from my_llm_app.llm import LLM
from my_llm_app.tools import searxng, wikimedia

log = logging.getLogger(__name__)


class Nodes:
    def __init__(self, settings: Settings, llm: LLM) -> None:
        self.settings = settings
        self.llm = llm

    def decide(self, state: AgentState) -> dict:
        raw = self.llm.chat_json(prompts.DECIDE_SYSTEM, prompts.decide_user(state), prompts.DECIDE_SCHEMA)
        decision = check_decision(state, raw)
        log.info("decide: %s (%s)%s", decision["action"], decision.get("reason", ""),
                 f" [guard: {decision['guard']}]" if decision.get("guard") else "")
        return {
            "decision": decision,
            "steps": state.get("steps", 0) + 1,
            "trace": [{"node": "decide", "llm": raw, "decision": decision}],
        }

    def search(self, state: AgentState) -> dict:
        decision = state["decision"]
        query = decision["query"]
        started = time.perf_counter()
        errors: list[str] = []

        # Wikidata は名前の前方一致で引くため、長い検索文ではなく短い名前で引く（横の展開はプログラム）
        names = [n.strip() for n in decision.get("names", []) if n.strip()] or [query.split()[0]]
        entities: list[wikimedia.Entity] = []
        for name in names[:3]:
            try:
                found = wikimedia.search_entities(name, limit=8)
            except Exception as e:  # noqa: BLE001 - 失敗は記録して続ける
                errors.append(f"wikidata({name}): {e}")
                continue
            have = {x.id for x in entities}
            entities += [e for e in found if e.id not in have]
        try:
            web = searxng.web_search(self.settings.searxng_url, query)
        except Exception as e:  # noqa: BLE001
            web, errors = searxng.WebSearchResponse(results=[]), errors + [f"searxng: {e}"]

        update = self.llm.chat_json(
            prompts.UPDATE_SYSTEM,
            prompts.update_user(state, query, entities, web.results),
            prompts.UPDATE_SCHEMA,
        )

        # LLM には id を選ばせるだけにし、実際に取得した項目にある id だけを認める。
        # 名前と説明は Wikidata の実データで埋める（LLM の書き写し間違い・作り話の防止）
        valid_ids = list(dict.fromkeys([e.id for e in entities] + [c["id"] for c in state.get("candidates", [])]))
        chosen = [i for i in update.get("candidate_ids", []) if i in valid_ids]
        target_id = update.get("target_id", "")
        target_id = target_id if target_id in valid_ids else ""
        try:
            info = wikimedia.get_entities(list(dict.fromkeys(chosen + [target_id] if target_id else chosen)))
        except Exception as e:  # noqa: BLE001
            errors.append(f"wikidata(get): {e}")
            info = {e.id: e for e in entities}
        candidates = [as_candidate(info[i]) for i in chosen if i in info] or state.get("candidates", [])
        target = state.get("target") or (as_candidate(info[target_id]) if target_id in info else None)

        # 根拠の URL は、実際に取得した検索結果・項目のものだけを認める（設計書 M-4 の簡易版）
        pages = {**state.get("pages", {}),
                 **{w.url: w.title for w in web.results},
                 **{e.url: f"Wikidata: {e.label}" for e in entities}}
        known = [{"text": k["text"], "source": k["source"] if k.get("source") in pages else ""}
                 for k in update["known"]]

        result: dict = {
            "known": known,
            "unknown": update["unknown"],
            "candidates": candidates,
            "target": target,
            "searched": state.get("searched", []) + [query],
            "unresponsive": sorted(set(state.get("unresponsive", []) + web.unresponsive)),
            "pages": pages,
        }

        # 対象が決まったら、Wikipedia の概要を取る（Tier 2）
        current = result["target"]
        if current and current.get("id") and not state.get("target_summary"):
            try:
                ws = wikimedia.summary_for_entity(current["id"])
            except Exception as e:  # noqa: BLE001
                ws = None
                errors.append(f"wikipedia: {e}")
            if ws:
                pages[ws.url] = f"Wikipedia: {ws.title}"
                result.update(target_summary=ws.extract, summary_url=ws.url)

        log.info("search: %r names=%s -> wikidata %d, web %d (%.1fs)", query, names, len(entities),
                 len(web.results), time.perf_counter() - started)
        result["trace"] = [{
            "node": "search", "query": query, "names": names, "errors": errors,
            "wikidata": [e.__dict__ for e in entities],
            "web": [w.__dict__ for w in web.results],
            "llm": update,
        }]
        return result

    def ask_user(self, state: AgentState) -> dict:
        question = state["decision"]["question"]
        answer = str(interrupt({"question": question})).strip()
        result: dict = {"questions_asked": state.get("questions_asked", 0) + 1}

        # 番号での回答は、プログラムが選択肢と対応づける（LLM には番号付きの選択肢が見えないため）
        picked = pick_candidate(answer, state.get("candidates", []))
        if picked:
            result["target"] = picked
            answer_text = f"{answer}（{picked['label']}: {picked['description']}）"
        else:
            answer_text = answer
        result["clarifications"] = state.get("clarifications", []) + [answer_text]
        result["trace"] = [{"node": "ask_user", "question": question, "answer": answer, "picked": picked}]
        return result

    def respond(self, state: AgentState) -> dict:
        sources = collect_sources(state)
        body = self.llm.chat_text(prompts.RESPOND_SYSTEM, prompts.respond_user(state, sources))
        parts = [body.strip()]
        if state.get("unresponsive"):
            parts.append(f"\n※ SearXNG で応答しなかった検索エンジン: {', '.join(state['unresponsive'])}")
        if sources:
            parts.append("\n### 出典\n" + "\n".join(
                f"[{i}] {s['title']} — {s['url']}" for i, s in enumerate(sources, 1)))
        answer = "\n".join(parts)
        return {"answer": answer, "trace": [{"node": "respond", "answer": answer}]}


def as_candidate(e: wikimedia.Entity) -> Candidate:
    return {"id": e.id, "label": e.label, "description": e.description}


def pick_candidate(answer: str, candidates: list[Candidate]) -> Candidate | None:
    """「2」「2番」のような番号だけの回答なら、その候補を返す。"""
    digits = answer.translate(str.maketrans("０１２３４５６７８９", "0123456789")).rstrip("番 .")
    if digits.isdigit() and 1 <= int(digits) <= len(candidates):
        return candidates[int(digits) - 1]
    return None


def collect_sources(state: AgentState) -> list[Source]:
    """回答で使う出典を、概要 → わかったことの順に重複なく並べる（出典番号はこの順）。"""
    pages = state.get("pages", {})
    urls = [state["summary_url"]] if state.get("target_summary") and state.get("summary_url") else []
    urls += [k["source"] for k in state.get("known", []) if k.get("source")]
    ordered = list(dict.fromkeys(urls))
    return [{"title": pages.get(u, u), "url": u} for u in ordered]


def route(state: AgentState) -> str:
    return state["decision"]["action"]
