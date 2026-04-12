# Installation Guide / インストールガイド

## Requirements / 必要環境

- Raspberry Pi 4B (Raspberry Pi OS Bookworm 64bit 推奨 / Recommended)
- Docker
- Docker Compose
- Tailscale (リモートアクセス用推奨 / Recommended for remote access)
- LINE Messaging API Channel (LINE連携用 / For LINE integration)

---

## Warning: Fork Recommended / 警告: Fork推奨

AYN が自動でコード修正・commit・push を行うため、本家リポジトリを直接運用対象にすると履歴や main ブランチが不安定になりやすいです。
Since AYN autonomously corrects, commits, and pushes code, using the upstream repository directly makes the history and main branch unstable.

そのため、ユーザーはまず本リポジトリを Fork し、Fork 側を運用用リポジトリとして使用する前提でインストールを行ってください。
Therefore, users should first Fork this repository and perform the installation assuming the Fork will be used as the operational repository.

また、AI の自動変更は main 直push ではなく、専用作業ブランチ経由 + 人間承認 merge を基本方針としています。
Also, the basic policy for AI's automatic changes is not direct push to main, but via a dedicated working branch + human-approved merge.

---

## LLM (Ollama) の設定 (Windows ホスト利用)

BCNOFNe は Windows PC 上で動作する Ollama を利用するように構成可能です。

### 1. Windows Ollama の外部アクセス許可
デフォルトでは Ollama は `localhost` のみ受け付けます。外部 (Docker や他の機器) から接続するには、環境変数を設定して再起動する必要があります。

1. Windows のシステム環境変数に `OLLAMA_HOST=0.0.0.0` を追加します。
2. Ollama アプリを完全に終了し、再度起動します。
3. Windows ファイアウォールで TCP ポート `11434` の受信を許可します。

### 2. BCNOFNe 側の設定 (.env)
`.env` ファイルで以下の項目を設定します。

```env
AI_PROVIDER_MODE=local_preferred
OLLAMA_BASE_URL=http://<WINDOWS_IP>:11434
```

### 3. 疎通確認
以下のコマンドで接続テストが可能です。
```bash
docker exec -it shipos-core python llm/health.py
```
またはホスト側から:
```bash
curl http://<WINDOWS_IP>:11434/api/tags
```

---

## Installation Steps / インストール手順

まず、GitHub でこのリポジトリを自身のフォークとしてコピーしてください。
First, copy this repository as your own fork on GitHub.

```bash
# フォークしたリポジトリをクローン
# Clone your forked repository
git clone https://github.com/YOUR_USERNAME/BCNOFNe.git

# ディレクトリへ移動
# Move into the directory
cd BCNOFNe

# 起動スクリプトを実行 (または docker compose を使用)
# Execute the startup script (or use docker compose)
./start.sh
# or
docker compose up -d
```

---

## Environment Setup / 環境設定

ディレクトリ内にある `.env.example` をコピーして `.env` を作成します。
Copy `.env.example` in the directory to create `.env`.

```bash
cp .env.example .env
nano .env
```

`.env` ファイルには以下の重要な環境変数を設定してください。
Set the following critical environmental variables in the `.env` file.

- `OPENAI_API_KEY`: OpenAIのAPIキー / OpenAI API key
- `OLLAMA_BASE_URL`: OllamaサーバーのURL (例: `http://ollama:11434`) / Ollama server URL
- `LLM_MODEL_TEXT`: 使用するローカルモデル名 (例: `qwen2.5:7b`) / Local model name
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Botのアクセストークン / LINE Bot access token
- `LINE_CHANNEL_SECRET`: LINE Botのシークレット / LINE Bot secret
- `LINE_ADMIN_USER_ID`: 管理者のLINEユーザーID / Administrator's LINE user ID
- `NGROK_AUTHTOKEN`: (Tailscaleを使わない場合) ngrokの認証トークン / ngrok auth token (if not using Tailscale)

---

## Local AI (Ollama) Setup / ローカルAIの設定

BCNOFNe v3 は、デフォルトで Ollama コンテナを起動します。
BCNOFNe v3 launches an Ollama container by default.

1. **モデルのプル / Pull the Model**:
   コンテナ起動後、以下のコマンドでモデルをダウンロードしてください。
   After starting the containers, download the model with the following command:
   ```bash
   docker exec -it shipos-ollama ollama pull qwen2.5:7b
   ```

2. **リソース制限 / Resource Notice**:
   Raspberry Pi 4B (8GB) で 7B モデルを動かす場合、スワップ設定の調整を推奨します。
   When running 7B models on Raspberry Pi 4B (8GB), adjusting swap settings is recommended.
