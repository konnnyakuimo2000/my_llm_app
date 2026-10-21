"""VL (Vision-Language) サーバーの動作確認用テストスクリプト。

使い方:
    uv run scripts/vl_test.py                     # 既定設定で全テスト
    uv run scripts/vl_test.py --image foo.png     # 画像を指定
    uv run scripts/vl_test.py --skip-image        # 画像テストを省略

接続先は .env か環境変数 (VL_BASE_URL / VL_MODEL / VL_API_KEY)、または引数で指定する。
.env は .env.example をコピーして作成すること。
すべて成功すれば終了コード 0、失敗があれば 1 を返す。
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")  # 接続先などの個別設定は .env (git 管理外) に書く

DEFAULT_BASE_URL = os.getenv("VL_BASE_URL")
DEFAULT_MODEL = os.getenv("VL_MODEL", "qwen3.8-27b")
DEFAULT_API_KEY = os.getenv("VL_API_KEY", "dummy")
DEFAULT_IMAGE = REPO_ROOT / "sample.png"  # リポジトリ直下の sample.png

# 思考モードOFF
NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VLサーバーの動作確認テスト")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=DEFAULT_API_KEY)
    p.add_argument("--image", type=Path, default=DEFAULT_IMAGE, help="画像テストに使う画像")
    p.add_argument("--prompt", default="この画像を説明してください。", help="画像テストのプロンプト")
    p.add_argument("--skip-image", action="store_true", help="画像テストを省略する")
    p.add_argument("--timeout", type=float, default=120.0, help="リクエストのタイムアウト秒数")
    args = p.parse_args()
    if not args.base_url:
        p.error("接続先が未設定です。.env に VL_BASE_URL を書くか --base-url で指定してください")
    return args


def to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def test_models(client: OpenAI, args: argparse.Namespace) -> str:
    """サーバーに接続でき、指定モデルが提供されているか。"""
    ids = [m.id for m in client.models.list().data]
    assert args.model in ids, f"モデル {args.model!r} が見つかりません (利用可能: {ids})"
    return f"利用可能モデル: {ids}"


def test_text(client: OpenAI, args: argparse.Namespace) -> str:
    """テキストのみの応答が返るか。"""
    r = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": "「OK」とだけ返答してください。"}],
        max_tokens=16,
        extra_body=NO_THINKING,
    )
    content = r.choices[0].message.content
    assert content and content.strip(), "応答が空です"
    return content.strip()


def test_image(client: OpenAI, args: argparse.Namespace) -> str:
    """画像入力に対して応答が返るか。"""
    assert args.image.is_file(), f"画像が見つかりません: {args.image}"
    r = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": args.prompt},
            {"type": "image_url", "image_url": {"url": to_data_url(args.image)}},
        ]}],
        extra_body=NO_THINKING,
    )
    content = r.choices[0].message.content
    assert content and content.strip(), "応答が空です"
    usage = r.usage
    tokens = f" (prompt={usage.prompt_tokens}, completion={usage.completion_tokens})" if usage else ""
    return content.strip() + tokens


def run(name: str, fn: Callable[[OpenAI, argparse.Namespace], str],
        client: OpenAI, args: argparse.Namespace) -> bool:
    print(f"=== {name} ===")
    start = time.perf_counter()
    try:
        detail = fn(client, args)
    except Exception as e:  # noqa: BLE001 - どんな失敗も FAIL として報告する
        print(f"[FAIL] {type(e).__name__}: {e} ({time.perf_counter() - start:.2f}s)\n")
        return False
    print(detail)
    print(f"[PASS] ({time.perf_counter() - start:.2f}s)\n")
    return True


def main() -> int:
    args = parse_args()
    print(f"base_url={args.base_url}  model={args.model}\n")
    client = OpenAI(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)

    tests: list[tuple[str, Callable[[OpenAI, argparse.Namespace], str]]] = [
        ("モデル一覧", test_models),
        ("テキスト応答", test_text),
    ]
    if not args.skip_image:
        tests.append(("画像応答", test_image))

    results = [run(name, fn, client, args) for name, fn in tests]
    passed = sum(results)
    print(f"結果: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
