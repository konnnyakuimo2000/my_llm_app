"""調査エージェントのグラフ（例 A: 調べる → 聞き返す → 応答）。

    START → decide ─┬─ search ───→ decide
                    ├─ ask_user ─→ decide
                    └─ respond ──→ END
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from my_llm_app.agent.nodes import Nodes, route
from my_llm_app.agent.state import AgentState
from my_llm_app.config import Settings, load_settings
from my_llm_app.llm import LLM


def build_graph(settings: Settings | None = None, llm: LLM | None = None):
    settings = settings or load_settings()
    nodes = Nodes(settings, llm or LLM(settings))

    g = StateGraph(AgentState)
    g.add_node("decide", nodes.decide)
    g.add_node("search", nodes.search)
    g.add_node("ask_user", nodes.ask_user)
    g.add_node("respond", nodes.respond)

    g.add_edge(START, "decide")
    g.add_conditional_edges("decide", route, ["search", "ask_user", "respond"])
    g.add_edge("search", "decide")
    g.add_edge("ask_user", "decide")
    g.add_edge("respond", END)

    # interrupt（聞き返し）で一時停止して再開するため、状態を保存する
    return g.compile(checkpointer=InMemorySaver())
