"""調査エージェントのグラフ。

    START → check_feasibility ─┬─ report_infeasible → END      （例 D: 調べられない依頼）
                               └─ decide ─┬─ search ───→ decide
                                          ├─ ask_user ─→ decide   （例 A: 聞き返す）
                                          └─ respond ──→ END
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from my_llm_app.agent.nodes import Nodes, route, route_feasibility
from my_llm_app.agent.state import AgentState
from my_llm_app.config import Settings, load_settings
from my_llm_app.llm import LLM


def build_graph(settings: Settings | None = None, llm: LLM | None = None):
    settings = settings or load_settings()
    nodes = Nodes(settings, llm or LLM(settings))

    g = StateGraph(AgentState)
    g.add_node("check_feasibility", nodes.check_feasibility)
    g.add_node("report_infeasible", nodes.report_infeasible)
    g.add_node("decide", nodes.decide)
    g.add_node("search", nodes.search)
    g.add_node("ask_user", nodes.ask_user)
    g.add_node("respond", nodes.respond)

    g.add_edge(START, "check_feasibility")
    g.add_conditional_edges("check_feasibility", route_feasibility, ["report_infeasible", "decide"])
    g.add_edge("report_infeasible", END)
    g.add_conditional_edges("decide", route, ["search", "ask_user", "respond"])
    g.add_edge("search", "decide")
    g.add_edge("ask_user", "decide")
    g.add_edge("respond", END)

    # interrupt（聞き返し）で一時停止して再開するため、状態を保存する
    return g.compile(checkpointer=InMemorySaver())
