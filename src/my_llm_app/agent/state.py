"""エージェントの状態（State）。"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

Action = Literal["search", "ask_user", "respond"]

# 上限（設計書 5.2 Q-4、10.3）
MAX_QUESTIONS = 2   # 利用者への質問は最大 2 往復
MAX_STEPS = 8       # 行動の選択は最大 8 回
MAX_CANDIDATES = 8  # 同名の候補は最大 8 件（すべて質問の選択肢に出す）
# 候補の 1 位の sitelinks（記事がある言語版などの数）が 2 位のこの倍数以上なら、
# 一般にはその意味を指すとみなし、聞き返さずに前提を明示して進める（例: 富士山）
DOMINANCE_RATIO = 4


class Candidate(TypedDict):
    id: str            # Wikidata の ID（Web 検索だけで見つけた候補は空文字）
    label: str
    description: str
    sitelinks: int     # どれだけ一般的に知られているかの目安


class Source(TypedDict):
    title: str
    url: str


class Fact(TypedDict):
    text: str
    source: str        # 根拠の URL（取得した検索結果にない URL は空文字にする）


class Decision(TypedDict, total=False):
    action: Action
    reason: str
    query: str         # search のとき: Web 検索の言葉
    names: list[str]   # search のとき: Wikidata で引く名前（原語・別名を含む）
    question: str      # ask_user のとき
    guard: str         # プログラムが LLM の選択を変えた場合の理由


class AgentState(TypedDict, total=False):
    request: str                      # 利用者の依頼（原文）
    clarifications: list[str]         # 質問に対する利用者の回答
    known: list[Fact]                 # わかったこと（根拠の URL 付き）
    unknown: list[str]                # わからないこと
    candidates: list[Candidate]       # 同名の候補
    target: Candidate | None          # 特定できた対象
    assumptions: list[str]            # 聞き返さずに置いた前提（報告の冒頭に書く）
    last_question: str                # 直前の質問（同じ質問の繰り返し防止）
    target_summary: str               # 対象の概要（Wikipedia の冒頭）
    summary_url: str                  # 概要の出典 URL
    pages: dict[str, str]             # 取得した検索結果の URL → タイトル（出典一覧を作るため）
    searched: list[str]               # 実行した検索の言葉（同じ検索の繰り返し防止）
    unresponsive: list[str]           # 応答しなかった検索エンジン
    questions_asked: int
    steps: int
    decision: Decision                # 直前に選んだ行動
    trace: Annotated[list[dict], operator.add]   # 行動の記録（実行記録用）
    answer: str
