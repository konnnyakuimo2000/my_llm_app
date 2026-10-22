# 要件定義書 v0.1: llama.cpp + Open WebUI + SearXNG による Web 検索付きチャット

- 作成日: 2026-10-21
- 状態: ドラフト（レビュー待ち）

## 1. 目的

研究室サーバーの LLM と、ブラウザで Web 検索を併用しながら会話できる環境を作る。
既存のソフトウェア（llama.cpp / Open WebUI / SearXNG）の組み合わせと設定だけで実現し、
アプリケーションのコードは書かない。

## 2. 構成

Open WebUI と SearXNG は Docker コンテナとして動かし、`docker compose` でまとめて管理する。
2 つのコンテナは同じ Docker ネットワークに入れ、コンテナ名で互いに通信する。

```
[ブラウザ]
    │ http://localhost:3000
    ▼
┌──────────── この PC: Docker (docker compose) ────────────┐
│                                                            │
│  [open-webui コンテナ] ──── http://searxng:8080 ───▶ [searxng コンテナ]
│        │                     (Docker 内部ネットワーク)        │        │
│        │                                                    │        │
└────────┼────────────────────────────────────────────────────┼────────┘
         │ OpenAI 互換 API (/v1)                              │ 検索
         ▼                                                    ▼
[llama.cpp サーバー]  研究室サーバー             [各検索エンジン (Google, Bing など)]
 qwen3.8-27b (Q4_K_M)
```

| コンポーネント | 役割 | 動かす場所 | 担当 |
|---|---|---|---|
| llama.cpp サーバー | LLM の推論（OpenAI 互換 API） | 研究室サーバー（稼働中） | サーバー管理者 |
| Open WebUI | チャット画面、検索結果を LLM に渡す | この PC の Docker コンテナ | 自分 |
| SearXNG | 複数の検索エンジンをまとめて検索するメタ検索エンジン（API キー不要・自前運用） | この PC の Docker コンテナ | 自分 |

- LLM は研究室サーバーで稼働中の llama.cpp サーバー（`.env` の `VL_BASE_URL`）をそのまま使う。
  Open WebUI からは「OpenAI API 接続」としてつなぐ（Ollama 接続は使わない）。
- この PC には GPU がなく、メモリも 16GB のため、LLM 本体はこの PC では動かさない。
- Docker を使う理由: 依存関係が PC 本体に入らない、Windows でも SearXNG を動かせる、
  他のメンバーや研究室サーバーに同じ構成をそのまま持っていける。

### 2.1 使用する LLM（2026-10-21 時点でサーバーから取得）

| 項目 | 内容 |
|---|---|
| モデル | qwen3.8-27b（`Qwen3.8-27B-UD-Q4_K_M.gguf`） |
| 入力 | テキスト・画像・動画 |
| コンテキスト長 | 32768 トークン |
| ツール呼び出し | 対応 |
| 同時処理数 | 4（研究室で共有） |

## 3. 機能要件

優先度: **Must** = v0.1 で必須 / **Should** = できれば v0.1 / **Could** = 余裕があれば

| ID | 優先度 | 要件 |
|---|---|---|
| F-1 | Must | Open WebUI から研究室サーバーの llama.cpp のモデルを選んで会話できる |
| F-2 | Must | チャット画面で「ウェブ検索」をオンにすると、SearXNG で検索した結果をもとに回答する |
| F-3 | Must | 検索結果を使った回答には、参照元の URL（出典）が表示される |
| F-4 | Must | 前の会話を踏まえて会話を続けられる |
| F-5 | Must | 画像を添付して質問できる |
| F-6 | Should | モデルが自分で検索の要否を判断して検索する（Open WebUI の Function Calling を Native にする） |
| F-7 | Should | 検索 1 回あたりの件数を設定できる（既定 3〜5 件） |
| F-8 | Could | 研究室の他の PC から Open WebUI を使える（同一ネットワーク内のみ） |

## 4. 非機能要件

| ID | 要件 |
|---|---|
| N-1 | 研究室サーバーの IP・ポートや SearXNG の secret_key はリポジトリに書かない。`.env`（git 管理外）に書き、`.env.example` にはダミー値だけを置く（リポジトリは public） |
| N-2 | `docker compose up -d` の 1 コマンドで Open WebUI と SearXNG が起動し、`docker compose down` で停止できる |
| N-3 | ホストに公開するポートは Open WebUI だけにし、`127.0.0.1` にのみ割り当てる。SearXNG は Docker 内部ネットワークからのみ使う（動作確認用にホストへ出す場合も `127.0.0.1` に限る） |
| N-4 | 会話履歴・アカウントなどの Open WebUI のデータは Docker ボリュームに保存し、コンテナを作り直しても消えない |
| N-5 | コンテナは PC の再起動後に自動で起動する（`restart: unless-stopped`） |
| N-6 | コンテナイメージのバージョンを固定する（`latest` を使わない）。更新は動作確認してから行う |
| N-7 | 検索結果を含めた入力がコンテキスト長（32768 トークン）に収まるよう、検索件数と取り込む本文の量を調整する |
| N-8 | 回答が返るまでの時間の目安: 検索なし 30 秒以内、検索あり 90 秒以内（共有サーバーのため混雑時は除く） |

## 5. 各コンポーネントの設定要件

### 5.1 llama.cpp サーバー（研究室サーバー、稼働中）

この PC 側からの変更は行わない。接続先は既存の `.env` の値を使う。

| 項目 | 値 |
|---|---|
| 接続先 | `VL_BASE_URL`（例: `http://<server-ip>:<port>/v1`） |
| API キー | `VL_API_KEY`（認証なし。任意の文字列でよい） |
| モデル名 | `VL_MODEL`（`qwen3.8-27b`） |

### 5.2 docker-compose.yml（この PC）

| 項目 | open-webui | searxng |
|---|---|---|
| イメージ | `ghcr.io/open-webui/open-webui:<固定バージョン>` | `searxng/searxng:<固定バージョン>` |
| ポート公開 | `127.0.0.1:3000:8080` | なし（確認用に出す場合のみ `127.0.0.1:8888:8080`） |
| データ | ボリューム `open-webui` → `/app/backend/data` | `./searxng/settings.yml` を読み取り専用でマウント |
| 環境変数 | 5.3 参照 | `SEARXNG_SECRET`（`.env` から） |
| 再起動 | `unless-stopped` | `unless-stopped` |
| ネットワーク | 共通の内部ネットワーク | 共通の内部ネットワーク |

- 環境変数は `.env` から読み込む（`${変数}` 展開）。

### 5.3 Open WebUI コンテナの環境変数

| 環境変数 | 値 | 説明 |
|---|---|---|
| `OPENAI_API_BASE_URL` | `.env` の `VL_BASE_URL` | 研究室サーバーの llama.cpp |
| `OPENAI_API_KEY` | `.env` の `VL_API_KEY` | 任意の文字列 |
| `ENABLE_OLLAMA_API` | `false` | Ollama 接続は使わない |
| `ENABLE_WEB_SEARCH` | `true` | ウェブ検索を有効にする |
| `WEB_SEARCH_ENGINE` | `searxng` | 検索エンジン |
| `SEARXNG_QUERY_URL` | `http://searxng:8080/search?q=<query>` | SearXNG の検索 URL（コンテナ名で指定。`localhost` ではない） |
| `WEB_SEARCH_RESULT_COUNT` | `5` | 1 回の検索で使う件数（F-7） |

- 環境変数は、新しいボリュームでの初回起動時に設定として保存される。
  以後は管理画面（管理者パネル →「設定」）で保存した値が優先されるため、変更は管理画面で行う。
- タイトル生成などの裏処理（タスクモデル）も同じ llama.cpp に送られる。共有サーバーの負荷になる場合は、
  管理者パネル →「設定」→「インターフェース」で裏処理を減らす（タイトル自動生成・フォローアップ提案をオフなど）。

### 5.4 SearXNG の設定（searxng/settings.yml）

| 項目 | 設定 |
|---|---|
| JSON 出力 | `search.formats` に `json` を追加する（**必須**。ないと Open WebUI からの検索が 403 エラーになる） |
| secret_key | 環境変数 `SEARXNG_SECRET` から渡し、ファイルには書かない |
| レート制限 | `server.limiter` は無効にする（Open WebUI からしか使わない内部用のため） |
| 言語 | 日本語の結果を優先する場合は既定言語を `ja` にする |

### 5.5 .env に追加する項目

既存の `VL_BASE_URL` / `VL_MODEL` / `VL_API_KEY` に加えて、以下を追加する。

| 変数 | 例 | 説明 |
|---|---|---|
| `SEARXNG_SECRET` | ランダムな文字列 | SearXNG の secret_key |

## 6. リポジトリの構成（追加・変更分）

```
docker-compose.yml        # Open WebUI と SearXNG の定義
.env.example              # SEARXNG_SECRET を追加（ダミー値）
searxng/
└── settings.yml          # json 出力の有効化など（秘密情報は含めない）
docs/
└── setup.md              # 起動・停止・更新の手順
```

- これまでの `scripts/start_webui.ps1`（uvx で直接起動）と `.open-webui/` は、Docker 版で動作確認できたら削除する。

## 7. 前提条件・準備

| # | 内容 | 状態 |
|---|---|---|
| P-1 | 研究室サーバーの llama.cpp に、この PC から接続できる | 済（`scripts/vl_test.py` で確認） |
| P-2 | この PC で Docker Desktop が起動し、`docker compose` が使える | インストール済み・未起動 |
| P-3 | Docker のコンテナから研究室サーバーに接続できる | 未確認 |

## 8. 受け入れ基準

v0.1 の完了は以下をすべて満たすこと。

| # | 確認内容 | 期待結果 |
|---|---|---|
| A-1 | `docker compose up -d` → `docker compose ps` | 2 つのコンテナが起動している |
| A-2 | open-webui コンテナ内から `curl <VL_BASE_URL>/models` | `qwen3.8-27b` が一覧に出る |
| A-3 | open-webui コンテナ内から `curl "http://searxng:8080/search?q=test&format=json"` | JSON で検索結果が返る |
| A-4 | ブラウザで http://localhost:3000 を開き、モデル選択を開く | `qwen3.8-27b` が表示される |
| A-5 | ウェブ検索オフで「こんにちは」と送る | 検索せずに回答が返る |
| A-6 | ウェブ検索オンで「今日の東京の天気は？」と送る | SearXNG の検索結果をもとに、出典付きで回答が返る |
| A-7 | 続けて「それについてもっと詳しく」と送る | 前の会話を踏まえて回答する |
| A-8 | `sample.png` を添付して「何が写っている？」と送る | 図形について回答する |
| A-9 | `docker compose down` → `docker compose up -d` の後に開く | アカウントと会話履歴が残っている |
| A-10 | `git grep` で研究室サーバーの IP と SearXNG の secret_key を検索する | ヒットしない |

## 9. v0.1 の対象外

- LangGraph などによるエージェントの自作（必要になったら v0.2 以降で再検討）
- インターネットへの公開、HTTPS 化
- ユーザー管理・利用制限の作り込み（Open WebUI 標準のログインのみ）
- RAG（社内文書・論文の検索）など、Web 検索以外の機能
- 研究室サーバー側（llama.cpp）の設定変更

## 10. 未決事項

| # | 内容 | 案 |
|---|---|---|
| Q-1 | Docker 構成を置く場所 | v0.1 はこの PC。複数人で使うなら同じ docker-compose.yml を研究室サーバーで動かす |
| Q-2 | F-8（研究室内からのアクセス）を v0.1 に含めるか | ポート公開を `0.0.0.0` にし、ファイアウォールを設定する必要がある（管理者権限） |
