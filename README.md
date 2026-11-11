# my_llm_app

研究室サーバーの LLM（llama.cpp / qwen3.8-27b）と Web 検索を組み合わせて、ブラウザから会話できる環境。

- **Open WebUI**: チャット画面
- **SearXNG**: Web 検索
- どちらも Docker で動かし、`docker compose up -d` で起動する

## はじめかた

```sh
cp .env.example .env      # 研究室サーバーの接続先などを書く
docker compose up -d      # 起動
```

http://localhost:3000 を開く。詳しくは [docs/setup.md](docs/setup.md) を参照。

## ドキュメント

- [docs/setup.md](docs/setup.md) — セットアップ手順・使い方・トラブル対処
- [docs/requirements_v0.1.md](docs/requirements_v0.1.md) — 要件定義書 v0.1
- [docs/hard_prompts.md](docs/hard_prompts.md) — モデルを試すための難しい問題集

## 注意

研究室サーバーの IP などは `.env`（git 管理外）に書き、リポジトリには書かない（このリポジトリは public）。
