# autonomous AI BCNOFNe system v3 (CryptoArk Edition)

Raspberry Pi 4B で稼働する自律型AI「AYN（あゆにゃん）」のための、元素記号をモチーフとした船のシステム『BCNOFNe』です。
壮大な世界観『DYOR島』を目指し航海するこの船は、Docker Compose を用いたマイクロサービスアーキテクチャで構成されており、自律的な進化と安全な航行をサポートします。

## 要求環境
- Raspberry Pi 4B (Raspberry Pi OS Bookworm 64bit 推奨)
- Docker & Docker Compose
- `.env` の設定 (事前に `.env.example` をコピーして作成)

## 起動方法
1. `.env` ファイルを作成し、必要な設定値（API Keyなど）を記述します。
   ```bash
   cp .env.example .env
   nano .env
   ```
2. Docker Compose でビルド・起動します（または `bash start.sh` を使用）。
   ```bash
   bash start.sh
   ```

## 各サービス概要
- **core**: AIの思考・コマンド解釈・全体指示を行う頭脳。
- **line-gateway**: LINE Bot との通信窓口。
- **discord-gateway**: Discord への通知専用口。
- **voice-router**: 読み上げや音声操作モードの切り替え口（NURSE/OAI/HYB）。
- **browser-agent**: Playwright によるブラウザ操作の実行環境。
- **storage-manager**: SSD/HDD 間の階層化移動などの安全なNAS管理。
- **billing-guard**: 課金状況を監視し、設定上限を超えたら強制停止させる安全装置（最重要）。
- **memory-service**: 短期・長期の記憶と要約を提供するサービス。
- **diary-service**: 日々の航海記録（ログ）をまとめ、日誌を作るサービス。
- **watchdog**: 他コンテナサービスの死活監視と復旧。
- **gui**: ブラウザから見られるステータスダッシュボード。

## 物理キー / モード設定 (予定機能)
- F13: Talk
- F14: Monologue mute
- F15: Status read
- F16: Logbook
- F17: Emergency stop
- F19~F21: Voice mode switch

## 開発ノート
各コンテナは `/app/data` にマウントされた領域（ホスト側の `./data`）にある SQLite データベース `shipos.db` を共有しています。
これにより、複雑なメッセージブローカー等を挟まずにステータスやログを軽量に共有しています。
（※内部データベース名などの互換性は維持されています）
