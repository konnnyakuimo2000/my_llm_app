"""接続先などの設定。値は .env（git 管理外）から読み込む。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Wikimedia などの API は、誰がアクセスしているかわかる User-Agent を求めている
USER_AGENT = "my-llm-app/0.1 (https://github.com/konnnyakuimo2000/my_llm_app)"


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    searxng_url: str
    llm_timeout: float = 300.0


def load_settings() -> Settings:
    base_url = os.getenv("VL_BASE_URL")
    if not base_url:
        raise RuntimeError(".env に VL_BASE_URL を設定してください")
    return Settings(
        llm_base_url=base_url,
        llm_model=os.getenv("VL_MODEL", "qwen3.8-27b"),
        llm_api_key=os.getenv("VL_API_KEY", "dummy"),
        searxng_url=os.getenv("SEARXNG_URL", "http://localhost:8888"),
    )
