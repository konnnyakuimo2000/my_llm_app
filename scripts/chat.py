"""VL サーバーと自然言語で対話するためのテスト用チャットスクリプト。

使い方:
    uv run scripts/chat.py
    uv run scripts/chat.py --system "あなたは整形外科医です。" --thinking

会話中のコマンド:
    /image <パス> [質問]  画像を添えて質問する (質問を省略すると画像の説明を求める)
    /reset               会話履歴を消す
    /exit                終了する (Ctrl+C / Ctrl+D でも可)

接続先は .env (VL_BASE_URL / VL_MODEL / VL_API_KEY) か引数で指定する。
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import shlex
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")  # 接続先などの個別設定は .env (git 管理外) に書く


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VLサーバーとの対話テスト")
    p.add_argument("--base-url", default=os.getenv("VL_BASE_URL"))
    p.add_argument("--model", default=os.getenv("VL_MODEL", "qwen3.8-27b"))
    p.add_argument("--api-key", default=os.getenv("VL_API_KEY", "dummy"))
    p.add_argument("--system", help="システムプロンプト")
    p.add_argument("--thinking", action="store_true", help="思考モードを有効にする")
    p.add_argument("--timeout", type=float, default=300.0, help="リクエストのタイムアウト秒数")
    args = p.parse_args()
    if not args.base_url:
        p.error("接続先が未設定です。.env に VL_BASE_URL を書くか --base-url で指定してください")
    return args


def to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def image_message(arg: str) -> dict:
    """`/image <パス> [質問]` の引数から、画像付きのユーザーメッセージを作る。"""
    parts = shlex.split(arg, posix=False)
    if not parts:
        raise ValueError("使い方: /image <パス> [質問]")
    path = Path(parts[0].strip('"'))
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        raise FileNotFoundError(f"画像が見つかりません: {path}")
    question = " ".join(parts[1:]) or "この画像を説明してください。"
    return {"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": to_data_url(path)}},
    ]}


def stream_reply(client: OpenAI, args: argparse.Namespace, messages: list[dict]) -> str:
    """応答をストリーミング表示し、全文を返す。"""
    stream = client.chat.completions.create(
        model=args.model,
        messages=messages,
        stream=True,
        extra_body={"chat_template_kwargs": {"enable_thinking": args.thinking}},
    )
    chunks: list[str] = []
    finish_reason = None
    for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if choice.delta.content:
            print(choice.delta.content, end="", flush=True)
            chunks.append(choice.delta.content)
        finish_reason = choice.finish_reason or finish_reason
    print()
    if finish_reason != "stop":
        # 途中で切れた原因の切り分け用 (length=長さ上限, None=接続が途中で切れた)
        print(f"(応答が途中で終了しました: finish_reason={finish_reason})")
    return "".join(chunks)


def main() -> int:
    args = parse_args()
    client = OpenAI(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)

    initial = [{"role": "system", "content": args.system}] if args.system else []
    messages = list(initial)
    print(f"model={args.model}  (/image <パス> [質問], /reset, /exit)\n")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line == "/exit":
            break
        if line == "/reset":
            messages = list(initial)
            print("(履歴を消しました)\n")
            continue

        try:
            if line.startswith("/image"):
                user_msg = image_message(line.removeprefix("/image").strip())
            else:
                user_msg = {"role": "user", "content": line}
        except (ValueError, OSError) as e:
            print(f"(エラー) {e}\n")
            continue

        messages.append(user_msg)
        print("bot> ", end="", flush=True)
        try:
            reply = stream_reply(client, args, messages)
        except KeyboardInterrupt:
            print("\n(中断しました)\n")
            messages.pop()
            continue
        except Exception as e:  # noqa: BLE001 - 通信エラー等を表示して会話を続ける
            print(f"\n(エラー) {type(e).__name__}: {e}\n")
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": reply})
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
