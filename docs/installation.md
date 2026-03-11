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
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Botのアクセストークン / LINE Bot access token
- `LINE_CHANNEL_SECRET`: LINE Botのシークレット / LINE Bot secret
- `LINE_ADMIN_USER_ID`: 管理者のLINEユーザーID / Administrator's LINE user ID
- `NGROK_AUTHTOKEN`: (Tailscaleを使わない場合) ngrokの認証トークン / ngrok auth token (if not using Tailscale)
