"""調査エージェントを CLI で実行する。

使い方:
    uv run scripts/agent.py "マーキュリーについて調べて"
    uv run scripts/agent.py "マーキュリーについて調べて" --verbose

聞き返されたら、ターミナルで答えを入力する。
1 回の実行の記録（各ノードの入出力）は runs/<日時>.json に保存する（git 管理外）。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

from langgraph.types import Command

from my_llm_app.agent.graph import build_graph
from my_llm_app.config import REPO_ROOT


def summarize(node: str, update: dict) -> str:
    if node == "decide":
        d = update["decision"]
        s = f"→ 次の行動: {d['action']}"
        if d.get("query"):
            s += f"「{d['query']}」"
        s += f"（{d.get('reason', '')}）"
        if d.get("guard"):
            s += f"\n   ⚠ プログラムが変更: {d['guard']}"
        return s
    if node == "check_feasibility":
        f = update["feasibility"]
        s = f"→ 調べられるか: {f['verdict']}（{f['reason']}）"
        if f["infeasible_parts"]:
            s += f"\n   調べられない部分: {f['infeasible_parts']}"
        return s
    if node == "search":
        lines = ["   わかったこと:"]
        lines += [f"     - {k['text']}  <{k['source'] or '出典なし'}>" for k in update.get("known", [])]
        lines += [f"   わからないこと: {update.get('unknown', [])}",
                  f"   候補: {[c['label'] + '/' + c['description'] for c in update.get('candidates', [])]}",
                  f"   対象: {update.get('target')}"]
        return "\n".join(lines)
    return ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="調査エージェント（例 A: 調べる → 聞き返す → 応答）")
    p.add_argument("request", help="調査の依頼文")
    p.add_argument("--verbose", "-v", action="store_true", help="各ノードの状態を表示する")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="   [%(name)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 40}

    payload: object = {"request": args.request}
    while True:
        interrupted = None
        for chunk in graph.stream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupted = update[0].value
                    continue
                print(f"[{node}]")
                if args.verbose and update:
                    text = summarize(node, update)
                    if text:
                        print(text)
        if interrupted is None:
            break
        print("\n" + interrupted["question"])
        try:
            answer = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        payload = Command(resume=answer)

    state = graph.get_state(config).values
    print("\n" + state.get("answer", "(回答なし)"))

    runs = REPO_ROOT / "runs"
    runs.mkdir(exist_ok=True)
    out = runs / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(state, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n(実行記録: {out.relative_to(REPO_ROOT)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
