# セットアップ手順

Open WebUI（チャット画面）と SearXNG（Web 検索）を Docker で起動し、研究室サーバーの LLM（llama.cpp）と
Web 検索を使って会話できるようにする手順。構成の詳細は [requirements_v0.1.md](requirements_v0.1.md) を参照。

## 必要なもの

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（起動しておく）
- git
- 研究室サーバーの LLM の接続先（IP・ポート）。リポジトリには書いていないので、メンバーに聞く
- 研究室ネットワークへの接続（学外からは研究室サーバーにつながらない）

Python のスクリプト（`scripts/`）も使う場合は [uv](https://docs.astral.sh/uv/) も入れる。

## 1. リポジトリを取得する

```sh
git clone https://github.com/konnnyakuimo2000/my_llm_app.git
cd my_llm_app
```

## 2. .env を作る

`.env.example` をコピーして `.env` を作り、値を書き換える。`.env` は git 管理外なので、コミットされない。

```sh
cp .env.example .env
```

| 変数 | 書く値 |
|---|---|
| `VL_BASE_URL` | 研究室サーバーの LLM の接続先（例: `http://<server-ip>:<port>/v1`） |
| `VL_MODEL` | `qwen3.8-27b`（そのままでよい） |
| `VL_API_KEY` | `dummy`（そのままでよい） |
| `SEARXNG_SECRET` | ランダムな文字列。下のコマンドで作る |

```sh
# どちらか一方で、ランダムな文字列を作る
python -c "import secrets; print(secrets.token_hex(32))"
openssl rand -hex 32
```

## 3. 起動する

```sh
docker compose up -d
```

初回はイメージのダウンロードと初期化に数分かかる。起動の確認:

```sh
docker compose ps
```

`open-webui` と `searxng` の 2 つが `Up` になっていれば OK（`open-webui` が `healthy` になるまで数分かかる）。

## 4. 初期設定

1. ブラウザで **http://localhost:3000** を開く
2. アカウントを作る（最初に作ったアカウントが管理者になる）
3. 左上のモデル選択で `qwen3.8-27b` を選ぶ

研究室サーバーへの接続と Web 検索の設定は、初回起動時に `.env` と `docker-compose.yml` から自動で入る。

## 5. 使い方

- 普通に入力して送ると、LLM が答える
- **Web 検索を使う**: 入力欄の左下、「＋」ボタンの右にある「統合」ボタン（ブロックを組み合わせたアイコン）を押し、
  「ウェブ検索」をオンにしてから送る。回答に出典（URL）が付く
- **画像を使う**: 「＋」から画像を添付して質問する

## 6. よく使うコマンド

| コマンド | 内容 |
|---|---|
| `docker compose up -d` | 起動 |
| `docker compose down` | 停止（アカウント・会話履歴は残る） |
| `docker compose ps` | 状態を確認 |
| `docker compose logs -f open-webui` | ログを表示（Ctrl+C で終了） |
| `docker compose restart open-webui` | Open WebUI だけ再起動 |

**注意**: `docker compose down -v` は、アカウントと会話履歴もすべて削除する。最初からやり直したいとき以外は使わない。

## 7. 更新するとき

`docker-compose.yml` のイメージのバージョンを書き換えてから:

```sh
docker compose pull
docker compose up -d
```

バージョンは固定している（`latest` は使わない）。更新後は、会話と Web 検索ができることを確認する。

## 8. うまくいかないとき

| 症状 | 原因と対処 |
|---|---|
| `docker compose up` で `VL_BASE_URL` や `SEARXNG_SECRET` のエラーが出る | `.env` がない、または値が空。手順 2 をやり直す |
| モデル選択に `qwen3.8-27b` が出ない | 研究室サーバーにつながっていない。研究室ネットワークにいるか確認し、`docker compose restart open-webui` 後にページを再読み込みする |
| 返事が返ってこない・途中で止まる | 研究室サーバーが混んでいるか、一時的に止まっている（共有サーバーのため）。時間をおいて再度試す |
| 「ウェブ検索」が見つからない | 「＋」の中ではなく、その右の「統合」ボタンの中にある。それでも出なければ `Ctrl+F5` で再読み込み |
| http://localhost:3000 が開けない | `docker compose ps` で起動しているか確認。Docker Desktop が起動しているかも確認する |
| `.env` を変えたのに反映されない | 接続先などの設定は初回起動時に保存され、以後は管理画面（管理者パネル →「設定」）の値が優先される。管理画面で変更する |

## 9. Python スクリプト（任意）

LLM サーバーを直接試すスクリプト。uv が必要。

```sh
uv sync
uv run scripts/vl_test.py   # 接続テスト（モデル一覧・テキスト・画像）
uv run scripts/chat.py      # ターミナルで会話
```

難しい問題でモデルを試すときは [hard_prompts.md](hard_prompts.md) のプロンプトを使う。
